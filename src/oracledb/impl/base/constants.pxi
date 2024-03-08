#------------------------------------------------------------------------------
# Copyright (c) 2024, Oracle and/or its affiliates.
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
# constants.pxi
#
# Cython file defining constants used by the base implementation classes
# (embedded in base_impl.pyx).
#------------------------------------------------------------------------------

# base JSON constants
cdef enum:
    TNS_JSON_MAGIC_BYTE_1 = 0xff
    TNS_JSON_MAGIC_BYTE_2 = 0x4a        # 'J'
    TNS_JSON_MAGIC_BYTE_3 = 0x5a        # 'Z'
    TNS_JSON_VERSION_MAX_FNAME_255 = 1
    TNS_JSON_VERSION_MAX_FNAME_65535 = 3
    TNS_JSON_FLAG_HASH_ID_UINT8 = 0x0100
    TNS_JSON_FLAG_NUM_FNAMES_UINT16 = 0x0400
    TNS_JSON_FLAG_FNAMES_SEG_UINT32 = 0x0800
    TNS_JSON_FLAG_TINY_NODES_STAT = 0x2000
    TNS_JSON_FLAG_TREE_SEG_UINT32 = 0x1000
    TNS_JSON_FLAG_REL_OFFSET_MODE = 0x01
    TNS_JSON_FLAG_INLINE_LEAF = 0x02
    TNS_JSON_FLAG_LEN_IN_PCODE = 0x04
    TNS_JSON_FLAG_NUM_FNAMES_UINT32 = 0x08
    TNS_JSON_FLAG_IS_SCALAR = 0x10
    TNS_JSON_FLAG_SEC_FNAMES_SEG_UINT16 = 0x0100

# JSON data types
cdef enum:
    TNS_JSON_TYPE_NULL = 0x30
    TNS_JSON_TYPE_TRUE = 0x31
    TNS_JSON_TYPE_FALSE = 0x32
    TNS_JSON_TYPE_STRING_LENGTH_UINT8 = 0x33
    TNS_JSON_TYPE_NUMBER_LENGTH_UINT8 = 0x34
    TNS_JSON_TYPE_BINARY_DOUBLE = 0x36
    TNS_JSON_TYPE_STRING_LENGTH_UINT16 = 0x37
    TNS_JSON_TYPE_STRING_LENGTH_UINT32 = 0x38
    TNS_JSON_TYPE_TIMESTAMP = 0x39
    TNS_JSON_TYPE_BINARY_LENGTH_UINT16 = 0x3a
    TNS_JSON_TYPE_BINARY_LENGTH_UINT32 = 0x3b
    TNS_JSON_TYPE_DATE = 0x3c
    TNS_JSON_TYPE_INTERVAL_YM = 0x3d
    TNS_JSON_TYPE_INTERVAL_DS = 0x3e
    TNS_JSON_TYPE_TIMESTAMP_TZ = 0x7c
    TNS_JSON_TYPE_TIMESTAMP7 = 0x7d
    TNS_JSON_TYPE_ID = 0x7e
    TNS_JSON_TYPE_BINARY_FLOAT = 0x7f
    TNS_JSON_TYPE_OBJECT = 0x84
    TNS_JSON_TYPE_ARRAY = 0xc0
    TNS_JSON_TYPE_EXTENDED = 0x7b
    TNS_JSON_TYPE_VECTOR = 0x01

# VECTOR constants
cdef enum:
    TNS_VECTOR_MAGIC_BYTE = 0xDB
    TNS_VECTOR_VERSION = 0

# VECTOR flags
cdef enum:
    TNS_VECTOR_FLAG_DIM_UINT8 = 0x0001
    TNS_VECTOR_FLAG_DIM_UINT32 = 0x0002
    TNS_VECTOR_FLAG_NORM = 0x0008
    TNS_VECTOR_FLAG_NORM_RESERVED = 0x0040

# general constants
cdef enum:
    TNS_MAX_SHORT_LENGTH = 252
    TNS_DURATION_MID = 0x80000000
    TNS_DURATION_OFFSET = 60
    TNS_CHUNK_SIZE = 32767
    TNS_HAS_REGION_ID = 0x80

# timezone offsets
cdef enum:
    TZ_HOUR_OFFSET = 20
    TZ_MINUTE_OFFSET = 60
