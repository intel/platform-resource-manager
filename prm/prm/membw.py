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

""" This module implements memory bandwidth control based on pqos tool """

from __future__ import print_function

import logging
from prm.resource import Resource, RDTResource
from wca.allocators import AllocationType

log = logging.getLogger(__name__)


class MemoryBw(Resource):
    """ This class is the resource class of memory bandwidth """

    def __init__(self):
        super(MemoryBw, self).__init__()
        self.cur_allocs = None
        self.new_allocs = None

    def update_allocs(self, cur_allocs, new_allocs, min_bandwidth, bandwidth_gran, nsocks):
        self.cur_allocs = cur_allocs
        self.new_allocs = new_allocs
        self.min_bandwidth = min_bandwidth
        self.bandwidth_gran = bandwidth_gran
        self.nsocks = nsocks
        self.level_max = int((100 - self.min_bandwidth) / self.bandwidth_gran)

    def update(self):
        if self.is_full_level():
            self.mb_value = 100
        elif self.is_min_level():
            self.mb_value = self.min_bandwidth
        else:
            self.mb_value = self.min_bandwidth + self.quota_level * self.bandwidth_gran

    def budgeting(self, bes, lcs):
        self.update()
        if bes:
            name = 'BE_Group'
            for cid in bes:
                mbs = [str(idx) + '=' + str(self.mb_value) for idx in range(self.nsocks)]
                mb_allocs = 'MB:' + ';'.join(mbs)
                self.set_alloc(cid, AllocationType.RDT, mb_allocs, RDTResource.MB, name)
