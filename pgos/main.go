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

package main

// #cgo CFLAGS: -fstack-protector-strong
// #cgo CFLAGS: -fPIE -fPIC
// #cgo CFLAGS: -O2 -D_FORTIFY_SOURCE=2
// #cgo CFLAGS: -Wformat -Wformat-security
// #cgo LDFLAGS: -lpqos -lm ./platform.o ./pgos.o ./helper.o
// #cgo LDFLAGS: -Wl,-z,noexecstack
// #cgo LDFLAGS: -Wl,-z,relro
// #cgo LDFLAGS: -Wl,-z,now
import "C"

func main() {

}
