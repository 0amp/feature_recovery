import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from scipy.optimize import linear_sum_assignment

class AutoEncoder(nn.Module): 
    def __init__(self, input_size, hidden_size, sparsity_penalty):
        super(AutoEncoder, self).__init__()
        self.encoder = nn.Linear(input_size, hidden_size)
        self.decoder = nn.Linear(hidden_size, input_size)
        self.sparsity_penalty = sparsity_penalty

    def forward(self, x):
        encoded = F.relu(self.encoder(x))
        decoded = self.decoder(encoded)

        return encoded, decoded
    
    def loss(self, x): 

        encoded, decoded = self.forward(x)
        recon_loss = nn.MSELoss()(decoded, x)
        sparsity = torch.abs(encoded).mean()
        num_nonzero = torch.sum(encoded != 0) // encoded.shape[0]
        loss = recon_loss + self.sparsity_penalty * sparsity

        return loss, recon_loss, sparsity, num_nonzero, encoded

def hungarian(orig_features, decoder_features): 
    # orig_features: (num_samples, residual_dim)
    # decoder_features: (num_samples, decoder_dim)
    # cosine_similarities: (residual_dim, decoder_dim)
    
    assert torch.isnan(orig_features).sum() == 0
    assert torch.isnan(decoder_features).sum() == 0

    orig_features_normed = orig_features / (torch.linalg.norm(orig_features, dim=0) + 1e-8)
    decoder_features_normed = decoder_features / (torch.linalg.norm(decoder_features, dim=0) + 1e-8)
    cost_matrix = orig_features_normed.T @ decoder_features_normed
    row_idxs, col_idxs = linear_sum_assignment(cost_matrix, maximize=True)
    return col_idxs, cost_matrix[row_idxs, col_idxs].sum().item() / orig_features.shape[1]


