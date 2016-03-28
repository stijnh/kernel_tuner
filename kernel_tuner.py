#!/usr/bin/env python
""" A simple CUDA kernel tuner in Python

The goal of this project is to provide a - as simple as possible - tool 
for tuning CUDA kernels. This implies that any CUDA kernel can be tuned 
without requiring extensive changes to the original kernel code.

A very common problem in CUDA programming is that some combination of 
thread block dimensions and other kernel parameters, like tiling or 
unrolling factors, results in dramatically better performance than other 
kernel configurations. The goal of auto-tuning is the automate the 
process of finding the best performing configuration for a given device.

This kernel tuner aims that you can directly use the tuned kernels 
without introducing any new dependencies. The tuned kernels can 
afterwards be used independently of the programming environment, whether 
that is using C/C++/Java/Fortran or Python doesn't matter.

This module currently only contains one function which is called 
tune_kernel() to which you pass at least the kernel name, a string 
containing the kernel code, the problem size, a list of kernel function 
arguments, and a dictionary of tunable parameters. There are also a lot 
of optional parameters, for a full list see the documentation of 
tune_kernel().

Example usage:
    See the bottom of this file.

Author:
    Ben van Werkhoven <b.vanwerkhoven@esciencenter.nl>

Copyright and License:
    Copyright 2014 Netherlands eScience Center

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import pycuda.driver as drv
from pycuda.autoinit import context
from pycuda.compiler import SourceModule
import numpy
import itertools


def tune_kernel(kernel_name, kernel_string, problem_size, arguments, 
        tune_params, cc=52, grid_div_x=["block_size_x"], grid_div_y=None):
    """ Tune a CUDA kernel given a set of tunable parameters

    Args:
        kernel_name: A string containing the kernel name
        kernel_string: A string containing the CUDA kernel code
        problem_size: A tuple containing the size from which the grid
            dimensions of the kernel will be computed
        arguments: A list of kernel arguments, use numpy arrays for arrays
        tune_params: A dictionary containing the parameter names as keys
            and lists of possible parameter settings as values.
            Currently the kernel tuner uses the convention that the following
            list of tunable parameters are used as compile-time constants
            in the code:
                block_size_x    thread block size x-dimension
                block_size_y    thread block size y-dimension
                block_size_z    thread block size z-dimension
            Options for changing these defaults will be added later.

        cc: compute capability of the CUDA device, 52 by default.
            Could be changed to detect this at runtime.
        grid_div_x: A list of names of the parameters whose values divide
            the grid dimensions in the x-direction, ["block_size_x"] by default
        grid_div_y: A list of names of the parameters whose values divide
            the grid dimensions in the y-direction, empty by default
        
    Returns:
        nothing for the moment it just prints a lot of stuff

    """

    original_kernel = kernel_string

    #move data to GPU
    gpu_args = []
    for i in range(len(arguments)):
        # if arg i is a numpy array copy to device
        if hasattr(arguments[i], "nbytes"):
            gpu_args.append(drv.mem_alloc(arguments[i].nbytes))
            drv.memcpy_htod(gpu_args[i], arguments[i])
        else: # if not an array, just pass argument along
            gpu_args.append(arguments[i])

    #compute cartesian product of all tunable parameters
    for element in itertools.product(*tune_params.values()):
        params = dict(zip(tune_params.keys(), element))

        #thread block size from tunable parameters, current using convention
        block_size_x = params.get("block_size_x", 256)
        block_size_y = params.get("block_size_y", 1)
        block_size_z = params.get("block_size_z", 1)

        #compute thread block and grid dimensions for this kernel
        threads = (block_size_x, block_size_y, block_size_z)
        div_x = numpy.prod([params[i] for i in grid_div_x])
        div_y = 1
        if grid_div_y is not None:
            div_y = numpy.prod([params[i] for i in grid_div_y])
        grid = (int(numpy.ceil(float(problem_size[0]) / float(div_x))),
                int(numpy.ceil(float(problem_size[1]) / float(div_y))) )

        #replace occurrences of the tuning parameters with their current value
        kernel_string = original_kernel
        for k, v in params.iteritems():
            kernel_string = kernel_string.replace(k, str(v))

        #rename the kernel to guarantee that PyCuda compiles a new kernel
        name = kernel_name + "_" + "_".join([str(i) for i in params.values()])
        kernel_string = kernel_string.replace(kernel_name, name)

        #compile kernel func
        func = SourceModule(kernel_string, options=['-Xcompiler=-Wall'],
                    arch='compute_' + str(cc), code='sm_' + str(cc),
                    cache_dir=False).get_function(name)

        #test kernel
        start = drv.Event()
        end = drv.Event()

        context.synchronize()
        start.record()
        func( *gpu_args, block=threads, grid=grid)
        end.record()

        context.synchronize()
        time = end.time_since(start)

        #print the result
        #later we'll save the results and return nice statistics
        print params, kernel_name, "took:", time, " ms."





if __name__ == "__main__":
    """ The following shows a simple example use of the kernel tuner """

    kernel_string = """
    __global__ void vector_add(float *c, float *a, float *b, int n) {
        int i = blockIdx.x * block_size_x + threadIdx.x;
        if (i<n) {
            c[i] = a[i] + b[i];
        }
    }
    """

    size = 10000000
    problem_size = (size, 1)

    a = numpy.random.randn(size).astype(numpy.float32)
    b = numpy.random.randn(size).astype(numpy.float32)
    c = numpy.zeros_like(b)

    args = [c, a, b]

    tune_params = dict()
    tune_params["block_size_x"] = [128+64*i for i in range(15)]

    tune_kernel("vector_add", kernel_string, problem_size, args, tune_params)

