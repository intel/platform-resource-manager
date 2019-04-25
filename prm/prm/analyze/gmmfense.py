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

""" This module implements build fense based on GMM model """

import logging
import math
import numpy as np
from sklearn import mixture

log = logging.getLogger(__name__)


class GmmFense:
    """ This class implements GMM fense build and related retrieve methods """

    def __init__(self, data, max_mixture=10, threshold=0.1):
        """
        Class constructor, arguments include:
            data - data to build GMM model
            max_mixture - max number of Gaussian mixtures
            threshold - probability threhold to determine fense
        """
        self.data = data
        self.thresh = threshold
        lowest_bic = np.infty
        components = 1
        bic = []
        n_components_range = range(1, max_mixture + 1)
        for n_components in n_components_range:
            # Fit a Gaussian mixture with EM
            gmm = mixture.GaussianMixture(n_components=n_components,
                                          random_state=1005)
            gmm.fit(data)
            bic.append(gmm.bic(data))
            if bic[-1] < lowest_bic:
                lowest_bic = bic[-1]
                best_gmm = gmm
                components = n_components
        log.debug('best gmm components number: %d, bic %f ', components, lowest_bic)
        self.gmm = best_gmm

    def __get_fense(self, is_upper, span=3):
        """
        Get fense turple based on predefined probability threshold
            is_upper - True if upper fense is needed,
                        False if lower fense is needed
            span - how many sigma span for normal fense
        """
        if is_upper:
            sdata = np.sort(self.data, axis=0)[::-1]
        else:
            sdata = np.sort(self.data, axis=0)

        clusters = self.gmm.predict(sdata)
        probs = self.gmm.weights_
        prob = 0
        indexset = set()
        for i in range(0, len(clusters)):
            index = clusters[i]
            if index not in indexset:
                indexset.add(index)
                prob = prob + probs[index]
                if prob > self.thresh:
                    mean = self.gmm.means_[index][0]
                    var = self.gmm.covariances_[index][0]
                    std = math.sqrt(var)
                    val = sdata[i][0]
                    if is_upper:
                        normal = mean + std * span
                    else:
                        normal = mean - std * span

                    log.debug('strict value: %f mean: %f std: %f', val,
                              mean, std)
                    return (val, normal)

    def get_normal_fense(self, is_upper, span=3):
        """
        Get fense normal threshold
            is_upper - True if upper fense is needed,
                        False if lower fense is needed
            span - how many sigma span for normal fense
        """
        fense = self.__get_fense(is_upper, span)
        return fense[1]

    def get_strict_fense(self, is_upper, span=3):
        """
        Get fense strict threshold
            is_upper - True if upper fense is needed,
                        False if lower fense is needed
            span - how many sigma span for normal fense
        """
        strict, normal = self.__get_fense(is_upper, span)
        if is_upper:
            if normal < strict:
                return normal
            return strict
        else:
            if normal > strict:
                return normal
            return strict
    
    def get_gaussian_round_fense(self, is_upper, is_strict, span=3):
        """
        Get threshold by looing into each gaussian
            is_upper - If True, upper fense is returned
            is_strict - If True, use min(3_std_threshold, max(data))
                        If False, always 3_std_threshold
            span - how many sigma span for normal fense
        """
        index_sort_means = np.argsort(self.gmm.means_, axis=0)
        labels = self.gmm.predict(self.data)

        if is_upper is True:
                index_sort_means = np.flipud(index_sort_means)

        last_threshold = -1.0
        last_percentage = -1.0
        total = float(self.data.shape[0])
        
        threshold = -1.0

        for i in index_sort_means:
            gaussian_index = i[0]
            #print(mixture_index, self.gmm.means_[mixture_index][0], math.sqrt(self.gmm.covariances_[mixture_index][0]), self.gmm.weights_[mixture_index])
            #print((labels == i).sum())

            gaussian_data = np.take(self.data, axis=0, indices=np.where(labels == gaussian_index))
            mean = self.gmm.means_[gaussian_index][0]
            std = math.sqrt(self.gmm.covariances_[gaussian_index][0])

            if is_upper is True:
                data_bar = np.amax(gaussian_data)
                three_std_bar = mean + span * std
                if is_strict is True:
                    threshold = three_std_bar if three_std_bar < data_bar else data_bar
                outlier_count = (self.data > threshold).sum()
            else:
                data_bar = np.amin(gaussian_data)
                three_std_bar = mean - span * std
                if is_strict is True:
                    threshold = three_std_bar if three_std_bar > data_bar else data_bar
                outlier_count = (self.data < threshold).sum()

            percentage = float(outlier_count) / total
            
            if percentage > self.thresh:
                if last_threshold != -1:
                    if np.abs(last_percentage - self.thresh) < np.abs(percentage - self.thresh):
                        threshold = last_threshold
                break
            else:
                last_threshold = threshold
                last_percentage = percentage


        return threshold
