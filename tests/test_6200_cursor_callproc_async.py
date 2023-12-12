# -----------------------------------------------------------------------------
# Copyright (c) 2023, Oracle and/or its affiliates.
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
# -----------------------------------------------------------------------------

"""
6200 - Module for testing the methods for calling stored procedures and
functions (callproc() and callfunc()) with asyncio
"""

import unittest

import oracledb
import test_env


@unittest.skipUnless(
    test_env.get_is_thin(), "asyncio not supported in thick mode"
)
class TestCase(test_env.BaseAsyncTestCase):
    async def test_6200_callproc(self):
        "6200 - test executing a stored procedure"
        var = self.cursor.var(oracledb.NUMBER)
        results = await self.cursor.callproc("proc_Test", ("hi", 5, var))
        self.assertEqual(results, ["hi", 10, 2.0])

    async def test_6201_callproc_all_keywords(self):
        "6201 - test executing a stored procedure with all args keyword args"
        inout_value = self.cursor.var(oracledb.NUMBER)
        inout_value.setvalue(0, 5)
        out_value = self.cursor.var(oracledb.NUMBER)
        kwargs = dict(
            a_InOutValue=inout_value, a_InValue="hi", a_OutValue=out_value
        )
        results = await self.cursor.callproc("proc_Test", [], kwargs)
        self.assertEqual(results, [])
        self.assertEqual(inout_value.getvalue(), 10)
        self.assertEqual(out_value.getvalue(), 2.0)

    async def test_6202_callproc_only_last_keyword(self):
        "6202 - test executing a stored procedure with last arg as keyword arg"
        out_value = self.cursor.var(oracledb.NUMBER)
        kwargs = dict(a_OutValue=out_value)
        results = await self.cursor.callproc("proc_Test", ("hi", 5), kwargs)
        self.assertEqual(results, ["hi", 10])
        self.assertEqual(out_value.getvalue(), 2.0)

    async def test_6203_callproc_repeated_keyword_parameters(self):
        "6203 - test executing a stored procedure, repeated keyword arg"
        kwargs = dict(
            a_InValue="hi", a_OutValue=self.cursor.var(oracledb.NUMBER)
        )
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-06550:"):
            await self.cursor.callproc("proc_Test", ("hi", 5), kwargs)

    async def test_6204_callproc_no_args(self):
        "6204 - test executing a stored procedure without any arguments"
        results = await self.cursor.callproc("proc_TestNoArgs")
        self.assertEqual(results, [])

    async def test_6205_callfunc(self):
        "6205 - test executing a stored function"
        results = await self.cursor.callfunc(
            "func_Test", oracledb.NUMBER, ("hi", 5)
        )
        self.assertEqual(results, 7)

    async def test_6206_callfunc_no_args(self):
        "6206 - test executing a stored function without any arguments"
        results = await self.cursor.callfunc(
            "func_TestNoArgs", oracledb.NUMBER
        )
        self.assertEqual(results, 712)

    async def test_6207_callfunc_negative(self):
        "6207 - test executing a stored function with wrong parameters"
        func_name = "func_Test"
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2007:"):
            await self.cursor.callfunc(oracledb.NUMBER, func_name, ("hi", 5))
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-06550:"):
            await self.cursor.callfunc(
                func_name, oracledb.NUMBER, ("hi", 5, 7)
            )
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2012:"):
            await self.cursor.callfunc(func_name, oracledb.NUMBER, "hi", 7)
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-06502:"):
            await self.cursor.callfunc(func_name, oracledb.NUMBER, [5, "hi"])
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-06550:"):
            await self.cursor.callfunc(func_name, oracledb.NUMBER)
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2012:"):
            await self.cursor.callfunc(func_name, oracledb.NUMBER, 5)

    async def test_6208_keyword_args_with_invalid_type(self):
        "6208 - test error for keyword args with invalid type"
        kwargs = [5]
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2013:"):
            await self.cursor.callproc("proc_Test", [], kwargs)
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2013:"):
            await self.cursor.callfunc(
                "func_Test", oracledb.NUMBER, [], kwargs
            )


if __name__ == "__main__":
    test_env.run_test_cases()
