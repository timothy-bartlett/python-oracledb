#------------------------------------------------------------------------------
# Copyright (c) 2020, 2024, Oracle and/or its affiliates.
#
# This software is dual-licensed to you under the Universal Permissive License
# (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl and Apache License
# 2.0 as shown at http://www.apache.org/licenses/LICENSE-2.0. You may choose
# either license.
#
# If you elect to accept the software under the Apache License, Version 2.0,
# the following applies:
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# base_impl.pyx
#
# Cython file for the base implementation that the thin and thick
# implementations use.
#------------------------------------------------------------------------------

# cython: language_level=3

cimport cython
cimport cpython
cimport cpython.datetime as cydatetime

from libc.stdint cimport int8_t, int16_t, int32_t, int64_t
from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t
from libc.stdint cimport UINT8_MAX, UINT16_MAX, UINT32_MAX, UINT64_MAX
from libc.string cimport memcpy
from cpython cimport array

import array

import base64
import datetime
import decimal
import inspect
import json
import os
import random
import re
import secrets
import sys

cydatetime.import_datetime()

include "impl/base/types.pyx"

from . import constants, errors, exceptions, utils

cdef type PY_TYPE_ASYNC_CURSOR
cdef type PY_TYPE_ASYNC_LOB
cdef type PY_TYPE_BOOL = bool
cdef type PY_TYPE_CURSOR
cdef type PY_TYPE_DATE = datetime.date
cdef type PY_TYPE_DATETIME = datetime.datetime
cdef type PY_TYPE_DECIMAL = decimal.Decimal
cdef type PY_TYPE_DB_OBJECT
cdef type PY_TYPE_DB_OBJECT_TYPE
cdef type PY_TYPE_JSON_ID
cdef type PY_TYPE_LOB
cdef type PY_TYPE_TIMEDELTA = datetime.timedelta
cdef type PY_TYPE_VAR
cdef type PY_TYPE_FETCHINFO

# purity values
cdef uint32_t PURITY_NEW = constants.PURITY_NEW
cdef uint32_t PURITY_SELF = constants.PURITY_SELF
cdef uint32_t PURITY_DEFAULT = constants.PURITY_DEFAULT

# vector types
cdef uint8_t VECTOR_FORMAT_FLOAT32 = constants.VECTOR_FORMAT_FLOAT32
cdef uint8_t VECTOR_FORMAT_FLOAT64 = constants.VECTOR_FORMAT_FLOAT64
cdef uint8_t VECTOR_FORMAT_INT8 = constants.VECTOR_FORMAT_INT8

cdef const char* ENCODING_UTF8 = "UTF-8"
cdef const char* ENCODING_UTF16 = "UTF-16BE"

cdef int get_preferred_num_type(int16_t precision, int8_t scale):
    if scale == 0 or (scale == -127 and precision == 0):
        return NUM_TYPE_INT
    return NUM_TYPE_FLOAT


include "impl/base/constants.pxi"
include "impl/base/defaults.pyx"
include "impl/base/utils.pyx"
include "impl/base/buffer.pyx"
include "impl/base/oson.pyx"
include "impl/base/vector.pyx"
include "impl/base/connect_params.pyx"
include "impl/base/pool_params.pyx"
include "impl/base/connection.pyx"
include "impl/base/pool.pyx"
include "impl/base/cursor.pyx"
include "impl/base/var.pyx"
include "impl/base/bind_var.pyx"
include "impl/base/dbobject.pyx"
include "impl/base/lob.pyx"
include "impl/base/soda.pyx"
include "impl/base/queue.pyx"
include "impl/base/subscr.pyx"
