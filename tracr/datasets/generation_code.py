from tqdm import tqdm
import numpy as np 
from typing import List, Sequence
import math
import os 
import sys
from threading import Thread
import logging

from tracr.compiler import compiling
from tracr.rasp import rasp
from tracr.compiler.lib import *

import jax
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import seaborn as sns 
import haiku as hk

# The default of float16 can lead to discrepancies between outputs of
# the compiled model and the RASP program.
jax.config.update('jax_default_matmul_precision', 'float32')

from tracr.compiler import lib
from tracr.rasp import rasp

logging.basicConfig(level=logging.ERROR)

PREAMBLE = '''"""RASP programs only using the subset of RASP supported by the compiler."""

from typing import List, Sequence
import math

from tracr.rasp import rasp
from tracr.compiler.lib import *

'''

PROGRAM_TEMPLATE = '''def make_program_{program_id}() -> rasp.SOp: '''

MAP_OPS_LIB = [
    'lambda x: -x', 'math.sin', 'math.cos', 'math.tan',
    'lambda x: x ** 2', 'lambda x: x ** 0.5', 'lambda x: abs(x)', 'math.log', 'lambda x: 1 / (x + 1e-5)',
    'lambda x: x + 1', 'lambda x: x - 1', 'lambda x: 2 * x', 'lambda x: x / 2', 'lambda x: x % 2',
    'math.atan', 'math.ceil', 'math.floor',
    'lambda x: round(x)', 'lambda x: x ** 1.5', 'lambda x: 1.1 ** x', 'math.sqrt', 'lambda x: x * -1',
    'lambda x: x / 3', 'lambda x: x * 5', 'lambda x: x - 5', 'lambda x: x // 2', 'lambda x: x % 3',
]

SELECT_OPS_LIB = [
    'rasp.Comparison.TRUE', 'rasp.Comparison.FALSE', 'rasp.Comparison.EQ', 'rasp.Comparison.LEQ', 'rasp.Comparison.GEQ',
    'rasp.Comparison.LT', 'rasp.Comparison.GT', 'rasp.Comparison.NEQ',
]

SMAP_OPS_LIB = [
    'lambda x, y: x + y',
    'lambda x, y: x - y',
    'lambda x, y: x * y',
    'lambda x, y: x / (y + 1) if y != -1 else 0',  # Avoid division by zero
    'lambda x, y: 0 if x == y else 1',
    'lambda x, y: (2 * x + y) / 2',
    'lambda x, y: (x + y) / 2',
    'lambda x, y: min(x, y)',
    'lambda x, y: max(x, y)',
    'lambda x, y: x % y if y else 0',  # Avoid division by zero
    'lambda x, y: y % x if x else 0',  # Avoid division by zero
    'lambda x, y: abs(x - y)',
    'lambda x, y: min((x**2 + y**2)**0.5, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: min((x * y)**0.5, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: min((x * y) ** 0.5, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: 1 / (x + y) if x + y else 0',  # Avoid division by zero
    'lambda x, y: 2 * x + 3 * y',
    'lambda x, y: x / (y + 1) if y != -1 else 0',  # Avoid division by zero
    'lambda x, y: y / (x + 1) if x != -1 else 0',  # Avoid division by zero
    'lambda x, y: (x + y) / (x - y + 1) if x != y - 1 else 0',  # Avoid division by zero
    'lambda x, y: (x - y) / (x + y + 1) if x + y != -1 else 0',  # Avoid division by zero
    'lambda x, y: min((x * x + y * y) ** 0.5, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: x * x - y * y',
    'lambda x, y: min((x + y) ** 1.1, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: min((x - y) ** 1.1, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: min(x ** 1.1 + y ** 1.1, 10**5)',  # Limit the result to avoid overflow
    'lambda x, y: min(x ** 1.1 - y ** 1.1, 10**5)'  # Limit the result to avoid overflow
]

def write_select(i1, i2, func, var_name): 
    write = ''
    write += f'\n   {var_name} = rasp.Select({i1}, {i2}, {func})'
    aggregation_op = np.random.choice(['aggregate', 'selectorwidth'])
    if aggregation_op == 'aggregate': 
        aggergation_i = np.random.choice([i1, i2])
        write += f'\n   {var_name} = rasp.Aggregate({var_name}, {aggergation_i}).named("{var_name}")'
    elif aggregation_op == 'selectorwidth':
        write += f'\n   {var_name} = rasp.SelectorWidth({var_name}).named("{var_name}")'
    return write

