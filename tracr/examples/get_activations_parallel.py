from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import haiku as hk
import jax
import logging
import pickle
from collections import defaultdict
from multiprocessing import Pool, Manager
import sys
import os
import time

from tracr.datasets import generated_lib
from tracr.compiler import compiling
from tracr.rasp import rasp

logging.basicConfig(level=logging.ERROR)

def lex_ord_to_seq(lex_ord, max_seq_len): 
    assert lex_ord < 10**max_seq_len and lex_ord >= 0
    seq = []
    for i in range(max_seq_len): 
        seq.append(lex_ord % 10)
        lex_ord = lex_ord // 10
    return seq

def seq_to_lex_ord(seq, max_seq_len): 
    assert len(seq) == max_seq_len
    lex_ord = 0
    for i in range(max_seq_len): 
        lex_ord += seq[i] * 10**i
    return lex_ord

if __name__ == '__main__':

    stime = time.time()
    vocab = {0,1,2,3,4,5,6,7,8,9}
    max_seq_len = 10
    num_samples = 1000

    # goes from start to end inclusive 
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    max_programs = end - start

    num_processes = 24
    seed = 0

    np.random.seed(seed)
    jax.random.PRNGKey(seed)
    hk.PRNGSequence(seed)

    samples = []
    for i in range(num_samples): 
        r = np.random.randint(0, 10**10)
        samples.append(r)

    print("compiling models")
    models = {}
    for program_id in tqdm(range(start, end+1)):
        program_name = f'program_{program_id}'
        program = getattr(generated_lib, program_name)

        compiled_model = compiling.compile_rasp_to_model(
            program=program,
            vocab=vocab,
            max_seq_len=max_seq_len,
            causal=False,
            compiler_bos="bos",
            compiler_pad="pad",
            mlp_exactness=100)

        models[program_id] = compiled_model

    def worker(program_id): 

        model = models[program_id]
        residuals = []
        outputs = []
        for sample in samples:
            seq = lex_ord_to_seq(sample, max_seq_len)
            out = model.apply(["bos"] + seq)

            # save activations
            residuals.append(out.residuals)
            out_seq = out.decoded[1:]

            not_numerical = []
            out_of_range = []

            try: 
                out_seq = [int(o) for o in out_seq]
            except: 
                # print(f'non-numerical output: program {program_id} outputted {out_seq} for input {sample}')
                not_numerical.append(sample)
                continue
            try: 
                assert [n in vocab for n in out_seq]
            except:
                # print(f'output values out of range: program {program_id} outputted {out_seq} for input {sample}')
                out_of_range.append(sample)
                continue
            
            outputs.append(seq_to_lex_ord(out_seq, max_seq_len))

        residuals = np.array(residuals)
        np.save(f'data/activations/program_{program_id}.npy', residuals)

        print(f"program {program_id} finished")
        return program_id, outputs, not_numerical, out_of_range

    # not_numerical_ids = Manager().dict({i: [] for i in range(max_programs)})
    # out_of_range_ids = Manager().dict({i: [] for i in range(max_programs)})
    # outputs = Manager().dict({i: [] for i in range(max_programs)})

    if os.path.exists('data/samples.pkl'):
        with open('data/samples.pkl', 'rb') as f:
            assert pickle.load(f) == samples
    if os.path.exists('data/outputs.pkl'):
        with open('data/outputs.pkl', 'rb') as f:
            outputs = pickle.load(f)
    else:
        outputs = defaultdict(list)
    if os.path.exists('data/not_numerical_ids.pkl'):
        with open('data/not_numerical_ids.pkl', 'rb') as f:
            not_numerical_ids = pickle.load(f)
    else: 
        non_numerical_ids = defaultdict(list)
    if os.path.exists('data/out_of_range_ids.pkl'):
        with open('data/out_of_range_ids.pkl', 'rb') as f:
            out_of_range_ids = pickle.load(f)
    else:
        out_of_range_ids = defaultdict(list)
    
    pool = Pool(num_processes)
    for program_id, out_seq, not_numerical, out_of_range in pool.imap_unordered(worker, range(start, end+1)):
        outputs[program_id] = out_seq
        not_numerical_ids[program_id] = not_numerical
        out_of_range_ids[program_id] = out_of_range
    pool.close()
        
    print(outputs)
    print("FINISHED in ", time.time() - stime, " seconds")
    with open('data/samples.pkl', 'wb') as f:
        pickle.dump(samples, f)
    with open('data/outputs.pkl', 'wb') as f: 
        pickle.dump(outputs, f)
    with open('data/not_numerical_ids.pkl', 'wb') as f:
        pickle.dump(not_numerical_ids, f)
    with open('data/out_of_range_ids.pkl', 'wb') as f:
        pickle.dump(out_of_range_ids, f)