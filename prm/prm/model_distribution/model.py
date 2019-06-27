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

import logging
from enum import Enum
import numpy as np
from scipy import stats
from prm.model_distribution.metric import GroupInfo, Metric
from prm.analyze.gmmfense import GmmFense
from typing import Optional, List, Union

log = logging.getLogger(__name__)


class DistriModel(object):
    """Building thresholds for platform metrics.
    Arguments:
        span: how many sigma span for normal fense
            (default to 4)
        strict: if true, pick less aggressive value from 3_std_threshold or extreme gaussian value),If False, always 3_std_threshold
            (default to true)
        use_origin: using origin or not
            (default to false)
        verbose: enable verbose output
            (default to false)
    """

    UTIL_BIN_STEP = 50

    def __init__(self,
                 span: Optional[int] = 3,
                 strict: Optional[bool] = True,
                 use_origin: Optional[bool] = False,
                 verbose: Optional[bool] = False,
                 ):
        self.span = 3 if span is None else span
        self.strict = True if span is None else strict
        self.use_origin = False if use_origin is None else use_origin
        self.verbose = False if verbose is None else verbose

    def partition_utilization(self, cpu_number, step=UTIL_BIN_STEP):
        """
        Partition utilizaton bins based on requested CPU number and step count
            cpu_number - processor count assigned to workload
            step - bin range of one partition, default value is half processor
        """
        utilization_upper = (cpu_number + 1) * 100
        utilization_lower = cpu_number * 50

        utilization_bar = np.arange(utilization_lower, utilization_upper, step)

        return utilization_bar

    def _build_tdp_thresh(self, cpu_number, jdata):

        utilization_threshold = float(cpu_number) * 100 * 0.95
        tdp_data = jdata[jdata[Metric.UTIL] >= utilization_threshold]
        util = tdp_data[Metric.UTIL]
        freq = tdp_data[Metric.NF]

        tdp_thresh = {}

        if not util.empty:
            mean, std = stats.norm.fit(freq)

            min_freq = min(freq)
            fbar = mean - 3 * std
            if min_freq < fbar:
                fbar = min_freq
            tdp_thresh = {
                'util': utilization_threshold,
                'mean': mean.item(),
                'std': std.item(),
                'bar': np.float64(fbar).item()
            }
        return tdp_thresh

    def _get_fense_origin(self, mdf, is_upper, strict, span):
        gmm_fense = GmmFense(mdf.values.reshape(-1, 1))
        if strict:
            return gmm_fense.get_strict_fense(is_upper, span)

        return gmm_fense.get_normal_fense(is_upper, span)

    def _get_fense(self, mdf, is_upper, strict, span, use_origin):
        if use_origin is True:
            return self._get_fense_origin(mdf, is_upper, strict, span)

        gmm_fense = GmmFense(mdf.values.reshape(-1, 1))

        return gmm_fense.get_gaussian_round_fense(is_upper, strict, span)

    def _build_thresh(self, cpu_number, jdata, span, strict, use_origin, verbose):
        utilization_partition = self.partition_utilization(
            cpu_number, self.UTIL_BIN_STEP)

        length = len(utilization_partition)
        thresholds = []
        for index, util in enumerate(utilization_partition):
            lower_bound = util
            if index != length - 1:
                higher_bound = utilization_partition[index + 1]
            else:
                higher_bound = lower_bound + self.UTIL_BIN_STEP
            try:
                jdataf = jdata[(jdata[Metric.UTIL] >= lower_bound) &
                               (jdata[Metric.UTIL] <= higher_bound)]
                cpi = jdataf[Metric.CPI]
                cpi_thresh = self._get_fense(cpi, True, strict,
                                             span, use_origin)
                mpki = jdataf[Metric.L3MPKI]
                mpki_thresh = self._get_fense(mpki, True, strict,
                                              span, use_origin)
                memb = jdataf[Metric.MB]
                mb_thresh = self._get_fense(memb, False, strict,
                                            span, use_origin)
                thresh = {
                    'util_start': lower_bound.item(),
                    'util_end': higher_bound.item(),
                    'cpi': np.float64(cpi_thresh).item(),
                    'mpki': np.float64(mpki_thresh).item(),
                    'mb': np.float64(mb_thresh).item()
                }
                mspki = jdataf[Metric.MSPKI]
                mspki_thresh = self._get_fense(mspki, True, strict,span, use_origin)
                thresh['mspki'] = np.float64(mspki_thresh).item()
                thresholds.append(thresh)

            except Exception as e:
                if verbose:
                    log.exception('error in build threshold util= (%r)', util)
        return thresholds

    def build_model(self, dataframe, cpu_number):
        tdp_thresh = self._build_tdp_thresh(cpu_number, dataframe)
        thresholds = self._build_thresh(
            cpu_number, dataframe, self.span, self.strict, self.use_origin, self.verbose)

        return tdp_thresh, thresholds