def generate_categorical_programs(N, max_ops, program_template, select_ops_lib, map_ops_lib, smap_ops_lib, seed): 
    """
    """
    np.random.seed(seed)
    for n in range(N): 
        program = program_template
        num_ops = np.random.randint(1, max_ops + 1)
        avail_vars = ['rasp.tokens', 'rasp.indices']
        for j in range(num_ops): 
            var_name = f't_{j}'
            if len(avail_vars) == 2: 
                # collapse 
                i1, i2 = avail_vars.pop(), avail_vars.pop()
                op = np.random.choice(['select', 'smap'])
                if op == 'select': 
                    func = np.random.choice(select_ops_lib)
                    program += write_select(i1, i2, func, var_name)
                elif op == 'smap': 
                    func = np.random.choice(smap_ops_lib)
                    program += f'\n   {var_name} = rasp.SequenceMap({func}, {i1}, {i2}).named("{var_name}")'
                avail_vars.append(var_name)
            else: 
                add_new_var = np.random.rand() < 0.5
                i1 = avail_vars.pop()
                op = np.random.choice(['map', 'select'])
                if op == 'map': 
                    func = np.random.choice(map_ops_lib)
                    program += f'\n   {var_name} = rasp.Map({func}, {i1}).named("{var_name}")'
                elif op == 'select': 
                    func = np.random.choice(select_ops_lib)
                    program += write_select(i1, i1, func, var_name)
                # elif op == 'smap': 
                #     func = np.random.choice(smap_ops_lib)
                #     program += f'\n   {var_name} = rasp.SequenceMap({func}, {i1}, {i1}).named("{var_name}")'
                avail_vars.append(var_name)
                if add_new_var: 
                    avail_vars.append(i1)
        program += f'\n   return {var_name}'
        yield program

def compile_and_test_program(program_def, vocab, max_seq_len, flag_dict): 
    try:
        compiled_model = compiling.compile_rasp_to_model(
            program=program_def,
            vocab=vocab,
            max_seq_len=max_seq_len,
            causal=False,
            compiler_bos="bos",
            compiler_pad="pad",
            mlp_exactness=100)
        compiled_model.apply(["bos", 0,1,2,3,4,5,6,7,8,9]).decoded
        compiled_model.apply(["bos", 9,8,7,6,5,4,3,2,1,0]).decoded
        compiled_model.apply(["bos", 0]).decoded
        flag_dict["completed"] = True
    except Exception as e:
        print(e)

N = 10
MAX_OPS = 10
seed = 0

if __name__ == '__main__':
    programs_gen = generate_categorical_programs(N, MAX_OPS, PROGRAM_TEMPLATE, SELECT_OPS_LIB, MAP_OPS_LIB, SMAP_OPS_LIB, seed)

    # check if file exists
    if not os.path.exists("generated_categorical_lib.py"):
        with open("generated_categorical_lib.py", "w") as file:
            file.write(PREAMBLE)

    max_i = max([-1] + [int(line.split('make_program_')[1].split('()')[0]) for line in open("generated_categorical_lib.py", "r") if " = make_program_" in line])
    vocab = {0,1,2,3,4,5,6,7,8,9}
    max_seq_len = 10
    pbar = tqdm(total=N)

    with open('generated_categorical_lib.py', 'a') as file:
        
        file_program_id = max_i + 1
        for i, program_def in enumerate(tqdm(programs_gen)):
            flag = {"completed": False}
            program_def = program_def.format(program_id=file_program_id)  # Use file_program_id here
            exec(program_def + f'\n\nto_exec = make_program_{file_program_id}()')

            thread = Thread(target=compile_and_test_program, args=(to_exec, vocab, max_seq_len, flag))
            thread.start()
            thread.join(timeout=30)  # Timeout of 30 seconds
            print("THREAD FINISHED")

            if flag["completed"]:
                program_def = program_def + '\n\n' + f'program_{file_program_id} = make_program_{file_program_id}()\n\n'
                file.write(program_def)
                file.flush()
                os.fsync(file.fileno())
                file_program_id += 1
                pbar.update(1)

            else:
                print(f"Generated program {file_program_id  } either had an error or timed out.")