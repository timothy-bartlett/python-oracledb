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
5300 - Module for testing connections with asyncio
"""

import asyncio
import random
import string
import unittest

import oracledb
import test_env


@unittest.skipUnless(
    test_env.get_is_thin(), "asyncio not supported in thick mode"
)
class TestCase(test_env.BaseAsyncTestCase):
    requires_connection = False

    async def __connect_and_drop(self):
        """
        Connect to the database, perform a query and drop the connection.
        """
        await asyncio.sleep(0.1)
        async with test_env.get_connection_async() as conn:
            cursor = conn.cursor()
            await cursor.execute("select count(*) from TestNumbers")
            (count,) = await cursor.fetchone()
            self.assertEqual(count, 10)

    async def __verify_fetched_data(self, connection):
        expected_data = [f"String {i + 1}" for i in range(10)]
        sql = "select StringCol from TestStrings order by IntCol"
        for i in range(5):
            with connection.cursor() as cursor:
                await cursor.execute(sql)
                fetched_data = [s async for s, in cursor]
                self.assertEqual(fetched_data, expected_data)

    async def __verify_attributes(self, connection, attr_name, value, sql):
        setattr(connection, attr_name, value)
        cursor = connection.cursor()
        await cursor.execute(sql)
        (result,) = await cursor.fetchone()
        self.assertEqual(result, value, f"{attr_name} value mismatch")

    async def test_5300_simple_connection(self):
        "5300 - simple connection to database"
        conn = await test_env.get_connection_async()
        self.assertEqual(
            conn.username, test_env.get_main_user(), "user name differs"
        )
        self.assertEqual(
            conn.dsn, test_env.get_connect_string(), "dsn differs"
        )

    async def test_5303_attributes(self):
        "5303 - test connection end-to-end tracing attributes"
        conn = await test_env.get_connection_async()
        if not await self.is_on_oracle_cloud(conn):
            sql = """select dbop_name from v$sql_monitor
                     where sid = sys_context('userenv', 'sid')
                     and status = 'EXECUTING'"""
            await self.__verify_attributes(conn, "dbop", "oracledb_dbop", sql)
        sql = "select sys_context('userenv', 'action') from dual"
        await self.__verify_attributes(conn, "action", "oracledb_Action", sql)
        await self.__verify_attributes(conn, "action", None, sql)
        sql = "select sys_context('userenv', 'module') from dual"
        await self.__verify_attributes(conn, "module", "oracledb_Module", sql)
        await self.__verify_attributes(conn, "module", None, sql)
        sql = "select sys_context('userenv', 'client_info') from dual"
        await self.__verify_attributes(
            conn, "clientinfo", "oracledb_cinfo", sql
        )
        await self.__verify_attributes(conn, "clientinfo", None, sql)
        sql = "select sys_context('userenv', 'client_identifier') from dual"
        await self.__verify_attributes(
            conn, "client_identifier", "oracledb_cid", sql
        )
        await self.__verify_attributes(conn, "client_identifier", None, sql)

    async def test_5304_autocommit(self):
        "5304 - test use of autocommit"
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        other_conn = await test_env.get_connection_async()
        other_cursor = other_conn.cursor()
        await cursor.execute("truncate table TestTempTable")
        await cursor.execute("insert into TestTempTable (IntCol) values (1)")
        await other_cursor.execute("select IntCol from TestTempTable")
        self.assertEqual(await other_cursor.fetchall(), [])
        conn.autocommit = True
        await cursor.execute("insert into TestTempTable (IntCol) values (2)")
        await other_cursor.execute(
            "select IntCol from TestTempTable order by IntCol"
        )
        self.assertEqual(await other_cursor.fetchall(), [(1,), (2,)])

    async def test_5305_bad_connect_string(self):
        "5305 - connection to database with bad connect string"
        with self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^DPY-4000:|^DPY-4026:|^DPY-4027:|ORA-12154:",
        ):
            await oracledb.connect_async(test_env.get_main_user())
        with self.assertRaisesRegex(
            oracledb.DatabaseError, "^DPY-4000:|^DPY-4001:"
        ):
            await oracledb.connect(
                test_env.get_main_user() + "@" + test_env.get_connect_string()
            )
        errors = (
            "^DPY-4000:|^DPY-4001:|^DPY-4017:|^ORA-12154:|^ORA-12521:|"
            "^ORA-12262:"
        )
        with self.assertRaisesRegex(oracledb.DatabaseError, errors):
            await oracledb.connect(
                test_env.get_main_user()
                + "@"
                + test_env.get_connect_string()
                + "/"
                + test_env.get_main_password()
            )

    async def test_5306_bad_password(self):
        "5306 - connection to database with bad password"
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-01017:"):
            await test_env.get_connection_async(
                password=test_env.get_main_password() + "X",
            )

    async def test_5307_change_password(self):
        "5307 - test changing password"
        conn = await test_env.get_connection_async()
        if await self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        new_password = "".join(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        await conn.changepassword(test_env.get_main_password(), new_password)
        conn = await test_env.get_connection_async(password=new_password)
        await conn.changepassword(new_password, test_env.get_main_password())

    async def test_5308_change_password_negative(self):
        "5308 - test changing password to an invalid value"
        conn = await test_env.get_connection_async()
        if await self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        new_password = "1" * 1500
        with self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-01017:|^ORA-00988:"
        ):
            await conn.changepassword(
                test_env.get_main_password(), new_password
            )
        with self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-01017:|^ORA-28008:|^ORA-00988:"
        ):
            await conn.changepassword("incorrect old password", new_password)

    async def test_5309_parse_password(self):
        "5309 - test connecting with password containing / and @ symbols"
        conn = await test_env.get_connection_async()
        if await self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        chars = list(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        chars[4] = "/"
        chars[8] = "@"
        new_password = "".join(chars)
        await conn.changepassword(test_env.get_main_password(), new_password)
        try:
            await test_env.get_connection_async(password=new_password)
        finally:
            await conn.changepassword(
                new_password, test_env.get_main_password()
            )

    async def test_5310_exception_on_close(self):
        "5310 - confirm an exception is raised after closing a connection"
        conn = await test_env.get_connection_async()
        await conn.close()
        with self.assertRaisesRegex(oracledb.InterfaceError, "^DPY-1001:"):
            await conn.rollback()

    async def test_5312_version(self):
        "5312 - connection version is a string"
        conn = await test_env.get_connection_async()
        self.assertIsInstance(conn.version, str)

    async def test_5313_rollback_on_close(self):
        "5313 - connection rolls back before close"
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        await cursor.execute("truncate table TestTempTable")
        other_conn = await test_env.get_connection_async()
        other_cursor = other_conn.cursor()
        await other_cursor.execute(
            "insert into TestTempTable (IntCol) values (1)"
        )
        other_cursor.close()
        await other_conn.close()
        await cursor.execute("select count(*) from TestTempTable")
        (count,) = await cursor.fetchone()
        self.assertEqual(count, 0)

    async def test_5315_threading(self):
        "5315 - multiple connections to database with multiple threads"
        coroutines = [self.__connect_and_drop() for i in range(20)]
        await asyncio.gather(*coroutines)

    async def test_5316_string_format(self):
        "5316 - test string format of connection"
        conn = await test_env.get_connection_async()
        expected_value = "<oracledb.AsyncConnection to %s@%s>" % (
            test_env.get_main_user(),
            test_env.get_connect_string(),
        )
        self.assertEqual(str(conn), expected_value)

    async def test_5317_ctx_mgr_close(self):
        "5317 - test context manager - close"
        async with test_env.get_connection_async() as conn:
            cursor = conn.cursor()
            await cursor.execute("truncate table TestTempTable")
            await cursor.execute(
                "insert into TestTempTable (IntCol) values (1)"
            )
            await conn.commit()
            await cursor.execute(
                "insert into TestTempTable (IntCol) values (2)"
            )
        with self.assertRaisesRegex(oracledb.InterfaceError, "^DPY-1001:"):
            await conn.ping()
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        await cursor.execute("select count(*) from TestTempTable")
        (count,) = await cursor.fetchone()
        self.assertEqual(count, 1)

    async def test_5318_connection_attributes(self):
        "5318 - test connection attribute values"
        conn = await test_env.get_connection_async()
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

    async def test_5319_closed_connection_attributes(self):
        "5319 - test closed connection attribute values"
        conn = await test_env.get_connection_async()
        await conn.close()
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

    async def test_5320_ping(self):
        "5320 - test connection ping makes a round trip"
        self.conn = await test_env.get_connection_async()
        await self.setup_round_trip_checker()
        await self.conn.ping()
        await self.assertRoundTrips(1)

    async def test_5325_threading_single_connection(self):
        "5325 - single connection to database with multiple threads"
        async with test_env.get_connection_async() as conn:
            coroutines = [self.__verify_fetched_data(conn) for i in range(3)]
            await asyncio.gather(*coroutines)

    async def test_5326_cancel(self):
        "5326 - test connection cancel"
        conn = await test_env.get_connection_async()
        sleep_proc_name = test_env.get_sleep_proc_name()

        async def perform_cancel():
            await asyncio.sleep(0.1)
            conn.cancel()

        async def perform_work():
            with self.assertRaises(oracledb.OperationalError):
                with conn.cursor() as cursor:
                    await cursor.callproc(sleep_proc_name, [2])

        await asyncio.gather(perform_work(), perform_cancel())

        with conn.cursor() as cursor:
            await cursor.execute("select user from dual")
            (user,) = await cursor.fetchone()
            self.assertEqual(user, test_env.get_main_user().upper())

    async def test_5327_change_password_during_connect(self):
        "5327 - test changing password during connect"
        conn = await test_env.get_connection_async()
        if await self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")
        sys_random = random.SystemRandom()
        new_password = "".join(
            sys_random.choice(string.ascii_letters) for i in range(20)
        )
        conn = await test_env.get_connection_async(newpassword=new_password)
        conn = await test_env.get_connection_async(password=new_password)
        await conn.changepassword(new_password, test_env.get_main_password())

    async def test_5328_autocommit_during_reexecute(self):
        "5328 - test use of autocommit during reexecute"
        sql = "insert into TestTempTable (IntCol, StringCol1) values (:1, :2)"
        data_to_insert = [(1, "Test String #1"), (2, "Test String #2")]
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        other_conn = await test_env.get_connection_async()
        other_cursor = other_conn.cursor()
        await cursor.execute("truncate table TestTempTable")
        await cursor.execute(sql, data_to_insert[0])
        await other_cursor.execute(
            "select IntCol, StringCol1 from TestTempTable"
        )
        self.assertEqual(await other_cursor.fetchall(), [])
        conn.autocommit = True
        await cursor.execute(sql, data_to_insert[1])
        await other_cursor.execute(
            "select IntCol, StringCol1 from TestTempTable"
        )
        self.assertEqual(await other_cursor.fetchall(), data_to_insert)

    async def test_5329_current_schema(self):
        "5329 - test current_schema is set properly"
        conn = await test_env.get_connection_async()
        self.assertIsNone(conn.current_schema)

        user = test_env.get_main_user().upper()
        proxy_user = test_env.get_proxy_user().upper()
        cursor = conn.cursor()
        await cursor.execute(f"alter session set current_schema={proxy_user}")
        self.assertEqual(conn.current_schema, proxy_user)

        conn.current_schema = user
        self.assertEqual(conn.current_schema, user)

        await cursor.execute(
            "select sys_context('userenv', 'current_schema') from dual"
        )
        (result,) = await cursor.fetchone()
        self.assertEqual(result, user)

    async def test_5330_dbms_output(self):
        "5330 - test dbms_output package"
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        test_string = "Testing DBMS_OUTPUT package"
        await cursor.callproc("dbms_output.enable")
        await cursor.callproc("dbms_output.put_line", [test_string])
        string_var = cursor.var(str)
        number_var = cursor.var(int)
        await cursor.callproc("dbms_output.get_line", (string_var, number_var))
        self.assertEqual(string_var.getvalue(), test_string)

    async def test_5331_calltimeout(self):
        "5331 - test connection call_timeout"
        conn = await test_env.get_connection_async()
        conn.call_timeout = 500  # milliseconds
        self.assertEqual(conn.call_timeout, 500)
        with self.assertRaisesRegex(
            oracledb.DatabaseError, "^DPY-4011:|^DPY-4024:"
        ):
            with conn.cursor() as cursor:
                await cursor.callproc(test_env.get_sleep_proc_name(), [2])

    async def test_5332_connection_repr(self):
        "5332 - test Connection repr()"

        class MyConnection(oracledb.AsyncConnection):
            pass

        conn = await test_env.get_connection_async(conn_class=MyConnection)
        expected_value = (
            f"<{__name__}.TestCase.test_5332_connection_repr."
            f"<locals>.MyConnection to {conn.username}@"
            f"{conn.dsn}>"
        )
        self.assertEqual(repr(conn), expected_value)

        await conn.close()
        expected_value = (
            f"<{__name__}.TestCase.test_5332_connection_repr."
            "<locals>.MyConnection disconnected>"
        )
        self.assertEqual(repr(conn), expected_value)

    async def test_5333_get_write_only_attributes(self):
        "5333 - test getting write-only attributes"
        conn = await test_env.get_connection_async()
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

    async def test_5334_invalid_params(self):
        "5334 - test error for invalid type for params and pool"
        pool = test_env.get_pool_async()
        await pool.close()
        with self.assertRaisesRegex(oracledb.InterfaceError, "^DPY-1002:"):
            await test_env.get_connection_async(pool=pool)
        with self.assertRaises(TypeError):
            await test_env.get_connection_async(
                pool="This isn't an instance of a pool"
            )
        with self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2025:"):
            await oracledb.connect_async(params={"number": 7})

    async def test_5335_instance_name(self):
        "5335 - test connection instance name"
        conn = await test_env.get_connection_async()
        cursor = conn.cursor()
        await cursor.execute(
            """
            select upper(sys_context('userenv', 'instance_name'))
            from dual
            """
        )
        (instance_name,) = await cursor.fetchone()
        self.assertEqual(conn.instance_name.upper(), instance_name)

    @unittest.skipIf(
        test_env.get_server_version() < (23, 0),
        "unsupported server",
    )
    async def test_5337_max_length_password(self):
        "5337 - test maximum allowed length for password"
        conn = await test_env.get_connection_async()
        if await self.is_on_oracle_cloud(conn):
            self.skipTest("passwords on Oracle Cloud are strictly controlled")

        original_password = test_env.get_main_password()
        new_password_32 = "a" * 32
        await conn.changepassword(original_password, new_password_32)
        conn = await test_env.get_connection_async(password=new_password_32)

        new_password_1024 = "a" * 1024
        await conn.changepassword(new_password_32, new_password_1024)
        conn = await test_env.get_connection_async(password=new_password_1024)
        await conn.changepassword(new_password_1024, original_password)

        new_password_1025 = "a" * 1025
        with self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-28218:|^ORA-00972"
        ):
            await conn.changepassword(original_password, new_password_1025)


if __name__ == "__main__":
    test_env.run_test_cases()
