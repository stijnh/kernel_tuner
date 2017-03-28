#!/usr/bin/env python
import numpy
from kernel_tuner import tune_kernel
from collections import OrderedDict

def tune():
    with open('reduction.cl', 'r') as f:
        kernel_string = f.read()

    tune_params = OrderedDict()
    tune_params["block_size_x"] = [2**i for i in range(5,11)]
    tune_params["vector"] = [2**i for i in range(3)]
    tune_params["num_blocks"] = [2**i for i in range(5,11)]

    problem_size = "num_blocks"
    size = 80000000
    max_blocks = max(tune_params["num_blocks"])

    x = numpy.random.rand(size).astype(numpy.float32)
    sum_x = numpy.zeros(max_blocks).astype(numpy.float32)
    n = numpy.int32(size)

    args = [sum_x, x, n]

    return tune_kernel("sum_floats", kernel_string, problem_size,
        args, tune_params, grid_div_x=[], verbose=True)


if __name__ == "__main__":
    tune()


