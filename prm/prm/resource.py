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
""" This module defines general resource control methods """

from enum import Enum
from typing import Union
from wca.allocators import AllocationType, RDTAllocation, TasksAllocations


class RDTResource(str, Enum):
    L3 = 'l3'
    MB = 'mb'


class Resource(object):
    """ Resource Class is abstraction of resource """
    BUGET_LEV_FULL = -1
    BUGET_LEV_MIN = 0
    BUGET_LEV_MAX = 20

    def __init__(self, init_level=BUGET_LEV_MIN, level_max=BUGET_LEV_MAX):
        self.quota_level = init_level
        self.level_max = level_max
        self.cur_allocs: TasksAllocations = dict()
        self.new_allocs: TasksAllocations = dict()

    def set_alloc(
            self, task_id, alloc_type: AllocationType, alloc: Union[float, str],
            rdt_res: RDTResource = None, name: str = None):
        is_new = True
        if task_id in self.cur_allocs and alloc_type in self.cur_allocs[task_id]:
            if alloc_type == AllocationType.RDT:
                val = getattr(self.cur_allocs[task_id][alloc_type], rdt_res)
            else:
                val = self.cur_allocs[task_id][alloc_type]
            if val == alloc:
                is_new = False

        if is_new:
            if task_id in self.new_allocs:
                task_allocs = self.new_allocs[task_id]
            else:
                task_allocs = dict()
                self.new_allocs[task_id] = task_allocs
            if alloc_type == AllocationType.RDT:
                if rdt_res == RDTResource.L3:
                    old_mb = task_allocs.get(AllocationType.RDT, RDTAllocation()).mb
                    task_allocs[alloc_type] = RDTAllocation(
                        name=name,
                        l3=alloc,
                        mb=old_mb
                    )
                else:
                    old_l3 = task_allocs.get(AllocationType.RDT, RDTAllocation()).l3
                    task_allocs[alloc_type] = RDTAllocation(
                        name=name,
                        l3=old_l3,
                        mb=alloc
                    )
            else:
                task_allocs[alloc_type] = alloc

    def is_min_level(self):
        """ is resource controled in lowest level """
        return self.quota_level == Resource.BUGET_LEV_MIN

    def is_full_level(self):
        """ is resource controled in full level """
        return self.quota_level == Resource.BUGET_LEV_FULL

    def set_level(self, level):
        """ set resource in given level """
        self.quota_level = level

    def increase_level(self):
        """ increase resource to next level """
        self.quota_level = self.quota_level + 1
        if self.quota_level == self.level_max:
            self.quota_level = Resource.BUGET_LEV_FULL

    def budgeting(self, bes, lcs):
        """ control resouce based on current resource level """
        pass
