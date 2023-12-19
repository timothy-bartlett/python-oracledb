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
3400 - Module for testing Simple Oracle Document Access (SODA) Collections
"""

import unittest

import oracledb
import test_env


@unittest.skipIf(
    test_env.skip_soda_tests(), "unsupported client/server combination"
)
class TestCase(test_env.BaseTestCase):
    def __normalize_docs(self, docs):
        """
        Remove the embedded OID added in Oracle Database 23c, if found, in
        order to ease comparison.
        """
        for doc in docs:
            if doc is not None and "_id" in doc:
                del doc["_id"]

    def __test_skip(self, coll, num_to_skip, expected_content):
        filter_spec = {"$orderby": [{"path": "name", "order": "desc"}]}
        doc = coll.find().filter(filter_spec).skip(num_to_skip).getOne()
        content = doc.getContent() if doc is not None else None
        self.__normalize_docs([content])
        self.assertEqual(content, expected_content)

    def test_3400_invalid_json(self):
        "3400 - test inserting invalid JSON value into SODA collection"
        invalid_json = "{testKey:testValue}"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("InvalidJSON")
        doc = soda_db.createDocument(invalid_json)
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-40780:|^ORA-02290:",
            coll.insertOne,
            doc,
        )
        coll.drop()

    def test_3401_insert_documents(self):
        "3401 - test inserting documents into a SODA collection"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestInsertDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "George", "age": 47},
            {"name": "Susan", "age": 39},
            {"name": "John", "age": 50},
            {"name": "Jill", "age": 54},
        ]
        inserted_keys = []
        for value in values_to_insert:
            doc = coll.insertOneAndGet(value)
            inserted_keys.append(doc.key)
        self.conn.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        for key, value in zip(inserted_keys, values_to_insert):
            doc = coll.find().key(key).getOne().getContent()
            self.__normalize_docs([doc])
            self.assertEqual(doc, value)
        coll.drop()

    def test_3402_skip_documents(self):
        "3402 - test skipping documents in a SODA collection"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestSkipDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "Anna", "age": 62},
            {"name": "Mark", "age": 37},
            {"name": "Martha", "age": 43},
            {"name": "Matthew", "age": 28},
        ]
        for value in values_to_insert:
            coll.insertOne(value)
        self.conn.commit()
        self.__test_skip(coll, 0, values_to_insert[3])
        self.__test_skip(coll, 1, values_to_insert[2])
        self.__test_skip(coll, 3, values_to_insert[0])
        self.__test_skip(coll, 4, None)
        self.__test_skip(coll, 125, None)

    def test_3403_replace_document(self):
        "3403 - test replace documents in SODA collection"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestReplaceDoc")
        coll.find().remove()
        content = {"name": "John", "address": {"city": "Sydney"}}
        doc = coll.insertOneAndGet(content)
        new_content = {"name": "John", "address": {"city": "Melbourne"}}
        replaced = coll.find().key(doc.key).replaceOne(new_content)
        self.assertTrue(replaced)
        self.conn.commit()
        doc = coll.find().key(doc.key).getOne().getContent()
        self.__normalize_docs([doc])
        self.assertEqual(doc, new_content)
        coll.drop()

    def test_3404_search_documents_with_content(self):
        "3404 - test search documents with different QBEs"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestSearchDocContent")
        coll.find().remove()
        data = [
            {
                "name": "John",
                "age": 22,
                "birthday": "2000-12-15",
                "locations": [{"city": "Bangalore"}, {"city": "Other"}],
            },
            {
                "name": "Johnson",
                "age": 45,
                "birthday": "1978-02-03",
                "locations": [{"city": "Banaras"}, {"city": "Manhattan"}],
            },
            {
                "name": "William",
                "age": 32,
                "birthday": "1991-05-17",
                "locations": {"city": "New Banaras"},
            },
        ]
        coll.insertMany(data)
        self.conn.commit()
        filter_specs = [
            ({"name": {"$like": "J%n"}}, 2),
            ({"name": {"$regex": ".*[ho]n"}}, 2),
            ("""{"locations.city": {"$regex": "^Ban.*"}}""", 2),
            ({"birthday": {"$date": {"$gt": "2000-01-01"}}}, 1),
            ({"birthday": {"$date": "2000-12-15"}}, 1),
            ({"age": {"$gt": 18}}, 3),
            ({"age": {"$lt": 25}}, 1),
            (
                {
                    "$or": [
                        {"age": {"$gt": 50}},
                        {"locations[*].city": {"$like": "%Ban%"}},
                    ]
                },
                3,
            ),
            (
                {
                    "$and": [
                        {"age": {"$gt": 40}},
                        {"locations[0 to 1].city": {"$like": "%aras"}},
                    ]
                },
                1,
            ),
            ({"name": {"$hasSubstring": "John"}}, 2),
            ({"name": {"$instr": "John"}}, 2),
            ({"name": {"$startsWith": "John"}}, 2),
            ({"name": {"$upper": {"$startsWith": "JO"}}}, 2),
            ({"age": {"$not": {"$eq": 22}}}, 2),
            ({"age": {"$not": {"$lt": 30, "$gt": 10}}}, 2),
            ({"locations": {"$type": "array"}}, 2),
        ]
        for filter_spec, expected_count in filter_specs:
            self.assertEqual(
                coll.find().filter(filter_spec).count(),
                expected_count,
                filter_spec,
            )
        coll.drop()

    def test_3405_document_remove(self):
        "3405 - test removing documents"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestRemoveDocs")
        coll.find().remove()
        data = [
            {"name": "John", "address": {"city": "Bangalore"}},
            {"name": "Johnson", "address": {"city": "Banaras"}},
            {"name": "Joseph", "address": {"city": "Mangalore"}},
            {"name": "Jibin", "address": {"city": "Secunderabad"}},
            {"name": "Andrew", "address": {"city": "Hyderabad"}},
            {"name": "Matthew", "address": {"city": "Mumbai"}},
        ]
        docs = [coll.insertOneAndGet(v) for v in data]
        self.assertEqual(coll.find().key(docs[3].key).remove(), 1)
        self.assertEqual(coll.find().count(), len(data) - 1)
        search_results = coll.find().filter({"name": {"$like": "Jibin"}})
        self.assertEqual(search_results.count(), 0)
        self.assertEqual(
            coll.find().filter({"name": {"$like": "John%"}}).remove(), 2
        )
        self.assertEqual(coll.find().count(), len(data) - 3)
        self.assertEqual(
            coll.find().filter({"name": {"$regex": "J.*"}}).remove(), 1
        )
        self.assertEqual(coll.find().count(), len(data) - 4)
        self.conn.commit()
        coll.drop()

    def test_3406_create_and_drop_index(self):
        "3406 - test create and drop Index"
        index_name = "TestIndexes_ix_1"
        index_spec = {
            "name": index_name,
            "fields": [
                {"path": "address.city", "datatype": "string", "order": "asc"}
            ],
        }
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestIndexes")
        coll.find().remove()
        self.conn.commit()
        coll.dropIndex(index_name)
        coll.createIndex(index_spec)
        self.assertRaises(TypeError, coll.createIndex, 3)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-40733:", coll.createIndex, index_spec
        )
        self.assertTrue(coll.dropIndex(index_name))
        self.assertFalse(coll.dropIndex(index_name))
        coll.drop()

    def test_3407_get_documents(self):
        "3407 - test getting documents from Collection"
        self.conn.autocommit = True
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestGetDocs")
        coll.find().remove()
        data = [
            {"name": "John", "address": {"city": "Bangalore"}},
            {"name": "Johnson", "address": {"city": "Banaras"}},
            {"name": "Joseph", "address": {"city": "Mangalore"}},
            {"name": "Jibin", "address": {"city": "Secunderabad"}},
            {"name": "Andrew", "address": {"city": "Hyderabad"}},
        ]
        inserted_keys = list(sorted(coll.insertOneAndGet(v).key for v in data))
        fetched_keys = list(
            sorted(doc.key for doc in coll.find().getDocuments())
        )
        self.assertEqual(fetched_keys, inserted_keys)
        coll.drop()

    def test_3408_cursor(self):
        "3408 - test fetching documents from a cursor"
        self.conn.autocommit = True
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestFindViaCursor")
        coll.find().remove()
        data = [
            {"name": "John", "address": {"city": "Bangalore"}},
            {"name": "Johnson", "address": {"city": "Banaras"}},
            {"name": "Joseph", "address": {"city": "Mangalore"}},
        ]
        inserted_keys = list(sorted(coll.insertOneAndGet(v).key for v in data))
        fetched_keys = list(sorted(doc.key for doc in coll.find().getCursor()))
        self.assertEqual(fetched_keys, inserted_keys)
        coll.drop()

    def test_3409_multiple_document_remove(self):
        "3409 - test removing multiple documents using multiple keys"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestRemoveMultipleDocs")
        coll.find().remove()
        data = [
            {"name": "John", "address": {"city": "Bangalore"}},
            {"name": "Johnson", "address": {"city": "Banaras"}},
            {"name": "Joseph", "address": {"city": "Mangalore"}},
            {"name": "Jibin", "address": {"city": "Secunderabad"}},
            {"name": "Andrew", "address": {"city": "Hyderabad"}},
            {"name": "Matthew", "address": {"city": "Mumbai"}},
        ]
        docs = [coll.insertOneAndGet(v) for v in data]
        keys = [docs[i].key for i in (1, 3, 5)]
        num_removed = coll.find().keys(keys).remove()
        self.assertEqual(num_removed, len(keys))
        self.assertEqual(coll.find().count(), len(data) - len(keys))
        self.conn.commit()
        coll.drop()

    def test_3410_document_version(self):
        "3410 - test using version to get documents and remove them"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestDocumentVersion")
        coll.find().remove()
        content = {"name": "John", "address": {"city": "Bangalore"}}
        inserted_doc = coll.insertOneAndGet(content)
        key = inserted_doc.key
        version = inserted_doc.version
        doc = coll.find().key(key).version(version).getOne().getContent()
        self.__normalize_docs([doc])
        self.assertEqual(doc, content)
        new_content = {"name": "James", "address": {"city": "Delhi"}}
        replacedDoc = coll.find().key(key).replaceOneAndGet(new_content)
        new_version = replacedDoc.version
        doc = coll.find().key(key).version(version).getOne()
        self.assertIsNone(doc)
        doc = coll.find().key(key).version(new_version).getOne().getContent()
        self.__normalize_docs([doc])
        self.assertEqual(doc, new_content)
        self.assertEqual(coll.find().key(key).version(version).remove(), 0)
        self.assertEqual(coll.find().key(key).version(new_version).remove(), 1)
        self.assertEqual(coll.find().count(), 0)
        self.conn.commit()
        coll.drop()

    def test_3411_get_cursor(self):
        "3411 - test keys with GetCursor"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestKeysWithGetCursor")
        coll.find().remove()
        values_to_insert = [
            {"name": "John", "address": {"city": "Bangalore"}},
            {"name": "Johnson", "address": {"city": "Banaras"}},
            {"name": "Joseph", "address": {"city": "Mangalore"}},
            {"name": "Jibin", "address": {"city": "Secunderabad"}},
            {"name": "Andrew", "address": {"city": "Hyderabad"}},
            {"name": "Matthew", "address": {"city": "Mumbai"}},
        ]
        docs = [coll.insertOneAndGet(value) for value in values_to_insert]
        keys = [docs[i].key for i in (2, 4, 5)]
        fetched_keys = [doc.key for doc in coll.find().keys(keys).getCursor()]
        self.assertEqual(list(sorted(fetched_keys)), list(sorted(keys)))
        self.conn.commit()
        coll.drop()

    def test_3412_created_on(self):
        "3412 - test createdOn attribute of Document"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("CreatedOn")
        coll.find().remove()
        data = {"name": "John", "address": {"city": "Bangalore"}}
        doc = coll.insertOneAndGet(data)
        self.assertEqual(doc.createdOn, doc.lastModified)

    @unittest.skipIf(
        test_env.get_client_version() < (20, 1), "unsupported client"
    )
    def test_3413_soda_truncate(self):
        "3413 - test Soda truncate"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("TestTruncateDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "George", "age": 47},
            {"name": "Susan", "age": 39},
            {"name": "John", "age": 50},
            {"name": "Jill", "age": 54},
        ]
        for value in values_to_insert:
            coll.insertOne(value)
        self.conn.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        coll.truncate()
        self.assertEqual(coll.find().count(), 0)
        coll.drop()

    def test_3414_soda_hint(self):
        "3414 - verify hints are reflected in the executed SQL statement"
        soda_db = self.conn.getSodaDatabase()
        cursor = self.conn.cursor()
        statement = """
                SELECT
                    ( SELECT t2.sql_fulltext
                      FROM v$sql t2
                      WHERE t2.sql_id = t1.prev_sql_id
                        AND t2.child_number = t1.prev_child_number
                    )
                FROM v$session t1
                WHERE t1.audsid = sys_context('userenv', 'sessionid')"""
        coll = soda_db.createCollection("TestSodaHint")
        coll.find().remove()
        values_to_insert = [
            {"name": "George", "age": 47},
            {"name": "Susan", "age": 39},
        ]
        coll.insertOneAndGet(values_to_insert[0], hint="MONITOR")
        cursor.execute(statement)
        (result,) = cursor.fetchone()
        self.assertIn("MONITOR", result.read())

        coll.find().hint("MONITOR").getOne().getContent()
        cursor.execute(statement)
        (result,) = cursor.fetchone()
        self.assertIn("MONITOR", result.read())

        coll.insertOneAndGet(values_to_insert[1], hint="NO_MONITOR")
        cursor.execute(statement)
        (result,) = cursor.fetchone()
        self.assertIn("NO_MONITOR", result.read())

    def test_3415_soda_hint_with_invalid_type(self):
        "3415 - test error for invalid type for soda hint"
        soda_db = self.conn.getSodaDatabase()
        coll = soda_db.createCollection("InvalidSodaHint")
        self.assertRaises(
            TypeError, coll.insertOneAndGet, dict(name="Fred", age=16), hint=5
        )
        self.assertRaises(
            TypeError,
            coll.insertManyAndGet,
            dict(name="George", age=25),
            hint=10,
        )
        self.assertRaises(
            TypeError, coll.saveAndGet, dict(name="Sally", age=36), hint=5
        )
        self.assertRaises(TypeError, coll.find().hint, 2)

    def test_3416_collection_name_and_metadata(self):
        "3416 - test name and metadata attribute"
        soda_db = self.conn.getSodaDatabase()
        collection_name = "TestCollectionMetadata"
        coll = soda_db.createCollection(collection_name)
        self.assertEqual(coll.name, collection_name)
        self.assertEqual(coll.metadata["tableName"], collection_name)
        coll.drop()

    def test_3417_insert_many(self):
        "3417 - test insertMany"
        soda_db = self.get_soda_database(minclient=(18, 5))
        coll = soda_db.createCollection("TestInsertMany")
        values_to_insert = [
            dict(name="George", age=25),
            soda_db.createDocument(dict(name="Lucas", age=47)),
        ]
        coll.insertMany(values_to_insert)
        self.conn.commit()
        fetched_values = [doc.getContent() for doc in coll.find().getCursor()]
        fetched_values.sort(key=lambda x: x["name"])
        for fetched_val, expected_val in zip(fetched_values, values_to_insert):
            if not isinstance(expected_val, dict):
                expected_val = expected_val.getContent()
            self.assertEqual(fetched_val, fetched_val)
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^DPI-1031:", coll.insertMany, []
        )
        coll.drop()

    def test_3418_save(self):
        "3418 - test save"
        soda_db = self.get_soda_database(minclient=(19, 9))
        coll = soda_db.createCollection("TestSodaSave")
        values_to_save = [
            dict(name="Jill", age=37),
            soda_db.createDocument(dict(name="John", age=7)),
            soda_db.createDocument(dict(name="Charles", age=24)),
        ]
        for value in values_to_save:
            coll.save(value)
        self.conn.commit()
        fetched_docs = coll.find().getDocuments()
        for fetched_doc, expected_doc in zip(fetched_docs, values_to_save):
            if isinstance(expected_doc, dict):
                expected_doc = soda_db.createDocument(expected_doc)
            self.assertEqual(
                fetched_doc.getContent(), expected_doc.getContent()
            )
        coll.drop()

    def test_3419_save_and_get_with_hint(self):
        "3419 - test saveAndGet with hint"
        soda_db = self.get_soda_database(minclient=(19, 11))
        cursor = self.conn.cursor()
        statement = """
                SELECT
                    ( SELECT t2.sql_fulltext
                      FROM v$sql t2
                      WHERE t2.sql_id = t1.prev_sql_id
                        AND t2.child_number = t1.prev_child_number
                    )
                FROM v$session t1
                WHERE t1.audsid = sys_context('userenv', 'sessionid')"""
        coll = soda_db.createCollection("TestSodaSaveWithHint")
        coll.find().remove()

        values_to_save = [
            dict(name="Jordan", age=59),
            dict(name="Curry", age=34),
        ]
        hints = ["MONITOR", "NO_MONITOR"]
        for value, hint in zip(values_to_save, hints):
            coll.saveAndGet(value, hint=hint)
            coll.find().hint(hint).getOne().getContent()
            cursor.execute(statement)
            (result,) = cursor.fetchone()
            self.assertIn(hint, result.read())

    def test_3420_save_and_get(self):
        "3420 - test saveAndGet"
        soda_db = self.get_soda_database(minclient=(19, 9))
        coll = soda_db.createCollection("TestSodaSaveAndGet")
        coll.find().remove()
        values_to_save = [
            dict(name="John", age=50),
            soda_db.createDocument(dict(name="Mark", age=45)),
            soda_db.createDocument(dict(name="Jill", age=32)),
        ]
        inserted_keys = []
        for value in values_to_save:
            doc = coll.saveAndGet(value)
            inserted_keys.append(doc.key)
        fetched_docs = coll.find().getDocuments()
        self.conn.commit()
        self.assertEqual(coll.find().count(), len(values_to_save))
        for key, fetched_doc in zip(inserted_keys, fetched_docs):
            doc = coll.find().key(key).getOne()
            self.assertEqual(doc.getContent(), fetched_doc.getContent())
        coll.drop()

    def test_3421_insert_many_and_get(self):
        "3421 - test insert many and get"
        soda_db = self.get_soda_database(minclient=(18, 5))
        for name in soda_db.getCollectionNames():
            soda_db.openCollection(name).drop()
        coll = soda_db.createCollection("TestInsertManyAndGet")
        values_to_insert = [
            dict(name="George", age=25),
            soda_db.createDocument(dict(name="Lucas", age=47)),
        ]
        docs = coll.insertManyAndGet(values_to_insert)
        inserted_keys = [doc.key for doc in docs]
        self.conn.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        for key, expected_doc in zip(inserted_keys, values_to_insert):
            if isinstance(expected_doc, dict):
                expected_doc = soda_db.createDocument(expected_doc)
            doc = coll.find().key(key).getOne().getContent()
            self.__normalize_docs([doc])
            self.assertEqual(doc, expected_doc.getContent())
        coll.drop()

    def test_3422_close_cursor(self):
        "3422 - close document cursor and confirm exception is raised"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestCloseSodaDocCursor")
        cursor = coll.find().getCursor()
        cursor.close()
        self.assertRaisesRegex(
            oracledb.InterfaceError, "^DPY-1006", cursor.close
        )
        self.assertRaisesRegex(
            oracledb.InterfaceError, "^DPY-1006:", next, cursor
        )
        coll.drop()

    def test_3423_limit(self):
        "3423 - test limit to get specific amount of documents"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestSodaLimit")
        values_to_insert = [{"group": "Camila"} for i in range(20)]
        coll.insertMany(values_to_insert)
        self.conn.commit()
        docs = coll.find().getDocuments()
        self.assertEqual(len(docs), len(values_to_insert))
        docs = coll.find().limit(3).getDocuments()
        self.assertEqual(len(docs), 3)
        coll.drop()

    def test_3424_count_negative(self):
        "3424 - get count exceptions when using limit and skip"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestSodaCountExceptions")
        data = [{"song": "WYMCA"} for i in range(20)]
        coll.insertMany(data)
        self.conn.commit()
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-40748:", coll.find().limit(5).count
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError, "^ORA-40748:", coll.find().skip(10).count
        )
        coll.drop()

    def test_3425_map_mode(self):
        "3425 - test mapMode parameter"
        soda_db = self.get_soda_database()
        data = [{"price": 4900}, {"price": 8}]
        expected_data = data * 2

        original_coll = soda_db.createCollection("TestCollMapMode")
        original_coll.insertMany(data)
        mapped_coll = soda_db.createCollection("TestCollMapMode", mapMode=True)
        mapped_coll.insertMany(data)

        for coll in [original_coll, mapped_coll]:
            fetched_data = list(
                doc.getContent() for doc in coll.find().getDocuments()
            )
            self.__normalize_docs(fetched_data)
            self.assertEqual(fetched_data, expected_data)
            self.assertRaisesRegex(
                oracledb.DatabaseError, "^ORA-40626", coll.drop
            )
        self.conn.commit()
        self.assertTrue(original_coll.drop())
        self.assertFalse(mapped_coll.drop())

    def test_3426_map_mode_negative(self):
        "3426 - test mapping a new collection from an non-existent table"
        soda_db = self.get_soda_database()
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-40623",
            soda_db.createCollection,
            "TestSodaMapNonExistent",
            mapMode=True,
        )

    def test_3427_negative(self):
        "3427 - test negative cases for SodaOperation methods"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestSodaOperationNegative")
        self.assertRaises(TypeError, coll.find().filter, 5)
        self.assertRaises(TypeError, coll.find().key, 2)
        self.assertRaises(TypeError, coll.find().keys, [1, 2, 3])
        self.assertRaises(TypeError, coll.find().skip, "word")
        self.assertRaises(TypeError, coll.find().skip, -5)
        self.assertRaises(TypeError, coll.find().version, 1971)
        self.assertRaises(TypeError, coll.find().limit, "a word")

    def test_3428_fetch_array_size(self):
        "3428 - test fetchArraySize"
        soda_db = self.get_soda_database(minclient=(19, 5))
        coll = soda_db.createCollection("TestSodaFetchArraySize")
        coll.find().remove()
        for i in range(90):
            coll.save({"name": "Emmanuel", "age": i + 1})
        self.conn.commit()

        self.setup_round_trip_checker()
        # setting array size to 0 will use the default value of 100
        # requires a single round-trip
        coll.find().fetchArraySize(0).getDocuments()
        self.assertRoundTrips(1)

        # setting array size to 1 requires a round-trip for each SodaDoc
        coll.find().fetchArraySize(1).getDocuments()
        self.assertRoundTrips(91)

        # setting array size to 20 requires 5 round-trips
        coll.find().fetchArraySize(20).getDocuments()
        self.assertRoundTrips(5)

        # getting a SodaDocCursor requires a round-trip
        coll.find().fetchArraySize(0).getCursor()
        self.assertRoundTrips(1)

        # setting array size to 1 and iterating the SodaDocCursor requires a
        # round-trip for each SodaDoc
        soda_doc_cursor = coll.find().fetchArraySize(1).getCursor()
        for soda_doc in soda_doc_cursor:
            continue
        self.assertRoundTrips(91)

        # setting array size to 50 and iterating the SodaDocCursor requires
        # two round-trips
        soda_doc_cursor = coll.find().fetchArraySize(50).getCursor()
        for soda_doc in soda_doc_cursor:
            continue
        self.assertRoundTrips(2)

        # check a few negative scenarios
        self.assertRaises(TypeError, coll.find().fetchArraySize, "Mijares")
        self.assertRaises(TypeError, coll.find().fetchArraySize, -1)
        coll.drop()

    def test_3429_getting_indexes(self):
        "3429 - test getting indexes on a collection"
        soda_db = self.get_soda_database(minclient=(19, 13))
        coll = soda_db.createCollection("TestSodaListIndexes")
        coll.drop()
        coll = soda_db.createCollection("TestSodaListIndexes")
        index_1 = {
            "name": "ix_3428-1",
            "fields": [
                {"path": "address.city", "datatype": "string", "order": "asc"}
            ],
        }
        index_2 = {
            "name": "ix_3428-2",
            "fields": [
                {
                    "path": "address.postal_code",
                    "datatype": "string",
                    "order": "asc",
                }
            ],
        }
        self.assertEqual(coll.listIndexes(), [])
        coll.createIndex(index_1)
        coll.createIndex(index_2)
        indexes = coll.listIndexes()
        indexes.sort(key=lambda x: x["name"])
        self.assertEqual(indexes[0]["fields"][0]["path"], "address.city")
        self.assertEqual(
            indexes[1]["fields"][0]["path"], "address.postal_code"
        )

    def test_3430_lock_documents(self):
        "3430 - test locking documents on fetch"
        soda_db = self.get_soda_database(minclient=(19, 11))
        coll = soda_db.createCollection("TestSodaLockDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "Bob", "age": 46},
            {"name": "Barb", "age": 45},
            {"name": "Sandy", "age": 47},
        ]
        coll.insertMany(values_to_insert)
        coll.find().lock().getDocuments()

    def test_3431_drop(self):
        "3431 - test that drop returns the correct boolean"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestDropCollection")
        self.assertTrue(coll.drop())

        # the collection has already been dropped
        self.assertFalse(coll.drop())

    def test_3432_drop_empty_mapped_collection(self):
        "3432 - test drop with an empty mapped collection"
        soda_db = self.get_soda_database()
        original_coll = soda_db.createCollection("TestDropMapMode")
        mapped_coll = soda_db.createCollection("TestDropMapMode", mapMode=True)
        self.assertTrue(mapped_coll.drop())
        self.assertFalse(original_coll.drop())

    def test_3433_replace_one_returns(self):
        "3433 - test that replaceOne() returns a correct boolean"
        soda_db = self.get_soda_database()
        coll = soda_db.createCollection("TestReplaceDocReturns")
        coll.find().remove()
        doc = coll.insertOneAndGet({"address": {"city": "Sydney"}})

        new_content = {"address": {"city": "Melbourne"}}
        self.assertTrue(coll.find().key(doc.key).replaceOne(new_content))

        unregistered_key = "DB4A2628F1E0985C891F3F4836"
        self.assertFalse(
            coll.find().key(unregistered_key).replaceOne(new_content)
        )
        self.conn.commit()
        coll.drop()

    def test_3434_replace_one_and_get_negative(self):
        "3434 - replaceOne() and replaceOneAndGet() with invalid scenarios"
        conn = test_env.get_connection()
        soda_db = conn.getSodaDatabase()
        coll = soda_db.createCollection("TestReplaceOneNegative")
        coll.find().remove()
        coll.insertMany([{"Wisdom": 1.7} for d in range(2)])
        keys = [d.key for d in coll.find().getDocuments()]
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-40734:",
            coll.find().keys(keys).replaceOne,
            {"data": "new"},
        )
        self.assertRaisesRegex(
            oracledb.DatabaseError,
            "^ORA-40734:",
            coll.find().keys(keys).replaceOneAndGet,
            {"data": "new"},
        )

    def test_3435_write_read_only_coll_negative(self):
        "3435 - test writting a read-only collection"
        soda_db = self.get_soda_database()
        metadata = {
            "readOnly": True,
        }
        coll = soda_db.createCollection("TestCollReadOnly", metadata)

        methods = [
            coll.insertOne,
            coll.insertOneAndGet,
            coll.insertMany,
            coll.insertManyAndGet,
            coll.save,
            coll.saveAndGet,
        ]
        for method in methods:
            with self.subTest(method=method):
                self.assertRaisesRegex(
                    oracledb.DatabaseError,
                    "^ORA-40663:",
                    method,
                    {"Song 1": "No end"},
                )

    def test_3436_create_collection_same_metadata(self):
        "3436 - createCollection() with the same name and metadata"
        soda_db = self.get_soda_database()
        coll_name = "TestCollSameMetadata"
        coll1 = soda_db.createCollection(coll_name, {"readOnly": True})
        coll2 = soda_db.createCollection(coll_name, {"readOnly": True})
        self.assertTrue(coll1.drop())
        self.assertFalse(coll2.drop())

    def test_3437_create_collection_different_metadata(self):
        "3437 - createCollection() with the same name but different metadata"
        soda_db = self.get_soda_database()
        coll_name = "TestCollDifferentMetadata"
        coll = soda_db.createCollection(coll_name)
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-40669:"):
            soda_db.createCollection(coll_name, {"readOnly": False})
        coll.drop()

        coll = soda_db.createCollection(coll_name, {"readOnly": True})
        with self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-40669:"):
            soda_db.createCollection(coll_name, {"readOnly": False})
        coll.drop()


if __name__ == "__main__":
    test_env.run_test_cases()
