#------------------------------------------------------------------------------
# Copyright (c) 2021, 2022, Oracle and/or its affiliates.
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
3700 - Module for testing all variable types.
"""

import datetime
import decimal
import unittest

import oracledb
import test_env

class TestCase(test_env.BaseTestCase):

    def _test_positive_set_and_get(self, var_type, value_to_set,
                                   expected_value, type_name=None):
        var = self.cursor.var(var_type, typename=type_name)
        var.setvalue(0, value_to_set)
        result = var.getvalue()
        if isinstance(result, oracledb.LOB):
            result = result.read()
        elif isinstance(result, oracledb.DbObject):
            result = self.get_db_object_as_plain_object(result)
        if isinstance(expected_value, datetime.date) \
                and not isinstance(expected_value, datetime.datetime):
            if isinstance(result, datetime.datetime):
                result = result.date()
        self.assertEqual(type(result), type(expected_value))
        self.assertEqual(result, expected_value)

    def _test_negative_set_and_get(self, var_type, value_to_set,
                                   type_name=None):
        var = self.cursor.var(var_type, typename=type_name)
        self.assertRaises((TypeError, oracledb.DatabaseError),
                           var.setvalue, 0, value_to_set)

    def test_3700_DB_TYPE_NUMBER(self):
        "3700 - setting values on variables of type DB_TYPE_NUMBER"
        self._test_positive_set_and_get(int, 5, 5)
        self._test_positive_set_and_get(oracledb.DB_TYPE_NUMBER, 3.5, 3.5)
        self._test_positive_set_and_get(decimal.Decimal,
                                        decimal.Decimal("24.8"),
                                        decimal.Decimal("24.8"))
        self._test_positive_set_and_get(int, True, 1)
        self._test_positive_set_and_get(int, False, 0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_NUMBER, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NUMBER, "abc")

    def test_3701_DB_TYPE_BINARY_INTEGER(self):
        "3701 - setting values on variables of type DB_TYPE_BINARY_INTEGER"
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER, 5, 5)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER,
                                        3.5, 3)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER,
                                        decimal.Decimal("24.8"), 24)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER,
                                        True, 1)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER,
                                        False, 0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BINARY_INTEGER, "abc")

    def test_3702_DB_TYPE_VARCHAR(self):
        "3702 - setting values on variables of type DB_TYPE_VARCHAR"
        value = "A VARCHAR string"
        self._test_positive_set_and_get(oracledb.DB_TYPE_VARCHAR, value, value)
        value = b"A raw string for VARCHAR"
        self._test_positive_set_and_get(oracledb.DB_TYPE_VARCHAR, value,
                                        value.decode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_VARCHAR, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_VARCHAR, 5)

    def test_3703_DB_TYPE_NVARCHAR(self):
        "3703 - setting values on variables of type DB_TYPE_NVARCHAR"
        value = "A NVARCHAR string"
        self._test_positive_set_and_get(oracledb.DB_TYPE_NVARCHAR, value,
                                        value)
        value = b"A raw string for NVARCHAR"
        self._test_positive_set_and_get(oracledb.DB_TYPE_NVARCHAR, value,
                                        value.decode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_NVARCHAR, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NVARCHAR, 5)

    def test_3704_DB_TYPE_CHAR(self):
        "3704 - setting values on variables of type DB_TYPE_CHAR"
        value = "A CHAR string"
        self._test_positive_set_and_get(oracledb.DB_TYPE_CHAR, value, value)
        value = b"A raw string for CHAR"
        self._test_positive_set_and_get(oracledb.DB_TYPE_CHAR, value,
                                        value.decode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_CHAR, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_CHAR, 5)

    def test_3705_DB_TYPE_NCHAR(self):
        "3705 - setting values on variables of type DB_TYPE_NCHAR"
        value = "A NCHAR string"
        self._test_positive_set_and_get(oracledb.DB_TYPE_NCHAR, value, value)
        value = b"A raw string for NCHAR"
        self._test_positive_set_and_get(oracledb.DB_TYPE_CHAR, value,
                                        value.decode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_NCHAR, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NCHAR, 5)

    def test_3706_DB_TYPE_LONG(self):
        "3706 - setting values on variables of type DB_TYPE_LONG"
        value = "Long Data" * 15000
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG, value, value)
        value = b"Raw data for LONG" * 15000
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG, value,
                                        value.decode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_LONG, 5)

    def test_3707_DB_TYPE_RAW(self):
        "3707 - setting values on variables of type DB_TYPE_RAW"
        value = b'Raw Data'
        self._test_positive_set_and_get(oracledb.DB_TYPE_RAW, value, value)
        value = "String data for RAW"
        self._test_positive_set_and_get(oracledb.DB_TYPE_RAW, value,
                                        value.encode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_RAW, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_RAW, 5)

    def test_3708_DB_TYPE_LONG_RAW(self):
        "3708 - setting values on variables of type DB_TYPE_LONG_RAW"
        value = b'Long Raw Data' * 15000
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG_RAW, value,
                                        value)
        value = "String data for LONG RAW" * 15000
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG_RAW, value,
                                        value.encode())
        self._test_positive_set_and_get(oracledb.DB_TYPE_LONG_RAW, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_LONG_RAW, 5)

    def test_3709_DB_TYPE_DATE(self):
        "3709 - setting values on variables of type DB_TYPE_DATE"
        value = datetime.date(2017, 5, 6)
        self._test_positive_set_and_get(oracledb.DB_TYPE_DATE, value,
                                        value)
        value = datetime.datetime(2017, 5, 6, 9, 36, 0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_DATE, value, value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_DATE, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_DATE, 5)

    def test_3710_DB_TYPE_TIMESTAMP(self):
        "3710 - setting values on variables of type DB_TYPE_TIMESTAMP"
        value = datetime.date(2017, 5, 6)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP, value,
                                        value)
        value = datetime.datetime(2017, 5, 6, 9, 36, 0, 300000)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP, value,
                                        value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_TIMESTAMP, 5)

    def test_3711_DB_TYPE_TIMESTAMP_TZ(self):
        "3711 - setting values on variables of type DB_TYPE_TIMESTAMP_TZ"
        value = datetime.date(2017, 5, 6)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_TZ, value,
                                        value)
        value = datetime.datetime(2017, 5, 6, 9, 36, 0, 300000)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_TZ, value,
                                        value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_TZ,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_TIMESTAMP_TZ, 5)

    def test_3712_DB_TYPE_TIMESTAMP_LTZ(self):
        "3712 - setting values on variables of type DB_TYPE_TIMESTAMP_LTZ"
        value = datetime.date(2017, 5, 6)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_LTZ, value,
                                        value)
        value = datetime.datetime(2017, 5, 6, 9, 36, 0, 300000)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_LTZ, value,
                                        value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_TIMESTAMP_LTZ,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_TIMESTAMP_LTZ, 5)

    def test_3713_DB_TYPE_BLOB(self):
        "3713 - setting values on variables of type DB_TYPE_BLOB"
        value = b'Short temp BLOB value'
        temp_blob = self.connection.createlob(oracledb.DB_TYPE_BLOB)
        temp_blob.write(value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BLOB, temp_blob,
                                        value)
        self._test_negative_set_and_get(oracledb.DB_TYPE_CLOB, temp_blob)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NCLOB, temp_blob)
        value = b'Short BLOB value'
        self._test_positive_set_and_get(oracledb.DB_TYPE_BLOB, value, value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BLOB, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BLOB, 5)

    def test_3714_DB_TYPE_CLOB(self):
        "3714 - setting values on variables of type DB_TYPE_CLOB"
        value = 'Short temp CLOB value'
        temp_clob = self.connection.createlob(oracledb.DB_TYPE_CLOB)
        temp_clob.write(value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_CLOB, temp_clob,
                                        value)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BLOB, temp_clob)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NCLOB, temp_clob)
        value = 'Short CLOB value'
        self._test_positive_set_and_get(oracledb.DB_TYPE_CLOB, value, value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_CLOB, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_CLOB, 5)

    def test_3715_DB_TYPE_NCLOB(self):
        "3715 - setting values on variables of type DB_TYPE_NCLOB"
        value = 'Short temp NCLOB value'
        temp_nclob = self.connection.createlob(oracledb.DB_TYPE_NCLOB)
        temp_nclob.write(value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_NCLOB, temp_nclob,
                                        value)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BLOB, temp_nclob)
        self._test_negative_set_and_get(oracledb.DB_TYPE_CLOB, temp_nclob)
        value = 'Short NCLOB Value'
        self._test_positive_set_and_get(oracledb.DB_TYPE_NCLOB, value, value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_NCLOB, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_NCLOB, 5)

    def test_3716_DB_TYPE_BINARY_FLOAT(self):
        "3716 - setting values on variables of type DB_TYPE_BINARY_FLOAT"
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT, 5, 5.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT,
                                        3.5, 3.5)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT,
                                        decimal.Decimal("24.5"), 24.5)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT,
                                        True, 1.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT,
                                        False, 0.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BINARY_FLOAT, "abc")

    def test_3717_DB_TYPE_BINARY_DOUBLE(self):
        "3717 - setting values on variables of type DB_TYPE_BINARY_DOUBLE"
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE, 5, 5.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE,
                                        3.5, 3.5)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE,
                                        decimal.Decimal("192.125"), 192.125)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE,
                                        True, 1.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE,
                                        False, 0.0)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_BINARY_DOUBLE, "abc")

    def test_3718_DB_TYPE_BOOLEAN(self):
        "3718 - setting values on variables of type DB_TYPE_BOOLEAN"
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, 5, True)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, 2.0, True)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, "abc", True)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN,
                                        decimal.Decimal("24.8"), True)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, 0.0, False)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, 0, False)
        self._test_positive_set_and_get(oracledb.DB_TYPE_BOOLEAN, None, None)

    def test_3719_DB_TYPE_INTERVAL_DS(self):
        "3719 - setting values on variables of type DB_TYPE_INTERVAL_DS"
        value = datetime.timedelta(days=5, seconds=56000, microseconds=123780)
        self._test_positive_set_and_get(oracledb.DB_TYPE_INTERVAL_DS,
                                        value, value)
        self._test_positive_set_and_get(oracledb.DB_TYPE_INTERVAL_DS,
                                        None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_INTERVAL_DS, 5)

    def test_3720_DB_TYPE_ROWID(self):
        "3720 - setting values on variables of type DB_TYPE_ROWID"
        self._test_negative_set_and_get(oracledb.DB_TYPE_ROWID, 12345)
        self._test_negative_set_and_get(oracledb.DB_TYPE_ROWID, "523lkhlf")

    def test_3721_DB_TYPE_OBJECT(self):
        "3721 - setting values on variables of type DB_TYPE_OBJECT"
        obj_type = self.connection.gettype("UDT_OBJECT")
        obj = obj_type.newobject()
        plain_obj = self.get_db_object_as_plain_object(obj)
        self._test_positive_set_and_get(oracledb.DB_TYPE_OBJECT,
                                        obj, plain_obj, "UDT_OBJECT")
        self._test_positive_set_and_get(obj_type, obj, plain_obj)
        self._test_positive_set_and_get(oracledb.DB_TYPE_OBJECT,
                                        None, None, "UDT_OBJECT")
        self._test_positive_set_and_get(obj_type, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_OBJECT,
                                        "abc", "UDT_OBJECT")
        self._test_negative_set_and_get(oracledb.DB_TYPE_OBJECT, obj,
                                        "UDT_OBJECTARRAY")
        wrong_obj_type = self.connection.gettype("UDT_OBJECTARRAY")
        self._test_negative_set_and_get(wrong_obj_type, obj)

    @unittest.skipIf(test_env.get_client_version() < (21, 0),
                     "unsupported client")
    @unittest.skipIf(test_env.get_server_version() < (21, 0),
                     "unsupported server")
    @unittest.skipIf(test_env.get_is_thin(),
                     "thin mode doesn't support JSON yet")
    def test_3722_DB_TYPE_JSON(self):
        "3722 - setting values on variables of type DB_TYPE_JSON"
        json_data = [
            5,
            25.25,
            decimal.Decimal("10.25"),
            True,
            False,
            datetime.datetime(2017, 5, 6),
            datetime.datetime(2017, 5, 6, 9, 36, 0, 300000),
            datetime.timedelta(days=5, seconds=56000, microseconds=123780),
            {},
            'String',
            b'Some bytes',
            {'keyA': 1, 'KeyB': 'Melbourne'},
            [],
            [1, "A"],
            {"name": None},
            {"name": "John"},
            {"age": 30},
            {"Permanent": True},
            {
                "employee": {
                    "name":"John",
                    "age": 30,
                    "city": "Delhi",
                    "Parmanent": True
                }
            },
            {
                "employees": ["John", "Matthew", "James"]
            },
            {
                "employees": [
                    {
                        "employee1": {"name": "John", "city": "Delhi"}
                    },
                    {
                        "employee2": {"name": "Matthew", "city": "Mumbai"}
                    },
                    {
                        "employee3": {"name": "James", "city": "Bangalore"}
                    }
                ]
            }
        ]
        self._test_positive_set_and_get(oracledb.DB_TYPE_JSON,
                                        json_data, json_data)
        self._test_positive_set_and_get(oracledb.DB_TYPE_JSON, None, None)

    def test_3723_DB_TYPE_CURSOR(self):
        "3723 - test setting values on variables of type DB_TYPE_CURSOR"
        cursor = self.connection.cursor()
        self._test_positive_set_and_get(oracledb.DB_TYPE_CURSOR, None, None)
        self._test_negative_set_and_get(oracledb.DB_TYPE_CURSOR, 5)

    def test_3724_fetch_null_column(self):
        "3724 - test fetching columns containing all null values"
        self.cursor.execute("""
                select
                    null,
                    to_char(null),
                    to_number(null),
                    to_date(null),
                    to_timestamp(null),
                    to_clob(null),
                    to_blob(null)
                from dual""")
        results = self.cursor.fetchall()
        self.assertEqual(results, [(None, None, None, None, None, None, None)])

    @unittest.skipIf(not test_env.get_is_thin(),
                     "thick mode doesn't support DB_TYPE_UROWID")
    def test_3725_DB_TYPE_UROWID(self):
        "3725 - setting values on variables of type DB_TYPE_UROWID"
        self._test_negative_set_and_get(oracledb.DB_TYPE_UROWID, 12345)
        self._test_negative_set_and_get(oracledb.DB_TYPE_UROWID, "523lkhlf")

if __name__ == "__main__":
    test_env.run_test_cases()
