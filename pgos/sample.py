#! /usr/bin/python

# Copyright (c) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# SPDX-License-Identifier: Apache-2.0
#
from ctypes import *

class cgroup(Structure):
    _fields_ = [("ret", c_int),
                ("path", c_char_p), 
                ("cid", c_char_p), 
                ("perf_result", POINTER(c_ulonglong)),
                ("llc_occupancy", c_ulonglong),
                ("mbm_local", c_double),
                ("mbm_remote", c_double)]

class context(Structure):
    _fields_ = [("ret", c_int),
                ("core", c_int),
                ("period", c_int),
                ("cgroup_count", c_int),
                ("timestamp", c_ulonglong),
                ("cgroups", POINTER(cgroup)),
                ("perf_counter_count", c_int),
                ("perf_counter_name", POINTER(c_char_p))]

class init_context(Structure):
    _fields_ = [("path", c_char_p),
                ("perf_counter_count", POINTER(c_int)),
                ("perf_counter_name", POINTER(c_char_p))]

lib = cdll.LoadLibrary('./libpgos.so')
lib.pgos_collect.argtypes = [context]
lib.pgos_collect.restype = context


cg0 = cgroup()
cg0.path = '/sys/fs/cgroup/perf_event/docker/71546547af31a748be4de938b70131d7375ac452dd0cc1099109d3070605aae2/'.encode()
cg0.cid = 'memcached'.encode()
cg0.perf_result = (c_ulonglong * 6)(0, 0, 0, 0, 0, 0)

ctx = context()
ctx.core = 22
ctx.period = 20000
ctx.cgroup_count = 1
ctx.cgroups = (cgroup * 1)(cg0)


init_ctx = init_context()
#init_ctx.path = "counters.json" // you can use your customized json file instead of skylake.json or broadwell.json
init_ctx.perf_counter_name = (c_char_p * 20)()
init_ctx.perf_counter_count = (c_int * 1)(0)
for i in range (0, 20):
    init_ctx.perf_counter_name[i] = bytearray(64).decode()

ret = lib.pgos_init(init_ctx)

counter_count = init_ctx.perf_counter_count[0]
print (counter_count)
for i in range(counter_count):
    print (init_ctx.perf_counter_name[i])

for i in range(1):
    ret = lib.pgos_collect(ctx)
    cg = ret.cgroups[0]
    for j in range(counter_count):
        print(cg.perf_result[j])
    print(cg.llc_occupancy, cg.mbm_local, cg.mbm_remote)

lib.pgos_finalize()