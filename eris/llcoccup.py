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

""" This module implements last level cache control based on pqos tool """

from __future__ import print_function

import subprocess
from datetime import datetime
from mresource import Resource


class LlcOccup(Resource):
    """ This class is the resource class of LLC occupancy """

    def __init__(self, init_level, exclusive):
        bitcnt = LlcOccup._get_cbm_bit_count()
        self.be_bmp = [hex(((1 << (i + 1)) - 1) << (bitcnt - 1 - i))
                       for i in range(1, bitcnt)]
        self.lc_bmp = [hex((1 << (bitcnt - 1 - i)) - 1)
                       for i in range(1, bitcnt)]
        if exclusive:
            self.be_bmp = self.be_bmp[0:int(bitcnt / 2)]
            self.lc_bmp = self.lc_bmp[0:int(bitcnt / 2)]
        super(LlcOccup, self).__init__(init_level, int(bitcnt / 2) if
                                       exclusive else bitcnt - 1)

    @staticmethod
    def _get_cbm_bit_count():
        with open('/sys/fs/resctrl/info/L3/cbm_mask') as cbmf:
            cbm_mask = cbmf.readline()
            cbm = int(cbm_mask, 16)
            cbm_bin = bin(cbm)
            setbits = [bit for bit in cbm_bin[2:] if bit == '1']
            return len(setbits)

    def _budgeting(self, containers, clsid, is_be):
        cpids = []
        cns = []
        for con in containers:
            cpids.append(','.join(con.pids))
            cns.append(con.name)

        bmp = self.be_bmp if is_be else self.lc_bmp
        cml = 'pqos -I -a' + '\'pid:' + clsid + '=' + ','.join(cpids) + '\''
        subprocess.Popen(cml, shell=True)

        cml = 'pqos -e' + '\'llc:' + clsid + '=' + bmp[self.quota_level] + '\''
        subprocess.Popen(cml, shell=True)

        print(datetime.now().isoformat(' ') + ' set container ' +
              ','.join(cns) + ' llc occupancy to ' + bmp[self.quota_level])

    def budgeting(self, bes, lcs):
        if bes:
            self._budgeting(bes, '1', True)
        if lcs:
            self._budgeting(lcs, '2', False)
