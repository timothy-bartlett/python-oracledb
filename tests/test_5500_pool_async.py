# -----------------------------------------------------------------------------
# Copyright (c) 2023, 2024, Oracle and/or its affiliates.
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
5500 - Module for testing pools with asyncio
"""

import asyncio
import unittest

import oracledb
import test_env


@unittest.skipUnless(
    test_env.get_is_thin(), "asyncio not supported in thick mode"
)
class TestCase(test_env.BaseAsyncTestCase):
    require_connection = False

    async def __connect_and_drop(self, pool):
        async with pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute("select count(*) from TestNumbers")
            (count,) = await cursor.fetchone()
            self.assertEqual(count, 10)

    async def __connect_and_generate_error(self, pool):
        async with pool.acquire() as conn:
            cursor = conn.cursor()
            with self.assertRaisesFullCode("ORA-01476"):
                await cursor.execute("select 1 / 0 from dual")

    async def __verify_connection(
        self, connection, expected_user, expected_proxy_user=None
    ):
        cursor = connection.cursor()
        await cursor.execute(
            """
            select
                sys_context('userenv', 'session_user'),
                sys_context('userenv', 'proxy_user')
            from dual
            """
        )
        actual_user, actual_proxy_user = await cursor.fetchone()
        self.assertEqual(actual_user, expected_user.upper())
        self.assertEqual(
            actual_proxy_user,
            expected_proxy_user and expected_proxy_user.upper(),
        )
        await connection.close()

    async def test_5500(self):
        "5500 - test getting default pool parameters"
        pool = test_env.get_pool_async()
        self.assertEqual(pool.busy, 0)
        self.assertEqual(pool.dsn, test_env.get_connect_string())
        self.assertEqual(pool.getmode, oracledb.POOL_GETMODE_WAIT)
        self.assertTrue(pool.homogeneous)
        self.assertEqual(pool.increment, 1)
        self.assertEqual(pool.max, 2)
        self.assertEqual(pool.max_lifetime_session, 0)
        self.assertEqual(pool.min, 1)
        self.assertEqual(pool.ping_interval, 60)
        self.assertEqual(pool.stmtcachesize, oracledb.defaults.stmtcachesize)
        self.assertEqual(pool.thin, True)
        self.assertEqual(pool.timeout, 0)
        self.assertEqual(pool.username, test_env.get_main_user())

    async def test_5501(self):
        "5501 - test setting pool attributes"
        pool = test_env.get_pool_async()
        test_values = [
            ((11, 2), "ping_interval", 30),
            ((11, 2), "stmtcachesize", 100),
            ((11, 2), "timeout", 10),
            ((12, 2), "getmode", oracledb.POOL_GETMODE_TIMEDWAIT),
            ((12, 1), "max_lifetime_session", 3),
        ]
        for version, attr_name, value in test_values:
            if test_env.get_client_version() >= version:
                setattr(pool, attr_name, value)
                self.assertEqual(getattr(pool, attr_name), value)
                self.assertRaises(
                    TypeError, setattr, pool, attr_name, "invalid value"
                )

    async def test_5502(self):
        "5502 - connection rolls back before released back to the pool"
        pool = test_env.get_pool_async()
        conn = await pool.acquire()
        cursor = conn.cursor()
        await cursor.execute("truncate table TestTempTable")
        await cursor.execute("insert into TestTempTable (IntCol) values (1)")
        cursor.close()
        await pool.release(conn)
        pool = test_env.get_pool_async()
        conn = await pool.acquire()
        cursor = conn.cursor()
        await cursor.execute("select count(*) from TestTempTable")
        (count,) = await cursor.fetchone()
        self.assertEqual(count, 0)
        await conn.close()

    async def test_5503(self):
        "5503 - test session pool with multiple coroutines"
        pool = test_env.get_pool_async(min=5, max=20, increment=2)
        coroutines = [self.__connect_and_drop(pool) for i in range(20)]
        await asyncio.gather(*coroutines)
        await pool.close()

    async def test_5504(self):
        "5504 - test session pool with multiple coroutines (with errors)"
        pool = test_env.get_pool_async(min=5, max=20, increment=2)
        coroutines = [
            self.__connect_and_generate_error(pool) for i in range(20)
        ]
        await asyncio.gather(*coroutines)
        await pool.close()

    @unittest.skipIf(test_env.get_is_drcp(), "not supported with DRCP")
    async def test_5505(self):
        "5505 - test session pool with various types of purity"
        pool = test_env.get_pool_async(min=1, max=8, increment=1)

        # get connection and set the action
        action = "TEST_ACTION"
        conn = await pool.acquire()
        conn.action = action
        cursor = conn.cursor()
        await cursor.execute("select 1 from dual")
        cursor.close()
        await pool.release(conn)
        self.assertEqual(pool.opened, 1, "opened (1)")

        # verify that the connection still has the action set on it
        conn = await pool.acquire()
        cursor = conn.cursor()
        await cursor.execute(
            "select sys_context('userenv', 'action') from dual"
        )
        (result,) = await cursor.fetchone()
        self.assertEqual(result, action)
        cursor.close()
        await pool.release(conn)
        self.assertEqual(pool.opened, 1, "opened (2)")

        # get a new connection with new purity (should not have state)
        conn = await pool.acquire(purity=oracledb.PURITY_NEW)
        cursor = conn.cursor()
        await cursor.execute(
            "select sys_context('userenv', 'action') from dual"
        )
        (result,) = await cursor.fetchone()
        self.assertIsNone(result)
        cursor.close()
        await pool.release(conn)

    async def test_5506(self):
        "5506 - test dropping/closing a connection from the pool"
        pool = test_env.get_pool_async(min=1, max=5, increment=2)
        conns1 = [await pool.acquire() for _ in range(2)]
        conns2 = [await oracledb.connect_async(pool=pool) for _ in range(3)]
        self.assertEqual(pool.busy, 5)
        self.assertEqual(pool.opened, 5)

        for conn in conns1:
            await pool.drop(conn)
        self.assertEqual(pool.busy, 3)
        self.assertEqual(pool.opened, 3)

        for conn in conns2:
            await conn.close()
        self.assertEqual(pool.busy, 0)
        self.assertEqual(pool.opened, 3)
        await pool.close()

    async def test_5507(self):
        "5507 - test to ensure pure connections are being created correctly"
        pool = test_env.get_pool_async(min=1, max=2, increment=1)
        conn1 = await pool.acquire()
        conn2 = await pool.acquire()
        self.assertEqual(pool.opened, 2, "opened (1)")
        await pool.release(conn1)
        await pool.release(conn2)
        conn3 = await pool.acquire(purity=oracledb.PURITY_NEW)
        self.assertEqual(pool.opened, 2, "opened (2)")
        await pool.release(conn3)
        await pool.close()

    async def test_5508(self):
        "5508 - test closing a pool normally with no connections checked out"
        pool = test_env.get_pool_async(min=1, max=8, increment=1)
        await pool.close()

    async def test_5509(self):
        "5509 - test closing a pool normally with connections checked out"
        pool = test_env.get_pool_async(min=1, max=8, increment=1)
        async with pool.acquire():
            with self.assertRaisesFullCode("DPY-1005"):
                await pool.close()

    async def test_5510(self):
        "5510 - test closing a pool forcibly"
        pool = test_env.get_pool_async(min=1, max=8, increment=1)
        async with pool.acquire():
            await pool.close(force=True)

    async def test_5511(self):
        "5511 - using the pool after it is closed raises an exception"
        pool = test_env.get_pool_async(min=1, max=8, increment=1)
        await pool.close()
        with self.assertRaisesFullCode("DPY-1002"):
            await pool.acquire()

    async def test_5512(self):
        "5512 - using the pool beyond max limit raises an error"
        pool = test_env.get_pool_async(min=1, max=2, increment=1)
        async with pool.acquire(), pool.acquire():
            pool.getmode = oracledb.POOL_GETMODE_NOWAIT
            with self.assertRaisesFullCode("DPY-4005"):
                await pool.acquire()
        await pool.close()

    async def test_5513(self):
        "5513 - callable session callback is executed for new connections"

        class Counter:
            num_calls = 0

            @classmethod
            async def session_callback(cls, conn, requested_tag):
                cls.num_calls += 1

        pool = test_env.get_pool_async(
            min=1,
            max=2,
            increment=1,
            session_callback=Counter.session_callback,
        )
        async with pool.acquire(), pool.acquire():
            pass
        async with pool.acquire(), pool.acquire():
            pass
        self.assertEqual(Counter.num_calls, 2)
        await pool.close()

    @unittest.skipIf(test_env.get_is_drcp(), "not supported with DRCP")
    async def test_5514(self):
        "5514 - drop the pooled connection on receiving dead connection error"
        admin_conn = await test_env.get_admin_connection_async()
        pool = test_env.get_pool_async(min=2, max=2, increment=2)

        # acquire connections from the pool and kill all the sessions
        with admin_conn.cursor() as admin_cursor:
            for conn in [await pool.acquire() for i in range(2)]:
                with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        select
                            dbms_debug_jdwp.current_session_id,
                            dbms_debug_jdwp.current_session_serial
                        from dual
                        """
                    )
                    sid, serial = await cursor.fetchone()
                    sql = f"alter system kill session '{sid},{serial}'"
                    await admin_cursor.execute(sql)
                await conn.close()
        self.assertEqual(pool.opened, 2)

        # when try to re-use the killed sessions error will be raised;
        # release all such connections
        for conn in [await pool.acquire() for i in range(2)]:
            with conn.cursor() as cursor:
                with self.assertRaisesFullCode("DPY-4011"):
                    await cursor.execute("select user from dual")
            await conn.close()
        self.assertEqual(pool.opened, 0)

        # if a free connection is available, it can be used; otherwise a new
        # connection will be created
        for conn in [await pool.acquire() for i in range(2)]:
            with conn.cursor() as cursor:
                await cursor.execute("select user from dual")
                (user,) = await cursor.fetchone()
                self.assertEqual(user, test_env.get_main_user().upper())
            await conn.close()
        self.assertEqual(pool.opened, 2)
        await pool.close()

    async def test_5515(self):
        "5515 - acquire a connection from an empty pool (min=0)"
        pool = test_env.get_pool_async(min=0, max=2, increment=2)
        async with pool.acquire() as conn:
            with conn.cursor() as cursor:
                await cursor.execute("select user from dual")
                (result,) = await cursor.fetchone()
                self.assertEqual(result, test_env.get_main_user().upper())
        await pool.close()

    async def test_5516(self):
        "5516 - get different object types from different connections"
        pool = test_env.get_pool_async(min=1, max=2, increment=1)
        async with pool.acquire() as conn:
            typ = await conn.gettype("UDT_SUBOBJECT")
            self.assertEqual(typ.name, "UDT_SUBOBJECT")
        async with pool.acquire() as conn:
            typ = await conn.gettype("UDT_OBJECTARRAY")
            self.assertEqual(typ.name, "UDT_OBJECTARRAY")
        await pool.close()

    async def test_5517(self):
        "5517 - test creating a pool using a proxy user"
        user_str = f"{test_env.get_main_user()}[{test_env.get_proxy_user()}]"
        pool = test_env.get_pool_async(user=user_str)
        await self.__verify_connection(
            await pool.acquire(),
            test_env.get_proxy_user(),
            test_env.get_main_user(),
        )
        await pool.close()

    @unittest.skipIf(test_env.get_is_drcp(), "not supported with DRCP")
    async def test_5518(self):
        "5518 - test acquiring conn from pool in LIFO order"
        pool = test_env.get_pool_async(min=5, max=10, increment=1)
        sql = "select sys_context('userenv', 'sid') from dual"
        conns = [await pool.acquire() for i in range(3)]
        sids = []
        for conn in conns:
            with conn.cursor() as cursor:
                await cursor.execute(sql)
                (sid,) = await cursor.fetchone()
                sids.append(sid)
        await conns[1].close()
        await conns[2].close()
        await conns[0].close()

        async with pool.acquire() as conn:
            with conn.cursor() as cursor:
                await cursor.execute(sql)
                (sid,) = await cursor.fetchone()
                self.assertEqual(sid, sids[0], "not LIFO")
        await pool.close()

    async def test_5519(self):
        "5519 - verify that dynamic pool cannot have an increment of zero"
        pool = test_env.get_pool_async(min=1, max=3, increment=0)
        self.assertEqual(pool.increment, 1)
        async with pool.acquire(), pool.acquire():
            pass
        await pool.close()

    async def test_5520(self):
        "5520 - verify that static pool can have an increment of zero"
        pool = test_env.get_pool_async(min=1, max=1, increment=0)
        self.assertEqual(pool.increment, 0)
        async with pool.acquire():
            pass
        await pool.close()

    async def test_5521(self):
        "5521 - verify that connection with different cclass is reused"
        cclass = "cclass2431"
        pool = test_env.get_pool_async(min=1, max=1)
        # ignore the first acquire which, depending on the speed with which the
        # minimum connections are created, may create a connection that is
        # discarded; instead, use the second acquire which should remain in the
        # pool
        async with pool.acquire(cclass=cclass) as conn:
            pass
        async with pool.acquire(cclass=cclass) as conn:
            with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    select
                        dbms_debug_jdwp.current_session_id || ',' ||
                        dbms_debug_jdwp.current_session_serial
                    from dual
                    """
                )
                (sid_serial,) = await cursor.fetchone()
        async with pool.acquire(cclass=cclass) as conn:
            with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    select
                        dbms_debug_jdwp.current_session_id || ',' ||
                        dbms_debug_jdwp.current_session_serial
                    from dual
                    """
                )
                (next_sid_serial,) = await cursor.fetchone()
                self.assertEqual(next_sid_serial, sid_serial)
        self.assertEqual(pool.opened, 1)
        await pool.close()

    async def test_5522(self):
        "5522 - test creating a pool invalid params"
        with self.assertRaisesFullCode("DPY-2027"):
            oracledb.create_pool_async(params="bad params")

    async def test_5523(self):
        "5523 - test releasing and dropping an invalid connection"
        pool = test_env.get_pool_async()
        with self.assertRaises(TypeError):
            await pool.release("invalid connection")
        with self.assertRaises(TypeError):
            await pool.drop("invalid connection")

    async def test_5524(self):
        "5524 - test creating a pool with invalid pool_class"
        with self.assertRaisesFullCode("DPY-2026"):
            oracledb.create_pool_async(pool_class=int)

    async def test_5525(self):
        "5525 - test creating a pool with a subclassed connection type"

        class MyConnection(oracledb.AsyncConnection):
            pass

        pool = test_env.get_pool_async(connectiontype=MyConnection)
        async with pool.acquire() as conn:
            self.assertIsInstance(conn, MyConnection)

    async def test_5526(self):
        "5526 - test creating a pool with a subclassed pool type"

        class MyPool(oracledb.AsyncConnectionPool):
            pass

        pool = test_env.get_pool_async(pool_class=MyPool)
        self.assertIsInstance(pool, MyPool)


if __name__ == "__main__":
    test_env.run_test_cases()
