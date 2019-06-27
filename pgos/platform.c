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

#include <unistd.h>
#include <cpuid.h>
#include <asm/unistd.h>
#include <stdint.h>
#include <errno.h>
#include "platform.h"

int UNKNOWN = 0;
int BROADWELL = 1;
int SKYLAKE = 2;
int CASCADELAKE = 3;

int get_cpu_family() {
	uint32_t eax, ebx, ecx, edx;
	__cpuid(1, eax, ebx, ecx, edx);
	const uint32_t model = (eax >> 4) & 0xF;
	const uint32_t family = (eax >> 8) & 0xF;
	const uint32_t extended_model = (eax >> 16) & 0xF;
	const uint32_t extended_family = (eax >> 20) & 0xFF;
	uint32_t display_family = family;
	if (family == 0xF) {
		display_family += extended_family;
	}
	uint32_t display_model = model;
	if ((family == 0x6) || (family == 0xF)) {
		display_model += extended_model << 4;
	}
	if (display_family == 0x06) {
		switch (display_model) {
			case 0x4E:
			case 0x5E:
			case 0x55:
				return SKYLAKE;
			case 0x3D:
			case 0x47:
			case 0x4F:
			case 0x56:
				return BROADWELL;
		}
	}
	return UNKNOWN;
}