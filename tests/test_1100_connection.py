# -----------------------------------------------------------------------------
# Copyright (c) 2020, 2023, Oracle and/or its affiliates.
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
1100 - Module for testing connections
"""

import random
import string
import threading
import time
import unittest

import oracledb
import test_env


class TestCase(test_env.BaseTestCase):
    requires_connection = False

    def __connect_and_drop(self):
        """
        Connect to the database, perform a query and drop the connection.
        """
        with test_env.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("select count(*) from TestNumbers")
            (count,) = cursor.fetchone()
            self.assertEqual(count, 10)

    def __verify_fetched_data(self, connection):
        expected_data = [f"String {i + 1}" for i in range(10)]
        sql = "select StringCol from TestStrings order by IntCol"
        for i in range(5):
            with connection.cursor() as cursor:
                fetched_data = [s for s, in cursor.execute(sql)]
                self.assertEqual(fetched_data, expected_data)

    def __verify_attributes(self, connection, attr_name, value, sql):
        setattr(connection, attr_name, value)
        cursor = connection.cursor()
        cursor.execute(sql)
        (result,) = cursor.fetchone()
        self.assertEqual(result, value, f"{attr_name} value mismatch")

    def test_1100_simple_connection(self):
        "1100 - simple connection to database"
        conn = test_env.get_connection()
        self.assertEqual(
            conn.username, test_env.get_main_user(), "user name differs"
        )
        self.assertEqual(
            conn.dsn, test_env.get_connect_string(), "dsn differs"
        )

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support application context yet",
    )
    def test_1101_app_context(self):
        "1101 - test use of application context"
        namespace = "CLIENTCONTEXT"
        app_context_entries = [
            (namespace, "ATTR1", "VALUE1"),
            (namespace, "ATTR2", "VALUE2"),
            (namespace, "ATTR3", "VALUE3"),
        ]
        conn = test_env.get_connection(appcontext=app_context_entries)
        cursor = conn.cursor()
        for namespace, name, value in app_context_entries:
            cursor.execute(
                "select sys_context(:1, :2) from dual", (namespace, name)
            )
            (actual_value,) = cursor.fetchone()
            self.assertEqual(actual_value, value)

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support application context yet",
    )
    def test_1102_app_context_negative(self):
        "1102 - test invalid use of application context"
        self.assertRaises(
            TypeError,
            test_env.get_connection,
            appcontext=[("userenv", "action")],
        )

    def test_1103_attributes(self):
        "1103 - test connection end-to-end tracing attributes"
        conn = test_env.get_connection()
        if test_env.get_client_version() >= (
            12,
            1,
        ) and not self.is_on_oracle_cloud(conn):
            sql = """select dbop_name from v$sql_monitor
                     where sid = sys_context('userenv', 'sid')
                     and status = 'EXECUTING'"""
            self.__verify_attributes(conn, "dbop", "oracledb_dbop", sql)
        sql = "select sys_context('userenv', 'action') from dual"
        self.__verify_attributes(conn, "action", "oracledb_Action", sql)
        self.__verify_attributes(conn, "action", None, sql)
        sql = "select sys_context('userenv', 'module') from dual"
        self.__verify_attributes(conn, "module", "oracledb_Module", sql)
        self.__verify_attributes(conn, "module", None, sql)
        sql = "select sys_context('userenv', 'client_info') from dual"
        self.__verify_attributes(conn, "clientinfo", "oracledb_cinfo", sql)
        self.__verify_attributes(conn, "clientinfo", None, sql)
        sql = "select sys_context('userenv', 'client_identifier') from dual"
        self.__verify_attributes(
            conn, "client_identifier", "oracledb_cid", sql
        )
        self.__verify_attributes(conn, "client_identifier", None, sql)
        if not test_env.get_is_thin():
            sql = """select ecid from v$session
                     where sid = sys_context('userenv', 'sid')"""
            self.__verify_attributes(conn, "econtext_id", "oracledb_ecid", sql)
            self.__verify_attributes(conn, "econtext_id", None, sql)

    def test_1104_autocommit(self):
        "1104 - test use of autocommit"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        other_conn = test_env.get_connection()
        other_cursor = other_conn.cursor()
        cursor.execute("truncate table TestTempTable")
        cursor.execute("insert into TestTempTable (IntCol) values (1)")
        other_cursor.execute("select IntCol from TestTempTable")
        self.assertEqual(other_cursor.fetchall(), [])
        conn.autocommit = True
        cursor.execute("insert into TestTempTable (IntCol) values (2)")
        other_cursor.execute(
            "select IntCol from TestTempTable order by IntCol"
        )
        self.assertEqual(other_cursor.fetchall(), [(1,), (2,)])

    def test_1105_bad_connect_string(self):
        "1105 - connection to database with bad connect string"
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^DPY-4000:|^DPY-4026:|^DPY-4027:|ORA-12154:",
            oracledb.connect,
            test_env.get_main_user(),
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^DPY-4000:|^DPY-4001:",
            oracledb.connect,
            test_env.get_main_user() + "@" + test_env.get_connect_string(),
        )
        errors = (
            "^DPY-4000:|^DPY-4001:|^DPY-4017:|^ORA-12154:|^ORA-12521:|"
            "^ORA-12262:"
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            errors,
            oracledb.connect,
            test_env.get_main_user()
            + "@"
            + test_env.get_connect_string()
            + "/"
            + test_env.get_main_password(),
        )

    def test_1106_bad_password(self):
        "1106 - connection to database with bad password"
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-01017:",
            test_env.get_connection,
            password=test_env.get_main_password() + "X",
        )

    def test_1107_change_password(self):
        "1107 - test changing password"
        conn = test_env.get_connection()
        if self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        new_password = "".join(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        conn.changepassword(test_env.get_main_password(), new_password)
        conn = test_env.get_connection(password=new_password)
        conn.changepassword(new_password, test_env.get_main_password())

    def test_1108_change_password_negative(self):
        "1108 - test changing password to an invalid value"
        conn = test_env.get_connection()
        if self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        new_password = "1" * 1500
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-01017:|^ORA-00988:",
            conn.changepassword,
            test_env.get_main_password(),
            new_password,
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-01017:|^ORA-28008:|^ORA-00988:",
            conn.changepassword,
            "incorrect old password",
            new_password,
        )

    def test_1109_parse_password(self):
        "1109 - test connecting with password containing / and @ symbols"
        conn = test_env.get_connection()
        if self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        chars = list(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        chars[4] = "/"
        chars[8] = "@"
        new_password = "".join(chars)
        conn.changepassword(test_env.get_main_password(), new_password)
        try:
            test_env.get_connection(password=new_password)
        finally:
            conn.changepassword(new_password, test_env.get_main_password())

    def test_1110_exception_on_close(self):
        "1110 - confirm an exception is raised after closing a connection"
        conn = test_env.get_connection()
        conn.close()
        self.assertRaisesRegex(
            oracledb.InterfaceError, "^DPY-1001:", conn.rollback
        )

    @unittest.skipIf(test_env.get_is_thin(), "not relevant for thin mode")
    def test_1111_connect_with_handle(self):
        "1111 - test creating a connection using a handle"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("truncate table TestTempTable")
        int_value = random.randint(1, 32768)
        cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (:val, null)
            """,
            val=int_value,
        )
        conn2 = oracledb.connect(handle=conn.handle)
        cursor = conn2.cursor()
        cursor.execute("select IntCol from TestTempTable")
        (fetched_int_value,) = cursor.fetchone()
        self.assertEqual(fetched_int_value, int_value)

        cursor.close()
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^DPI-1034:", conn2.close
        )
        conn.close()

    def test_1112_version(self):
        "1112 - connection version is a string"
        conn = test_env.get_connection()
        self.assertIsInstance(conn.version, str)

    def test_1113_rollback_on_close(self):
        "1113 - connection rolls back before close"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("truncate table TestTempTable")
        other_conn = test_env.get_connection()
        other_cursor = other_conn.cursor()
        other_cursor.execute("insert into TestTempTable (IntCol) values (1)")
        other_cursor.close()
        other_conn.close()
        cursor.execute("select count(*) from TestTempTable")
        (count,) = cursor.fetchone()
        self.assertEqual(count, 0)

    def test_1114_rollback_on_del(self):
        "1114 - connection rolls back before destruction"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("truncate table TestTempTable")
        other_conn = test_env.get_connection()
        other_cursor = other_conn.cursor()
        other_cursor.execute("insert into TestTempTable (IntCol) values (1)")
        del other_cursor
        del other_conn
        cursor.execute("select count(*) from TestTempTable")
        (count,) = cursor.fetchone()
        self.assertEqual(count, 0)

    def test_1115_threading(self):
        "1115 - multiple connections to database with multiple threads"
        threads = []
        for i in range(20):
            thread = threading.Thread(None, self.__connect_and_drop)
            threads.append(thread)
            thread.start()
            time.sleep(0.1)
        for thread in threads:
            thread.join()

    def test_1116_string_format(self):
        "1116 - test string format of connection"
        conn = test_env.get_connection()
        expected_value = "<oracledb.Connection to %s@%s>" % (
            test_env.get_main_user(),
            test_env.get_connect_string(),
        )
        self.assertEqual(str(conn), expected_value)

    def test_1117_ctx_mgr_close(self):
        "1117 - test context manager - close"
        with test_env.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("truncate table TestTempTable")
            cursor.execute("insert into TestTempTable (IntCol) values (1)")
            conn.commit()
            cursor.execute("insert into TestTempTable (IntCol) values (2)")
        self.assertRaisesRegex(
            oracledb.InterfaceError, "^DPY-1001:", conn.ping
        )
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("select count(*) from TestTempTable")
        (count,) = cursor.fetchone()
        self.assertEqual(count, 1)

    def test_1118_connection_attributes(self):
        "1118 - test connection attribute values"
        conn = test_env.get_connection()
        if test_env.get_client_version() >= (12, 1):
            self.assertEqual(conn.ltxid, b"")
        self.assertIsNone(conn.current_schema)
        conn.current_schema = "test_schema"
        self.assertEqual(conn.current_schema, "test_schema")
        self.assertIsNone(conn.edition)
        conn.external_name = "test_external"
        self.assertEqual(conn.external_name, "test_external")
        conn.internal_name = "test_internal"
        self.assertEqual(conn.internal_name, "test_internal")
        conn.stmtcachesize = 30
        self.assertEqual(conn.stmtcachesize, 30)
        self.assertRaises(TypeError, conn.stmtcachesize, 20.5)
        self.assertRaises(TypeError, conn.stmtcachesize, "value")

    def test_1119_closed_connection_attributes(self):
        "1119 - test closed connection attribute values"
        conn = test_env.get_connection()
        conn.close()
        attr_names = [
            "current_schema",
            "edition",
            "external_name",
            "internal_name",
            "stmtcachesize",
        ]
        if test_env.get_client_version() >= (12, 1):
            attr_names.append("ltxid")
        for name in attr_names:
            self.assertRaisesRegex(
                oracledb.InterfaceError, "^DPY-1001:", getattr, conn, name
            )

    def test_1120_ping(self):
        "1120 - test connection ping makes a round trip"
        self.conn = test_env.get_connection()
        self.setup_round_trip_checker()
        self.conn.ping()
        self.assertRoundTrips(1)

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support two-phase commit yet",
    )
    def test_1121_transaction_begin(self):
        "1121 - test begin, prepare, cancel transaction"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("truncate table TestTempTable")
        conn.begin(10, "trxnId", "branchId")
        self.assertFalse(conn.prepare())
        conn.begin(10, "trxnId", "branchId")
        cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'tesName')
            """
        )
        self.assertTrue(conn.prepare())
        conn.cancel()
        conn.rollback()
        cursor.execute("select count(*) from TestTempTable")
        (count,) = cursor.fetchone()
        self.assertEqual(count, 0)

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support two-phase commit yet",
    )
    def test_1122_multiple_transactions(self):
        "1122 - test multiple transactions on the same connection"
        conn = test_env.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("truncate table TestTempTable")

        id_ = random.randint(0, 2**128)
        xid = (0x1234, "%032x" % id_, "%032x" % 9)
        conn.begin(*xid)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (1, 'tesName')
                """
            )
            self.assertTrue(conn.prepare())
            conn.commit()

        for begin_trans in (True, False):
            val = 3
            if begin_trans:
                conn.begin()
                val = 2
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into TestTempTable (IntCol, StringCol1)
                    values (:int_val, 'tesName')
                    """,
                    int_val=val,
                )
                conn.commit()

        expected_rows = [(1, "tesName"), (2, "tesName"), (3, "tesName")]
        with conn.cursor() as cursor:
            cursor.execute("select IntCol, StringCol1 from TestTempTable")
            self.assertEqual(cursor.fetchall(), expected_rows)

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support two-phase commit yet",
    )
    def test_1123_multiple_global_transactions(self):
        "1123 - test multiple global transactions on the same connection"
        conn = test_env.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("truncate table TestTempTable")

        id_ = random.randint(0, 2**128)
        xid = (0x1234, "%032x" % id_, "%032x" % 9)
        conn.begin(*xid)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (1, 'tesName')
                """
            )
            self.assertTrue(conn.prepare())
            conn.commit()

        for begin_trans in (True, False):
            val = 3
            if begin_trans:
                conn.begin()
                val = 2
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into TestTempTable (IntCol, StringCol1)
                    values (:int_val, 'tesName')
                    """,
                    int_val=val,
                )
                conn.commit()

        id2_ = random.randint(0, 2**128)
        xid2 = (0x1234, "%032x" % id2_, "%032x" % 9)
        conn.begin(*xid2)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (4, 'tesName')
                """
            )
            self.assertTrue(conn.prepare())
            conn.commit()

        expected_rows = [
            (1, "tesName"),
            (2, "tesName"),
            (3, "tesName"),
            (4, "tesName"),
        ]
        with conn.cursor() as cursor:
            cursor.execute("select IntCol, StringCol1 from TestTempTable")
            self.assertEqual(cursor.fetchall(), expected_rows)

    @unittest.skipIf(
        test_env.get_is_thin(),
        "thin mode doesn't support two-phase commit yet",
    )
    def test_1124_exception_creating_global_txn_after_local_txn(self):
        "1124 - test creating global txn after a local txn"
        conn = test_env.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("truncate table TestTempTable")

        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (2, 'tesName')
                """
            )

        id_ = random.randint(0, 2**128)
        xid = (0x1234, "%032x" % id_, "%032x" % 9)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24776:", conn.begin, *xid
        )

    def test_1125_threading_single_connection(self):
        "1125 - single connection to database with multiple threads"
        with test_env.get_connection() as conn:
            threads = [
                threading.Thread(
                    target=self.__verify_fetched_data, args=(conn,)
                )
                for i in range(3)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

    def test_1126_cancel(self):
        "1126 - test connection cancel"
        conn = test_env.get_connection()
        sleep_proc_name = test_env.get_sleep_proc_name()

        def perform_cancel():
            time.sleep(0.1)
            conn.cancel()

        thread = threading.Thread(target=perform_cancel)
        thread.start()
        try:
            with conn.cursor() as cursor:
                self.assertRaises(
                    oracledb.OperationalError,
                    cursor.callproc,
                    sleep_proc_name,
                    [2],
                )
        finally:
            thread.join()
        with conn.cursor() as cursor:
            cursor.execute("select user from dual")
            (user,) = cursor.fetchone()
            self.assertEqual(user, test_env.get_main_user().upper())

    def test_1127_change_password_during_connect(self):
        "1127 - test changing password during connect"
        conn = test_env.get_connection()
        if self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        new_password = "".join(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        conn = test_env.get_connection(newpassword=new_password)
        conn = test_env.get_connection(password=new_password)
        conn.changepassword(new_password, test_env.get_main_password())

    def test_1128_autocommit_during_reexecute(self):
        "1128 - test use of autocommit during reexecute"
        sql = "insert into TestTempTable (IntCol, StringCol1) values (:1, :2)"
        data_to_insert = [(1, "Test String #1"), (2, "Test String #2")]
        conn = test_env.get_connection()
        cursor = conn.cursor()
        other_conn = test_env.get_connection()
        other_cursor = other_conn.cursor()
        cursor.execute("truncate table TestTempTable")
        cursor.execute(sql, data_to_insert[0])
        other_cursor.execute("select IntCol, StringCol1 from TestTempTable")
        self.assertEqual(other_cursor.fetchall(), [])
        conn.autocommit = True
        cursor.execute(sql, data_to_insert[1])
        other_cursor.execute("select IntCol, StringCol1 from TestTempTable")
        self.assertEqual(other_cursor.fetchall(), data_to_insert)

    def test_1129_current_schema(self):
        "1129 - test current_schema is set properly"
        conn = test_env.get_connection()
        self.assertIsNone(conn.current_schema)

        user = test_env.get_main_user().upper()
        proxy_user = test_env.get_proxy_user().upper()
        cursor = conn.cursor()
        cursor.execute(f"alter session set current_schema={proxy_user}")
        self.assertEqual(conn.current_schema, proxy_user)

        conn.current_schema = user
        self.assertEqual(conn.current_schema, user)

        cursor.execute(
            "select sys_context('userenv', 'current_schema') from dual"
        )
        (result,) = cursor.fetchone()
        self.assertEqual(result, user)

    def test_1130_dbms_output(self):
        "1130 - test dbms_output package"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        test_string = "Testing DBMS_OUTPUT package"
        cursor.callproc("dbms_output.enable")
        cursor.callproc("dbms_output.put_line", [test_string])
        string_var = cursor.var(str)
        number_var = cursor.var(int)
        cursor.callproc("dbms_output.get_line", (string_var, number_var))
        self.assertEqual(string_var.getvalue(), test_string)

    @unittest.skipIf(
        not test_env.get_is_thin() and test_env.get_client_version() < (18, 1),
        "unsupported client",
    )
    def test_1131_calltimeout(self):
        "1131 - test connection call_timeout"
        conn = test_env.get_connection()
        conn.call_timeout = 500  # milliseconds
        self.assertEqual(conn.call_timeout, 500)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^DPY-4011:|^DPY-4024:",
            conn.cursor().callproc,
            test_env.get_sleep_proc_name(),
            [2],
        )

    def test_1132_connection_repr(self):
        "1132 - test Connection repr()"

        class MyConnection(oracledb.Connection):
            pass

        conn = test_env.get_connection(conn_class=MyConnection)
        expected_value = (
            f"<{__name__}.TestCase.test_1132_connection_repr."
            f"<locals>.MyConnection to {conn.username}@"
            f"{conn.dsn}>"
        )
        self.assertEqual(repr(conn), expected_value)

        conn.close()
        expected_value = (
            f"<{__name__}.TestCase.test_1132_connection_repr."
            "<locals>.MyConnection disconnected>"
        )
        self.assertEqual(repr(conn), expected_value)

    def test_1133_get_write_only_attributes(self):
        "1133 - test getting write-only attributes"
        conn = test_env.get_connection()
        with self.assertRaises(AttributeError):
            conn.action
        with self.assertRaises(AttributeError):
            conn.dbop
        with self.assertRaises(AttributeError):
            conn.clientinfo
        with self.assertRaises(AttributeError):
            conn.econtext_id
        with self.assertRaises(AttributeError):
            conn.module
        with self.assertRaises(AttributeError):
            conn.client_identifier

    def test_1134_invalid_params(self):
        "1134 - test error for invalid type for params and pool"
        pool = test_env.get_pool()
        pool.close()
        self.assertRaisesRegex(
            oracledb.InterfaceError,
            "^DPY-1002:",
            test_env.get_connection,
            pool=pool,
        )
        self.assertRaises(
            TypeError,
            test_env.get_connection,
            pool="This isn't an instance of a pool",
        )
        self.assertRaisesRegex(
            oracledb.ProgrammingError,
            "^DPY-2025:",
            oracledb.connect,
            params={"number": 7},
        )

    def test_1135_instance_name(self):
        "1135 - test connection instance name"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            select upper(sys_context('userenv', 'instance_name'))
            from dual
            """
        )
        (instance_name,) = cursor.fetchone()
        self.assertEqual(conn.instance_name.upper(), instance_name)

    def test_1136_deprecations(self):
        "1136 - test deprecated attributes"
        conn = test_env.get_connection()
        conn.callTimeout = 500
        self.assertEqual(conn.callTimeout, 500)

    @unittest.skipIf(
        test_env.get_server_version() < (23, 0)
        or test_env.get_client_version() < (23, 0),
        "unsupported client/server",
    )
    def test_1137_max_length_password(self):
        "1137 - test maximum allowed length for password"
        conn = test_env.get_connection()
        if self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")

        original_password = test_env.get_main_password()
        new_password_32 = "a" * 32
        conn.changepassword(original_password, new_password_32)
        conn = test_env.get_connection(password=new_password_32)

        new_password_1024 = "a" * 1024
        conn.changepassword(new_password_32, new_password_1024)
        conn = test_env.get_connection(password=new_password_1024)
        conn.changepassword(new_password_1024, original_password)

        new_password_1025 = "a" * 1025
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-28218:|^ORA-00972",
            conn.changepassword,
            original_password,
            new_password_1025,
        )

    def test_1138_db_name(self):
        "1138 - test getting db_name"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("select name from V$DATABASE")
        (db_name,) = cursor.fetchone()
        self.assertEqual(conn.db_name.upper(), db_name.upper())

    def test_1139_max_open_cursors(self):
        "1139 - test getting max_open_cursors"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "select value from V$PARAMETER where name='open_cursors'"
        )
        (max_open_cursors,) = cursor.fetchone()
        self.assertEqual(conn.max_open_cursors, int(max_open_cursors))

    def test_1140_service_name(self):
        "1140 - test getting service_name"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "select sys_context('userenv', 'service_name') from dual"
        )
        (service_name,) = cursor.fetchone()
        self.assertEqual(conn.service_name, service_name)

    def test_1141_transaction_in_progress(self):
        "1141 - test transaction_in_progress"
        conn = test_env.get_connection()
        self.assertFalse(conn.transaction_in_progress)

        cursor = conn.cursor()
        cursor.execute("truncate table TestTempTable")
        self.assertFalse(conn.transaction_in_progress)

        cursor.execute("insert into TestTempTable (IntCol) values (1)")
        self.assertTrue(conn.transaction_in_progress)

        conn.commit()
        self.assertFalse(conn.transaction_in_progress)

    def test_1142_db_domain(self):
        "1142 - test getting db_domain"
        conn = test_env.get_connection()
        cursor = conn.cursor()
        cursor.execute("select value from V$PARAMETER where name='db_domain'")
        (db_domain,) = cursor.fetchone()
        self.assertEqual(conn.db_domain, db_domain)

    def test_1143_proxy_user(self):
        "1143 - test connecting with a proxy user"
        proxy_user = test_env.get_proxy_user()
        conn = test_env.get_connection(proxy_user=proxy_user)
        self.assertEqual(conn.username, test_env.get_main_user())
        self.assertEqual(conn.proxy_user, proxy_user)


if __name__ == "__main__":
    test_env.run_test_cases()
