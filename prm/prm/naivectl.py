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

""" This module implements a simple resource controller """

from prm.resource import Resource


class NaiveController:
    """ This class implement a naive control logic against BE workloads """

    def __init__(self, res, cyc_thresh=3):
        self.res = res
        self.cyc_thresh = cyc_thresh
        self.cyc_cnt = 0

    def update(self, bes, lcs, detected, hold):
        """
        Update contention detection result to controller, controller conducts
        control policy on BE workloads based on current contention status
            bes - all BE workload containers ids
            lcs - all LC workload containers ids
            detected - if resource contention detected on LC workloads
            hold - if current resource level need to be maintained
        """

        if detected:
            self.cyc_cnt = 0
            # always throttle BE to minimal
            self.res.set_level(Resource.BUGET_LEV_MIN)
            self.res.budgeting(bes, lcs)
        else:
            if hold or self.res.is_full_level():
                # no contention, pass
                pass
            else:
                # increase cycle count, adjust budget if step count is reached
                self.cyc_cnt = self.cyc_cnt + 1
                if self.cyc_cnt >= self.cyc_thresh:
                    self.cyc_cnt = 0
                    self.res.increase_level()
                    self.res.budgeting(bes, lcs)
