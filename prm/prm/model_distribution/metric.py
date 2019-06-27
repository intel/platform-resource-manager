# Copyright (C) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.
#
#
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
from collections import namedtuple


class GroupInfo(str, Enum):
    CPU_MODEL = "cpu_model"
    INITIAL_TASK_CPU_ASSIGNMENT = "initial_task_cpu_assignment"
    APPLICATION = "application"
    APPLICATION_VERSION_NAME = "application_version_name"

class Metric(str, Enum):

    CYC = 'cycle'
    INST = 'instruction'
    L3MISS = 'cache_miss'
    L3OCC = 'cache_occupancy'
    MB = 'memory_bandwidth_total'
    MBL = 'memory_bandwidth_local'
    MBR = 'memory_bandwidth_remote'
    CPI = 'cycles_per_instruction'
    L3MPKI = 'cache_miss_per_kilo_instruction'
    NF = 'normalized_frequency'
    UTIL = 'cpu_utilization'
    L2STALL = 'stalls_l2_miss'
    MEMSTALL = 'stalls_mem_load'
    L2SPKI = 'stalls_l2miss_per_kilo_instruction'
    MSPKI = 'stalls_memory_load_per_kilo_instruction'
    LCCAPACITY = 'latency_critical_utilization_capacity'
    LCMAX = 'latency_critical_utilization_max'
    SYSUTIL = 'system_utilization'
    NAME = 'name'
    CPU_MODEL = 'cpu_model'
    VCPU_COUNT = 'vcpu_count'

GroupLabel = namedtuple(
    'GroupLabel', ["cpu_model", "application", "initial_task_cpu_assignment"])


