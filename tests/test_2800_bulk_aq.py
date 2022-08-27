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
2800 - Module for testing AQ Bulk enqueue/dequeue
"""

import datetime
import threading
import unittest

import oracledb
import test_env

RAW_QUEUE_NAME = "TEST_RAW_QUEUE"
JSON_QUEUE_NAME = "TEST_JSON_QUEUE"
RAW_PAYLOAD_DATA = [
    "The first message",
    "The second message",
    "The third message",
    "The fourth message",
    "The fifth message",
    "The sixth message",
    "The seventh message",
    "The eighth message",
    "The ninth message",
    "The tenth message",
    "The eleventh message",
    "The twelfth and final message"
]

JSON_DATA_PAYLOAD = [
    [
        2.75,
        True,
        'Ocean Beach',
        b'Some bytes',
        {'keyA': 1.0, 'KeyB': 'Melbourne'},
        datetime.datetime(2022, 8, 1, 0, 0)
    ],
    dict(name="John", age=30, city="New York")
]

@unittest.skipIf(test_env.get_is_thin(), "thin mode doesn't support AQ yet")
class TestCase(test_env.BaseTestCase):

    def __deq_in_thread(self, results):
        with test_env.get_connection() as connection:
            queue = connection.queue(RAW_QUEUE_NAME)
            queue.deqoptions.wait = 10
            queue.deqoptions.navigation = oracledb.DEQ_FIRST_MSG
            while len(results) < len(RAW_PAYLOAD_DATA):
                messages = queue.deqmany(5)
                if not messages:
                    break
                for m in messages:
                    results.append(m.payload.decode())
            connection.commit()

    def test_2800_enq_and_deq(self):
        "2800 - test bulk enqueue and dequeue"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        messages = [self.connection.msgproperties(payload=d) \
                    for d in RAW_PAYLOAD_DATA]
        queue.enqmany(messages)
        messages = queue.deqmany(len(RAW_PAYLOAD_DATA))
        data = [m.payload.decode() for m in messages]
        self.connection.commit()
        self.assertEqual(data, RAW_PAYLOAD_DATA)

    def test_2801_dequeue_empty(self):
        "2801 - test empty bulk dequeue"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        queue.deqoptions.wait = oracledb.DEQ_NO_WAIT
        messages = queue.deqmany(5)
        self.connection.commit()
        self.assertEqual(messages, [])

    def test_2802_deq_with_wait(self):
        "2802 - test bulk dequeue with wait"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        results = []
        thread = threading.Thread(target=self.__deq_in_thread, args=(results,))
        thread.start()
        messages = [self.connection.msgproperties(payload=d) \
                    for d in RAW_PAYLOAD_DATA]
        queue.enqoptions.visibility = oracledb.ENQ_IMMEDIATE
        queue.enqmany(messages)
        thread.join()
        self.assertEqual(results, RAW_PAYLOAD_DATA)

    def test_2803_enq_and_deq_multiple_times(self):
        "2803 - test enqueue and dequeue multiple times"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        data_to_enqueue = RAW_PAYLOAD_DATA
        for num in (2, 6, 4):
            messages = [self.connection.msgproperties(payload=d) \
                        for d in data_to_enqueue[:num]]
            data_to_enqueue = data_to_enqueue[num:]
            queue.enqmany(messages)
        self.connection.commit()
        all_data = []
        for num in (3, 5, 10):
            messages = queue.deqmany(num)
            all_data.extend(m.payload.decode() for m in messages)
        self.connection.commit()
        self.assertEqual(all_data, RAW_PAYLOAD_DATA)

    def test_2804_enq_and_deq_visibility(self):
        "2804 - test visibility option for enqueue and dequeue"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)

        # first test with ENQ_ON_COMMIT (commit required)
        queue.enqoptions.visibility = oracledb.ENQ_ON_COMMIT
        props1 = self.connection.msgproperties(payload="A first message")
        props2 = self.connection.msgproperties(payload="A second message")
        queue.enqmany([props1, props2])
        other_connection = test_env.get_connection()
        other_queue = other_connection.queue(RAW_QUEUE_NAME)
        other_queue.deqoptions.wait = oracledb.DEQ_NO_WAIT
        other_queue.deqoptions.visibility = oracledb.DEQ_ON_COMMIT
        messages = other_queue.deqmany(5)
        self.assertEqual(len(messages), 0)
        self.connection.commit()
        messages = other_queue.deqmany(5)
        self.assertEqual(len(messages), 2)
        other_connection.rollback()

        # second test with ENQ_IMMEDIATE (no commit required)
        queue.enqoptions.visibility = oracledb.ENQ_IMMEDIATE
        other_queue.deqoptions.visibility = oracledb.DEQ_IMMEDIATE
        queue.enqmany([props1, props2])
        messages = other_queue.deqmany(5)
        self.assertEqual(len(messages), 4)
        other_connection.rollback()
        messages = other_queue.deqmany(5)
        self.assertEqual(len(messages), 0)

    def test_2805_messages_with_no_payload(self):
        "2805 - test error for messages with no payload"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        messages = [self.connection.msgproperties() \
                    for d in RAW_PAYLOAD_DATA]
        self.assertRaisesRegex(oracledb.ProgrammingError, "^DPY-2000:",
                               queue.enqmany, messages)

    def test_2806_verify_msgid(self):
        "2806 - verify that the msgid property is returned correctly"
        queue = self.get_and_clear_queue(RAW_QUEUE_NAME)
        messages = [self.connection.msgproperties(payload=d) \
                    for d in RAW_PAYLOAD_DATA]
        queue.enqmany(messages)
        self.cursor.execute("select msgid from raw_queue_tab")
        actual_msgids = set(m for m, in self.cursor)
        msgids = set(m.msgid for m in messages)
        self.assertEqual(msgids, actual_msgids)
        messages = queue.deqmany(len(RAW_PAYLOAD_DATA))
        msgids = set(m.msgid for m in messages)
        self.assertEqual(msgids, actual_msgids)

    def test_2807_json_enq_deq(self):
        "4800 - test enqueuing and dequeuing JSON message"
        queue = self.get_and_clear_queue(JSON_QUEUE_NAME, "JSON")
        props = [self.connection.msgproperties(payload=d) \
                 for d in JSON_DATA_PAYLOAD]
        queue.enqmany(props)
        self.connection.commit()
        queue.deqoptions.wait = oracledb.DEQ_NO_WAIT
        messages = queue.deqmany(5)
        actual_data = [m.payload for m in messages]
        self.assertEqual(actual_data, JSON_DATA_PAYLOAD)

if __name__ == "__main__":
    test_env.run_test_cases()
