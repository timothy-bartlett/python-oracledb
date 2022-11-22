#------------------------------------------------------------------------------
# Copyright (c) 2020, 2022, Oracle and/or its affiliates.
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

"""
1600 - Module for testing DML returning clauses
"""

import datetime
import unittest

import oracledb
import test_env

class TestCase(test_env.BaseTestCase):

    def test_1600_insert(self):
        "1600 - test insert (single row) with DML returning"
        self.cursor.execute("truncate table TestTempTable")
        int_val = 5
        str_val = "A test string"
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str)
        self.cursor.execute("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:int_val, :str_val)
                returning IntCol, StringCol1 into :int_var, :str_var""",
                int_val=int_val,
                str_val=str_val,
                int_var=int_var,
                str_var=str_var)
        self.assertEqual(int_var.values, [[int_val]])
        self.assertEqual(str_var.values, [[str_val]])

    def test_1601_insert_many(self):
        "1601 - test insert (multiple rows) with DML returning"
        self.cursor.execute("truncate table TestTempTable")
        int_values = [5, 8, 17, 24, 6]
        str_values = ["Test 5", "Test 8", "Test 17", "Test 24", "Test 6"]
        int_var = self.cursor.var(oracledb.NUMBER, arraysize=len(int_values))
        str_var = self.cursor.var(str, arraysize=len(int_values))
        self.cursor.setinputsizes(None, None, int_var, str_var)
        data = list(zip(int_values, str_values))
        self.cursor.executemany("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:int_val, :str_val)
                returning IntCol, StringCol1 into :int_var, :str_var""", data)
        self.assertEqual(int_var.values, [[v] for v in int_values])
        self.assertEqual(str_var.values, [[v] for v in str_values])

    def test_1602_insert_with_small_size(self):
        "1602 - test insert with DML returning into too small a variable"
        self.cursor.execute("truncate table TestTempTable")
        int_val = 6
        str_val = "A different test string"
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str, 2)
        parameters = dict(int_val=int_val, str_val=str_val, int_var=int_var,
                          str_var=str_var)
        self.assertRaisesRegex(oracledb.DatabaseError, "^DPY-4002:|^DPI-1037:",
                self.cursor.execute, """
                insert into TestTempTable (IntCol, StringCol1)
                values (:int_val, :str_val)
                returning IntCol, StringCol1 into :int_var, :str_var""",
                parameters)

    def test_1603_update_single_row(self):
        "1603 - test update single row with DML returning"
        int_val = 7
        str_val = "The updated value of the string"
        self.cursor.execute("truncate table TestTempTable")
        self.cursor.execute("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)""",
                (int_val, "The initial value of the string"))
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str)
        self.cursor.execute("""
                update TestTempTable set
                    StringCol1 = :str_val
                where IntCol = :int_val
                returning IntCol, StringCol1 into :int_var, :str_var""",
                int_val=int_val,
                str_val=str_val,
                int_var=int_var,
                str_var=str_var)
        self.assertEqual(int_var.values, [[int_val]])
        self.assertEqual(str_var.values, [[str_val]])

    def test_1604_update_no_rows(self):
        "1604 - test update no rows with DML returning"
        int_val = 8
        str_val = "The updated value of the string"
        self.cursor.execute("truncate table TestTempTable")
        self.cursor.execute("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)""",
                (int_val, "The initial value of the string"))
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str)
        self.cursor.execute("""
                update TestTempTable set
                    StringCol1 = :str_val
                where IntCol = :int_val
                returning IntCol, StringCol1 into :int_var, :str_var""",
                int_val=int_val + 1,
                str_val=str_val,
                int_var=int_var,
                str_var=str_var)
        self.assertEqual(int_var.values, [[]])
        self.assertEqual(str_var.values, [[]])
        self.assertEqual(int_var.getvalue(), [])
        self.assertEqual(str_var.getvalue(), [])

    def test_1605_update_multiple_rows(self):
        "1605 - test update multiple rows with DML returning"
        self.cursor.execute("truncate table TestTempTable")
        for i in (8, 9, 10):
            self.cursor.execute("""
                    insert into TestTempTable (IntCol, StringCol1)
                    values (:1, :2)""",
                    (i, "The initial value of string %d" % i))
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str)
        self.cursor.execute("""
                update TestTempTable set
                    IntCol = IntCol + 15,
                    StringCol1 = 'The final value of string ' || to_char(IntCol)
                returning IntCol, StringCol1 into :int_var, :str_var""",
                int_var=int_var,
                str_var=str_var)
        self.assertEqual(self.cursor.rowcount, 3)
        self.assertEqual(int_var.values, [[23, 24, 25]])
        expected_values = [[
            "The final value of string 8",
            "The final value of string 9",
            "The final value of string 10"
        ]]
        self.assertEqual(str_var.values, expected_values)

    def test_1606_update_multiple_rows_executemany(self):
        "1606 - test update multiple rows with DML returning (executemany)"
        data = [(i, "The initial value of string %d" % i) \
                for i in range(1, 11)]
        self.cursor.execute("truncate table TestTempTable")
        self.cursor.executemany("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)""", data)
        int_var = self.cursor.var(oracledb.NUMBER, arraysize=3)
        str_var = self.cursor.var(str, arraysize=3)
        self.cursor.setinputsizes(None, int_var, str_var)
        self.cursor.executemany("""
                update TestTempTable set
                    IntCol = IntCol + 25,
                    StringCol1 = 'Updated value of string ' || to_char(IntCol)
                where IntCol < :inVal
                returning IntCol, StringCol1 into :int_var, :str_var""",
                [[3], [8], [11]])
        expected_values = [
            [26, 27],
            [28, 29, 30, 31, 32],
            [33, 34, 35]
        ]
        self.assertEqual(int_var.values, expected_values)
        expected_values = [
            [
                "Updated value of string 1",
                "Updated value of string 2"
            ],
            [
                "Updated value of string 3",
                "Updated value of string 4",
                "Updated value of string 5",
                "Updated value of string 6",
                "Updated value of string 7"
            ],
            [
                "Updated value of string 8",
                "Updated value of string 9",
                "Updated value of string 10"
            ]
        ]
        self.assertEqual(str_var.values, expected_values)

    def test_1607_insert_and_return_object(self):
        "1607 - test inserting an object with DML returning"
        type_obj = self.connection.gettype("UDT_OBJECT")
        string_value = "The string that will be verified"
        obj = type_obj.newobject()
        obj.STRINGVALUE = string_value
        out_var = self.cursor.var(oracledb.DB_TYPE_OBJECT,
                                  typename="UDT_OBJECT")
        self.cursor.execute("""
                insert into TestObjects (IntCol, ObjectCol)
                values (4, :obj)returning ObjectCol into :outObj""",
                obj=obj, outObj=out_var)
        result, = out_var.getvalue()
        self.assertEqual(result.STRINGVALUE, string_value)
        self.connection.rollback()

    def test_1608_insert_and_return_rowid(self):
        "1608 - test inserting a row and returning a rowid"
        self.cursor.execute("truncate table TestTempTable")
        var = self.cursor.var(oracledb.ROWID)
        self.cursor.execute("""
                insert into TestTempTable (IntCol, StringCol1)
                values (278, 'String 278')
                returning rowid into :1""", (var,))
        rowid, = var.getvalue()
        self.cursor.execute("""
                select IntCol, StringCol1
                from TestTempTable
                where rowid = :1""",
                (rowid,))
        self.assertEqual(self.cursor.fetchall(), [(278, 'String 278')])

    def test_1609_insert_with_ref_cursor(self):
        "1609 - test inserting with a REF cursor and returning a rowid"
        self.cursor.execute("truncate table TestTempTable")
        var = self.cursor.var(oracledb.ROWID)
        in_cursor = self.connection.cursor()
        in_cursor.execute("""
                select StringCol
                from TestStrings
                where IntCol >= 5
                order by IntCol""")
        self.cursor.execute("""
                insert into TestTempTable (IntCol, StringCol1)
                values (187, pkg_TestRefCursors.TestInCursor(:1))
                returning rowid into :2""", (in_cursor, var))
        rowid, = var.getvalue()
        self.cursor.execute("""
                select IntCol, StringCol1
                from TestTempTable
                where rowid = :1""",
                (rowid,))
        self.assertEqual(self.cursor.fetchall(),
                         [(187, 'String 7 (Modified)')])

    def test_1610_delete_returning_decreasing_rows_returned(self):
        "1610 - test delete returning decreasing number of rows"
        data = [(i, "Test String %d" % i) for i in range(1, 11)]
        self.cursor.execute("truncate table TestTempTable")
        self.cursor.executemany("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)""", data)
        results = []
        int_var = self.cursor.var(int)
        self.cursor.setinputsizes(None, int_var)
        for int_val in (5, 8, 10):
            self.cursor.execute("""
                    delete from TestTempTable
                    where IntCol < :1
                    returning IntCol into :2""", [int_val])
            results.append(int_var.getvalue())
        self.assertEqual(results, [[1, 2, 3, 4], [5, 6, 7], [8, 9]])

    def test_1611_delete_returning_no_rows_after_many_rows(self):
        "1611 - test delete returning no rows after returning many rows"
        data = [(i, "Test String %d" % i) for i in range(1, 11)]
        self.cursor.execute("truncate table TestTempTable")
        self.cursor.executemany("""
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)""", data)
        int_var = self.cursor.var(int)
        self.cursor.execute("""
                delete from TestTempTable
                where IntCol < :1
                returning IntCol into :2""", [5, int_var])
        self.assertEqual(int_var.getvalue(), [1, 2, 3, 4])
        self.cursor.execute(None, [4, int_var])
        self.assertEqual(int_var.getvalue(), [])

    def test_1612_insert_with_dml_returning_and_error(self):
        "1612 - test DML returning when an error occurs"
        self.cursor.execute("truncate table TestTempTable")
        int_val = 7
        str_val = "A" * 401
        int_var = self.cursor.var(oracledb.NUMBER)
        str_var = self.cursor.var(str)
        sql = """
                insert into TestTempTable (IntCol, StringCol1)
                values (:int_val, :str_val)
                returning IntCol, StringCol1 into :int_var, :str_var"""
        parameters = dict(int_val=int_val, str_val=str_val, int_var=int_var,
                          str_var=str_var)
        self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-12899:",
                               self.cursor.execute, sql, parameters)

    def test_1613_insert_with_dml_returning_no_input_vars(self):
        "1613 - test DML returning with no input variables, multiple iters"
        self.cursor.execute("truncate table TestTempTable")
        sql = """
                insert into TestTempTable (IntCol)
                values ((select count(*) + 1 from TestTempTable))
                returning IntCol into :1"""
        var = self.cursor.var(int)
        self.cursor.execute(sql, [var])
        self.assertEqual(var.getvalue(), [1])
        self.cursor.execute(sql, [var])
        self.assertEqual(var.getvalue(), [2])

    def test_1614_parse_quoted_returning_bind(self):
        "1614 - test DML returning with a quoted bind name"
        sql = '''
                insert into TestTempTable (IntCol, StringCol1)
                values (:int_val, :str_val)
                returning IntCol, StringCol1 into :"_val1" , :"VaL_2"'''
        self.cursor.parse(sql)
        expected_bind_names = ['INT_VAL', 'STR_VAL', '_val1', 'VaL_2']
        self.assertEqual(self.cursor.bindnames(), expected_bind_names)

    def test_1615_parse_invalid_returning_bind(self):
        "1615 - test DML returning with an invalid bind name"
        sql = '''
                insert into TestTempTable (IntCol)
                values (:int_val)
                returning IntCol, StringCol1 into :ROWID'''
        self.assertRaisesRegex(oracledb.DatabaseError,
                               "^ORA-01745:", self.cursor.parse, sql)

    def test_1616_parse_non_ascii_returning_bind(self):
        "1616 - test DML returning with a non-ascii bind name"
        sql = '''
                insert into TestTempTable (IntCol)
                values (:int_val)
                returning IntCol, StringCol1 into :méil'''
        self.cursor.prepare(sql)
        self.assertEqual(self.cursor.bindnames(), ["INT_VAL", "MÉIL"])

    def test_1617_dml_returning_with_input_bind_vars(self):
        "1617 - test DML returning with input bind variable data"
        self.cursor.execute("truncate table TestTempTable")
        out_var = self.cursor.var(int)
        self.cursor.execute("""
                insert into TestTempTable (IntCol)
                values (:int_val)
                returning IntCol + :add_val into :out_val""",
                int_val=5,
                add_val=18,
                out_val=out_var)
        self.connection.commit()
        self.assertEqual(out_var.getvalue(), [23])

    def test_1618_dml_returning_with_lob_and_outconverter(self):
        "1618 - test DML returning with LOBs and an output converter"
        self.cursor.execute("truncate table TestCLOBs")
        out_var = self.cursor.var(oracledb.DB_TYPE_CLOB,
                                  outconverter=lambda value: value.read())
        lob_value = "A short CLOB - 1618"
        self.cursor.execute("""
                insert into TestCLOBs
                (IntCol, ClobCol)
                values (1, :in_val)
                returning CLOBCol into :out_val""",
                in_val=lob_value,
                out_val=out_var)
        self.connection.commit()
        self.assertEqual(out_var.getvalue(), [lob_value])

    def test_1619_dml_returning_with_clob_converted_to_long(self):
        "1619 - test DML returning with CLOB converted to LONG"
        self.cursor.execute("truncate table TestCLOBs")
        out_var = self.cursor.var(oracledb.DB_TYPE_LONG)
        lob_value = "A short CLOB - 1619"
        self.cursor.execute("""
                insert into TestCLOBs
                (IntCol, ClobCol)
                values (1, :in_val)
                returning CLOBCol into :out_val""",
                in_val=lob_value,
                out_val=out_var)
        self.connection.commit()
        self.assertEqual(out_var.getvalue(), [lob_value])

    def test_1620_dml_returning_with_index_organized_table(self):
        "1620 - test dml returning with an index organized table"
        self.cursor.execute("truncate table TestUniversalRowids")
        rowid_var = self.cursor.var(oracledb.ROWID)
        data = (1, "ABC", datetime.datetime(2017, 4, 11), rowid_var)
        sql = "insert into TestUniversalRowids values (:1, :2, :3)\n" + \
              "returning rowid into :4"
        self.cursor.execute(sql, data)
        rowid_value, = rowid_var.getvalue()
        self.cursor.execute("""
                select * from TestUniversalRowids where rowid = :1""",
                [rowid_value])
        row, = self.cursor.fetchall()
        self.assertEqual(data[:3], row)

    def test_1621_plsql_returning_rowids_with_index_organized_table(self):
        "1621 - test plsql returning rowids with index organized table"
        self.cursor.execute("truncate table TestUniversalRowids")
        rowid_var = self.cursor.var(oracledb.ROWID)
        data = (1, "ABC", datetime.datetime(2017, 4, 11), rowid_var)
        self.cursor.execute("""
                begin
                insert into TestUniversalRowids values (:1, :2, :3)
                returning rowid into :4; end;""", data)
        rowid_value = rowid_var.values[0]
        self.cursor.execute("""
                select * from TestUniversalRowids where rowid = :1""",
                [rowid_value])
        row, = self.cursor.fetchall()
        self.assertEqual(data[:3], row)

if __name__ == "__main__":
    test_env.run_test_cases()
