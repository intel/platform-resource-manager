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

CFLAGS = -fstack-protector-strong -fPIE -fPIC -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security

libpgos.so: platform.o helper.o pgos.o
	CGO_LDFLAGS_ALLOW="(-Wl,-z,now|\./.*\.o)" go build -a -buildmode=c-shared -o libpgos.so *.go
platform.o:
	gcc $(CFLAGS) -c -o platform.o platform.c
helper.o:
	gcc $(CFLAGS) -c -o helper.o helper.c
pgos.o:
	gcc $(CFLAGS) -c -o pgos.o pgos.c
clean:
	rm ./libpgos.so ./*.o