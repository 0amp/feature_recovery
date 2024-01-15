from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import haiku as hk
import jax
import logging
import pickle
from collections import defaultdict

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

    vocab = {0,1,2,3,4,5,6,7,8,9}
    max_seq_len = 10
    num_samples = 10**1
    seed = 0

    np.random.seed(seed)
    jax.random.PRNGKey(seed)
    hk.PRNGSequence(seed)

    samples = []
    for i in range(num_samples): 
        r = np.random.randint(0, 10**10)
        samples.append(r)

    not_numerical_ids = defaultdict(list)
    out_of_range_ids = defaultdict(list)
    outputs = defaultdict(list)
    for program_name in generated_lib.__all__:

        program_id = int(program_name.split('_')[-1])
        program = getattr(generated_lib, program_name)

        if program_id == 2: 
            break

        compiled_model = compiling.compile_rasp_to_model(
            program=program,
            vocab=vocab,
            max_seq_len=max_seq_len,
            causal=False,
            compiler_bos="bos",
            compiler_pad="pad",
            mlp_exactness=100)
    
        residuals = []
        for sample in tqdm(samples): 
            seq = lex_ord_to_seq(sample, max_seq_len)
            out = compiled_model.apply(["bos"] + seq)

            # save activations
            residuals.append(out.residuals)
            
            out_seq = out.decoded[1:]
            try: 
                out_seq = [int(o) for o in out_seq]
            except: 
                print(f'non-numerical output: program {program_id} outputted {out_seq} for input {sample}')
                not_numerical_ids[program_id].append(sample)
                continue
            try: 
                assert [n in vocab for n in out_seq]
            except:
                print(f'output values out of range: program {program_id} outputted {out_seq} for input {sample}')
                out_of_range_ids[program_id].append(sample)
                continue

            outputs[program_id].append(seq_to_lex_ord(out_seq, max_seq_len))

        residuals = np.array(residuals)
        np.save(f'data/activations/program_{program_id}.npy', residuals)
        
    with open('data/samples.pkl', 'wb') as f:
        pickle.dump(samples, f)
    with open('data/outputs.pkl', 'wb') as f: 
        pickle.dump(outputs, f)
    with open('data/not_numerical_ids.pkl', 'wb') as f:
        pickle.dump(not_numerical_ids, f)
    with open('data/out_of_range_ids.pkl', 'wb') as f:
        pickle.dump(out_of_range_ids, f)


    


