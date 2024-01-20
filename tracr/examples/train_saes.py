import jax
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import seaborn as sns 
import haiku as hk
import sys 
import os
import logging
from collections import defaultdict
import pickle
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F

# The default of float16 can lead to discrepancies between outputs of
# the compiled model and the RASP program.
jax.config.update('jax_default_matmul_precision', 'float32')

from tracr.compiler import compiling
from tracr.compiler import lib
from tracr.rasp import rasp

from scipy.optimize import linear_sum_assignment

from utils import *

if __name__ == '__main__': 

    parser = argparse.ArgumentParser()
    parser.add_argument('start', type=int)
    parser.add_argument('end', type=int)
    parser.add_argument('--suffix', type=str, default='')
    parser.add_argument('--device', type=int, default=0)
    args = parser.parse_args()

    # program params
    vocab = {0,1,2,3,4,5,6,7,8,9}
    max_seq_len = 10
    num_samples = 10**3
    max_programs = args.end - args.start + 1 # inclusive
    seed = 0

    # training params
    device = torch.device(f'cuda:{args.device}' if torch.cuda.is_available() else 'cpu')
    epochs = 100
    batch_size = 8192
    eval_batch_size = 8192
    lr = 0.001
    ae_hdim_scale = 4
    sparsity_penalty = 0.1

    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    jax.random.PRNGKey(seed)
    hk.PRNGSequence(seed)

    data_path = 'data'

    # check if data exists
    if os.path.exists(f'{data_path}/autoencoder/results{args.suffix}.pkl'):
        with open(f'{data_path}/autoencoder/results{args.suffix}.pkl', 'rb') as f:
            results = pickle.load(f)
    else:
        results = {}

    to_ignore = np.load(f'{data_path}/to_ignore.npy')

    for program_id in range(args.start, args.end+1):
        
        if program_id in to_ignore: 
            continue

        print(f'Program {program_id}')

        residuals = np.load(f'{data_path}/activations/program_{program_id}.npy')
        num_layers = residuals.shape[-2]
        residuals = residuals.reshape((-1, residuals.shape[-1])) # n_samples x n_features

        residuals = torch.tensor(residuals)
        train_set, test_set = torch.utils.data.random_split(residuals, [len(residuals)//2, len(residuals) - len(residuals)//2])
        train_loader = torch.utils.data.DataLoader(train_set, batch_size=batch_size, shuffle=True)
        test_loader = torch.utils.data.DataLoader(test_set, batch_size=eval_batch_size, shuffle=True)
        orig_features = test_set.dataset.clone().detach()[test_set.indices]

        ae = AutoEncoder(residuals.shape[1], ae_hdim_scale * residuals.shape[1], sparsity_penalty).to(device)
        optimizer = torch.optim.Adam(ae.parameters(), lr=lr)

        # track metrics per epoch
        losses, recon_losses, l1_sparsity, l0_sparsity = [], [], [], []
        test_losses, test_recon_losses, test_l1_sparsity, test_l0_sparsity = [], [], [], []
        effective_ranks, ordered_l2 = [], []

        pbar = tqdm(range(epochs))
        for epoch in pbar: 
             
            # test 
            with torch.no_grad(): 
                temp_loss, temp_recon_loss, temp_l1_sparsity, temp_l0_sparsity = [], [], [], []
                test_acts = []
                for batch in test_loader: 
                    batch = batch.to(device)
                    loss, recon_loss, sparsity, num_nonzero, encoded = ae.loss(batch)
                    temp_loss.append(loss.detach().cpu().item())
                    temp_recon_loss.append(recon_loss.detach().cpu().item())
                    temp_l1_sparsity.append(sparsity.detach().cpu().item())
                    temp_l0_sparsity.append(num_nonzero.detach().cpu().item())
                    test_acts.append(encoded.detach().cpu())
                test_losses.append(np.mean(temp_loss))
                test_recon_losses.append(np.mean(temp_recon_loss))
                test_l1_sparsity.append(np.mean(temp_l1_sparsity))
                test_l0_sparsity.append(np.mean(temp_l0_sparsity))
                test_acts = torch.cat(test_acts, dim=0)
                num_nonzero = torch.sum(test_acts != 0, dim=0)
                nnz_idxs = torch.nonzero(num_nonzero).squeeze()
                test_acts = test_acts[:, nnz_idxs]
                effective_rank = torch.linalg.matrix_rank(test_acts)
                effective_ranks.append(effective_rank.item())
                permutation, dist = hungarian(orig_features, test_acts)
                ordered_l2.append(dist)

            # train
            temp_loss, temp_recon_loss, temp_l1_sparsity, temp_l0_sparsity = [], [], [], []
            for batch in train_loader: 
                batch = batch.to(device)
                optimizer.zero_grad()
                loss, recon_loss, sparsity, num_nonzero, _ = ae.loss(batch)
                loss.backward()
                optimizer.step()

                temp_loss.append(loss.detach().cpu().item())
                temp_recon_loss.append(recon_loss.detach().cpu().item())
                temp_l1_sparsity.append(sparsity.detach().cpu().item())
                temp_l0_sparsity.append(num_nonzero.detach().cpu().item())

            losses.append(np.mean(temp_loss))
            recon_losses.append(np.mean(temp_recon_loss))
            l1_sparsity.append(np.mean(temp_l1_sparsity))
            l0_sparsity.append(np.mean(temp_l0_sparsity))

            pbar.set_description(f'Epoch {epoch+1}: loss {test_losses[-1]:.4f}, recon_loss {test_recon_losses[-1]:.4f}, l1_sparsity {test_l1_sparsity[-1]:.4f}, l0_sparsity {test_l0_sparsity[-1]:.4f}, effective_rank {effective_ranks[-1]:.4f}, ordered_l2 {ordered_l2[-1]:.4f}')

        # save metrics
        results[program_id] = {
            'residual_dim': residuals.shape[1],
            'num_layers': num_layers,
            'losses': losses,
            'recon_losses': recon_losses,
            'l1_sparsity': l1_sparsity,
            'l0_sparsity': l0_sparsity,
            'test_losses': test_losses,
            'test_recon_losses': test_recon_losses,
            'test_l1_sparsity': test_l1_sparsity,
            'test_l0_sparsity': test_l0_sparsity,
            'effective_ranks': effective_ranks,
            'ordered_l2': ordered_l2
        }

        # save results
        with open(f'{data_path}/autoencoder/results{args.suffix}.pkl', 'wb') as f:
            pickle.dump(results, f)
    
    print("FINISHED")
