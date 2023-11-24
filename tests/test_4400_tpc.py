# -----------------------------------------------------------------------------
# Copyright (c) 2021, 2023, Oracle and/or its affiliates.
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
4400 - Module for testing TPC (two-phase commit) transactions.
"""

import unittest

import oracledb
import test_env


@unittest.skipIf(
    test_env.get_is_thin(), "thin mode doesn't support two-phase commit yet"
)
class TestCase(test_env.BaseTestCase):
    def test_4400_tpc_with_rolback(self):
        "4400 - test begin, prepare, roll back global transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(3900, "txn3900", "branchId")
        self.conn.tpc_begin(xid)
        self.assertEqual(self.conn.tpc_prepare(), False)
        self.conn.tpc_begin(xid)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'tesName')
            """
        )
        self.assertEqual(self.conn.tpc_prepare(), True)
        self.conn.tpc_rollback()
        self.cursor.execute("select count(*) from TestTempTable")
        (count,) = self.cursor.fetchone()
        self.assertEqual(count, 0)

    def test_4401_tpc_with_commit(self):
        "4401 - test begin, prepare, commit global transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(3901, "txn3901", "branchId")
        self.conn.tpc_begin(xid)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'tesName')
            """
        )
        self.assertEqual(self.conn.tpc_prepare(), True)
        self.conn.tpc_commit()
        self.cursor.execute("select IntCol, StringCol1 from TestTempTable")
        self.assertEqual(self.cursor.fetchall(), [(1, "tesName")])

    def test_4402_tpc_multiple_transactions(self):
        "4402 - test multiple global transactions on the same connection"
        self.cursor.execute("truncate table TestTempTable")
        xid1 = self.conn.xid(3902, "txn3902", "branch1")
        xid2 = self.conn.xid(3902, "txn3902", "branch2")
        self.conn.tpc_begin(xid1)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'tesName')
            """
        )
        self.conn.tpc_end()
        self.conn.tpc_begin(xid2)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (2, 'tesName')
            """
        )
        self.conn.tpc_end()
        needs_commit1 = self.conn.tpc_prepare(xid1)
        needs_commit2 = self.conn.tpc_prepare(xid2)
        if needs_commit1:
            self.conn.tpc_commit(xid1)
        if needs_commit2:
            self.conn.tpc_commit(xid2)
        self.cursor.execute(
            "select IntCol, StringCol1 from TestTempTable order by IntCol"
        )
        expected_rows = [(1, "tesName"), (2, "tesName")]
        self.assertEqual(self.cursor.fetchall(), expected_rows)

    def test_4403_rollback_with_xid(self):
        "4403 - test rollback with parameter xid"
        self.cursor.execute("truncate table TestTempTable")
        xid1 = self.conn.xid(3901, "txn3901", "branch1")
        xid2 = self.conn.xid(3902, "txn3902", "branch2")
        for count, xid in enumerate([xid1, xid2]):
            self.conn.tpc_begin(xid)
            self.cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (:id, 'tesName')
                """,
                id=count,
            )
            self.conn.tpc_end()
        self.conn.tpc_rollback(xid1)

        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24756", self.conn.tpc_prepare, xid1
        )
        needs_commit = self.conn.tpc_prepare(xid2)
        if needs_commit:
            self.conn.tpc_commit(xid2)
        self.cursor.execute(
            "select IntCol, StringCol1 from TestTempTable order by IntCol"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, "tesName")])

    def test_4404_tpc_begin_resume(self):
        "4404 - test resuming a transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid1 = self.conn.xid(3939, "txn3939", "branch39")
        xid2 = self.conn.xid(3940, "txn3940", "branch40")
        values = [[xid1, (1, "User Info")], [xid2, (2, "Other User Info")]]
        for xid, data in values:
            self.conn.tpc_begin(xid)
            self.cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, :2)
                """,
                data,
            )
            self.conn.tpc_end()
        for xid, data in values:
            self.conn.tpc_begin(xid, oracledb.TPC_BEGIN_RESUME)
            self.cursor.execute("select IntCol, StringCol1 from TestTempTable")
            (res,) = self.cursor.fetchall()
            self.assertEqual(res, data)
            self.conn.tpc_rollback(xid)

    def test_4405_tpc_begin_promote(self):
        "4405 - test promoting a local transaction to a tpc transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(3941, "txn3941", "branch41")
        values = (1, "String 1")
        self.cursor.execute(
            "insert into TestTempTable (IntCol, StringCol1) values (:1, :2)",
            values,
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24776", self.conn.tpc_begin, xid
        )
        self.conn.tpc_begin(xid, oracledb.TPC_BEGIN_PROMOTE)
        self.cursor.execute("select IntCol, StringCol1 from TestTempTable")
        (res,) = self.cursor.fetchall()
        self.assertEqual(res, values)
        self.conn.tpc_rollback(xid)

    def test_4406_tpc_end_with_xid(self):
        "4406 - test ending a transaction with parameter xid"
        self.cursor.execute("truncate table TestTempTable")
        xid1 = self.conn.xid(4406, "txn4406a", "branch3")
        xid2 = self.conn.xid(4406, "txn4406b", "branch4")
        self.conn.tpc_begin(xid1)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'test4406a')
            """
        )
        self.conn.tpc_begin(xid2)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24758:", self.conn.tpc_end, xid1
        )
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (2, 'test4406b')
            """
        )
        self.conn.tpc_end(xid2)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-25352:", self.conn.tpc_end, xid1
        )
        self.conn.tpc_rollback(xid1)
        self.conn.tpc_rollback(xid2)

    def test_4407_tpc_recover(self):
        "4407 - test tpc_recover()"
        self.cursor.execute("truncate table TestTempTable")
        n_xids = 10
        for i in range(n_xids):
            xid = self.conn.xid(4407 + i, f"txn4407{i}", f"branch{i}")
            self.conn.tpc_begin(xid)
            self.cursor.execute(
                """
                insert into TestTempTable (IntCol, StringCol1)
                values (:1, 'test4407')
                """,
                [i + 1],
            )
            self.conn.tpc_prepare(xid)
        recovers = self.conn.tpc_recover()
        self.assertEqual(len(recovers), n_xids)

        self.cursor.execute("select * from DBA_PENDING_TRANSACTIONS")
        self.assertEqual(self.cursor.fetchall(), recovers)

        for format_id, txn, branch in recovers:
            if format_id % 2 == 0:
                xid = self.conn.xid(format_id, txn, branch)
                self.conn.tpc_commit(xid)
        recovers = self.conn.tpc_recover()
        self.assertEqual(len(recovers), n_xids // 2)

        for format_id, txn, branch in recovers:
            xid = self.conn.xid(format_id, txn, branch)
            self.conn.tpc_rollback(xid)
        recovers = self.conn.tpc_recover()
        self.assertEqual(len(recovers), 0)

    def test_4408_tpc_recover_read_only(self):
        "4408 - test tpc_recover() with read-only transaction"
        self.cursor.execute("truncate table TestTempTable")
        for i in range(4):
            xid = self.conn.xid(4408 + i, f"txn4408{i}", f"branch{i}")
            self.conn.tpc_begin(xid)
            self.cursor.execute("select * from TestTempTable")
            self.conn.tpc_prepare(xid)
        recovers = self.conn.tpc_recover()
        self.assertEqual(len(recovers), 0)

    def test_4409_tpc_commit_one_phase(self):
        "4409 - test tpc_commit() with one_phase parameter"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4409, "txn4409", "branch1")
        self.conn.tpc_begin(xid)
        values = (1, "test4409")
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (:1, :2)
            """,
            values,
        )
        self.cursor.execute("select IntCol, StringCol1 from TestTempTable")
        self.conn.tpc_commit(xid, one_phase=True)
        self.assertEqual(self.cursor.fetchall(), [values])

    def test_4410_tpc_commit_one_phase_negative(self):
        "4410 - test negative cases for tpc_commit()"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4410, "txn4410", "branch1")
        self.conn.tpc_begin(xid)
        self.cursor.execute(
            """
            insert into TestTempTable (IntCol, StringCol1)
            values (1, 'test4410')
            """
        )
        self.assertRaises(TypeError, self.conn.tpc_commit, "invalid xid")
        self.conn.tpc_prepare(xid)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-02053:",
            self.conn.tpc_commit,
            xid,
            one_phase=True,
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24756:", self.conn.tpc_commit, xid
        )
        self.conn.tpc_rollback(xid)

    def test_4411_tpc_begin_negative(self):
        "4411 - test starting an already created transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4411, "txn4411", "branch1")
        self.conn.tpc_begin(xid)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-24757:",
            self.conn.tpc_begin,
            xid,
            oracledb.TPC_BEGIN_NEW,
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-24797:",
            self.conn.tpc_begin,
            xid,
            oracledb.TPC_BEGIN_PROMOTE,
        )
        self.conn.tpc_end()
        for flag in [oracledb.TPC_BEGIN_NEW, oracledb.TPC_BEGIN_PROMOTE]:
            self.assertRaisesRegex(
                oracledb.DatabaseError,
                "^ORA-24757:",
                self.conn.tpc_begin,
                xid,
                flag,
            )
        self.conn.tpc_rollback(xid)

    def test_4412_resuming_prepared_txn_negative(self):
        "4412 - test resuming a prepared transaction"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4412, "txn4412", "branch1")
        self.conn.tpc_begin(xid)
        self.conn.tpc_prepare(xid)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-24756",
            self.conn.tpc_begin,
            xid,
            oracledb.TPC_BEGIN_RESUME,
        )

    def test_4413_tpc_begin_end_params_negative(self):
        "4413 - test tpc_begin and tpc_end with invalid parameters"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4413, "txn4413", "branch1")
        test_values = [
            (self.conn.tpc_begin, "^ORA-24759:"),
            (self.conn.tpc_end, "^DPI-1002:"),
        ]
        for tpc_function, error_code in test_values:
            self.assertRaises(TypeError, tpc_function, "invalid xid")
            self.assertRaises(TypeError, tpc_function, xid, "invalid flag")
            self.assertRaisesRegex(
                oracledb.DatabaseError, error_code, tpc_function, xid, 70
            )
        self.conn.tpc_rollback(xid)

    def test_4414_implicit_commit_negative(self):
        "4414 - test commiting transaction without tpc_commit"
        xid = self.conn.xid(4414, "txn4409", "branch1")
        self.conn.tpc_begin(xid)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-02089",
            self.cursor.execute,
            "truncate table TestTempTable",
        )

    def test_4415_commit_is_not_needed(self):
        "4415 - test tpc_commit when a commit is not needed"
        xid = self.conn.xid(4416, "txn4416", "branch1")
        self.conn.tpc_begin(xid)
        self.cursor.execute("select * from TestTempTable")
        self.conn.tpc_end(xid)
        self.conn.tpc_prepare(xid)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-24756:", self.conn.tpc_commit, xid
        )

    def test_4416_transaction_in_progress(self):
        "4416 - test transaction_in_progress"
        self.cursor.execute("truncate table TestTempTable")
        xid = self.conn.xid(4415, "txn4415", "branch1")
        self.assertFalse(self.conn.transaction_in_progress)

        self.conn.tpc_begin(xid)
        self.assertTrue(self.conn.transaction_in_progress)
        self.cursor.execute("insert into TestTempTable (IntCol) values (2)")

        self.conn.tpc_end(xid)
        self.assertFalse(self.conn.transaction_in_progress)

        self.conn.tpc_prepare(xid)
        self.assertFalse(self.conn.transaction_in_progress)

        self.conn.tpc_commit(xid)
        self.assertFalse(self.conn.transaction_in_progress)


if __name__ == "__main__":
    test_env.run_test_cases()
