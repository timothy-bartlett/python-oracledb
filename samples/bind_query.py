#------------------------------------------------------------------------------
# Copyright (c) 2016, 2022, Oracle and/or its affiliates.
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
# bind_query.py
#
# Demonstrates how to perform a simple query limiting the rows retrieved using
# a bind variable. Since the query that is executed is identical, no additional
# parsing is required, thereby reducing overhead and increasing performance. It
# also permits data to be bound without having to be concerned about escaping
# special characters or SQL injection attacks.
#------------------------------------------------------------------------------

import oracledb
import sample_env

# determine whether to use python-oracledb thin mode or thick mode
if not sample_env.get_is_thin():
    oracledb.init_oracle_client(lib_dir=sample_env.get_oracle_client())

connection = oracledb.connect(sample_env.get_main_connect_string())
cursor = connection.cursor()
sql = 'select * from SampleQueryTab where id = :bvid'

print("Query results with id = 4")
for row in cursor.execute(sql, bvid = 4):
    print(row)
print()

print("Query results with id = 1")
for row in cursor.execute(sql, bvid = 1):
    print(row)
print()
