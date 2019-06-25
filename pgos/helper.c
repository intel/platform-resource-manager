// Copyright (C) 2018 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.
//
//
// SPDX-License-Identifier: Apache-2.0
//
#include "helper.h"
#include <string.h>
#include <stdio.h>

void set_attr_disabled(struct perf_event_attr *attr, int disabled) {
	attr->disabled = disabled;
}

struct cgroup* get_cgroup(struct cgroup *cgroups, int index) {
    return cgroups + index;
}

void set_perf_result(struct cgroup *cgroup, int index, uint64_t value) {
	cgroup->perf_result[index] = value;
}

void set_perf_counter_name(struct init_context *ctx, int index, char* name) {
	strncpy((ctx->perf_counter_name)[index], name, strlen(name));
}