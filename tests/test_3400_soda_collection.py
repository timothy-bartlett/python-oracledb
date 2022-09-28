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
3400 - Module for testing Simple Oracle Document Access (SODA) Collections
"""

import unittest
import json

import oracledb
import test_env

@unittest.skipIf(test_env.skip_soda_tests(),
                 "unsupported client/server combination")
class TestCase(test_env.BaseTestCase):

    def __test_skip(self, coll, num_to_skip, expected_content):
        filter_spec = {'$orderby': [{'path': 'name', 'order': 'desc'}]}
        doc = coll.find().filter(filter_spec).skip(num_to_skip).getOne()
        content = doc.getContent() if doc is not None else None
        self.assertEqual(content, expected_content)

    def test_3400_invalid_json(self):
        "3400 - test inserting invalid JSON value into SODA collection"
        invalid_json = "{testKey:testValue}"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("InvalidJSON")
        doc = soda_db.createDocument(invalid_json)
        self.assertRaisesRegex(oracledb.DatabaseError,
                               "^ORA-40780:|^ORA-02290:", coll.insertOne, doc)
        coll.drop()

    def test_3401_insert_documents(self):
        "3401 - test inserting documents into a SODA collection"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestInsertDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "George", "age": 47},
            {"name": "Susan", "age": 39},
            {"name": "John", "age": 50},
            {"name": "Jill", "age": 54}
        ]
        inserted_keys = []
        for value in values_to_insert:
            doc = coll.insertOneAndGet(value)
            inserted_keys.append(doc.key)
        self.connection.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        for key, value in zip(inserted_keys, values_to_insert):
            doc = coll.find().key(key).getOne()
            self.assertEqual(doc.getContent(), value)
        coll.drop()

    def test_3402_skip_documents(self):
        "3402 - test skipping documents in a SODA collection"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestSkipDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "Anna", "age": 62},
            {"name": "Mark", "age": 37},
            {"name": "Martha", "age": 43},
            {"name": "Matthew", "age": 28}
        ]
        for value in values_to_insert:
            coll.insertOne(value)
        self.connection.commit()
        self.__test_skip(coll, 0, values_to_insert[3])
        self.__test_skip(coll, 1, values_to_insert[2])
        self.__test_skip(coll, 3, values_to_insert[0])
        self.__test_skip(coll, 4, None)
        self.__test_skip(coll, 125, None)

    def test_3403_replace_document(self):
        "3403 - test replace documents in SODA collection"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestReplaceDoc")
        coll.find().remove()
        content = {'name': 'John', 'address': {'city': 'Sydney'}}
        doc = coll.insertOneAndGet(content)
        new_content = {'name': 'John', 'address': {'city':'Melbourne'}}
        coll.find().key(doc.key).replaceOne(new_content)
        self.connection.commit()
        self.assertEqual(coll.find().key(doc.key).getOne().getContent(),
                         new_content)
        coll.drop()

    def test_3404_search_documents_with_content(self):
        "3404 - test search documents with content using $like and $regex"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestSearchDocContent")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Bangalore'}},
            {'name': 'Jibin', 'address': {'city': 'Secunderabad'}},
            {'name': 'Andrew', 'address': {'city': 'Hyderabad'}},
            {'name': 'Matthew', 'address': {'city': 'Mumbai'}}
        ]
        for value in data:
            coll.insertOne(value)
        self.connection.commit()
        filter_specs = [
            ({'name': {'$like': 'And%'}}, 1),
            ({'name': {'$like': 'J%n'}}, 3),
            ({'name': {'$like': '%hn%'}}, 2),
            ({'address.city': {'$like': 'Ban%'}}, 3),
            ({'address.city': {'$like': '%bad'}}, 2),
            ({'address.city': {'$like': 'Hyderabad'}}, 1),
            ({'address.city': {'$like': 'China%'}}, 0),
            ({'name': {'$regex': 'Jo.*'}}, 3),
            ({'name': {'$regex': '.*[ho]n'}}, 2),
            ({'name': {'$regex': 'J.*h'}}, 1),
            ({'address.city': {'$regex': 'Ba.*'}}, 3),
            ({'address.city': {'$regex': '.*bad'}}, 2),
            ({'address.city': {'$regex': 'Hyderabad'}}, 1),
            ({'name': {'$regex': 'Js.*n'}}, 0)
        ]
        for filter_spec, expected_count in filter_specs:
            self.assertEqual(coll.find().filter(filter_spec).count(),
                             expected_count, filter_spec)
        coll.drop()

    def test_3405_document_remove(self):
        "3405 - test removing documents"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestRemoveDocs")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Mangalore'}},
            {'name': 'Jibin', 'address': {'city': 'Secunderabad'}},
            {'name': 'Andrew', 'address': {'city': 'Hyderabad'}},
            {'name': 'Matthew', 'address': {'city': 'Mumbai'}}
        ]
        docs = [coll.insertOneAndGet(v) for v in data]
        coll.find().key(docs[3].key).remove()
        self.assertEqual(coll.find().count(), len(data) - 1)
        searchResults = coll.find().filter({'name': {'$like': 'Jibin'}})
        self.assertEqual(searchResults.count(), 0)
        coll.find().filter({'name': {'$like': 'John%'}}).remove()
        self.assertEqual(coll.find().count(), len(data) - 3)
        coll.find().filter({'name': {'$regex': 'J.*'}}).remove()
        self.assertEqual(coll.find().count(), len(data) - 4)
        self.connection.commit()
        coll.drop()

    def test_3406_create_and_drop_index(self):
        "3406 - test create and drop Index"
        index_name = "TestIndexes_ix_1"
        index_spec =  {
            'name': index_name,
            'fields': [
                {
                    'path': 'address.city',
                    'datatype': 'string',
                    'order': 'asc'
                }
            ]
        }
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestIndexes")
        coll.find().remove()
        self.connection.commit()
        coll.dropIndex(index_name)
        coll.createIndex(index_spec)
        self.assertRaisesRegex(oracledb.DatabaseError, "^ORA-40733:",
                               coll.createIndex, index_spec)
        self.assertEqual(coll.dropIndex(index_name), True)
        self.assertEqual(coll.dropIndex(index_name), False)
        coll.drop()

    def test_3407_get_documents(self):
        "3407 - test getting documents from Collection"
        self.connection.autocommit = True
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestGetDocs")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Mangalore'}},
            {'name': 'Jibin', 'address': {'city': 'Secunderabad'}},
            {'name': 'Andrew', 'address': {'city': 'Hyderabad'}}
        ]
        inserted_keys = list(sorted(coll.insertOneAndGet(v).key for v in data))
        fetched_keys = list(sorted(d.key for d in coll.find().getDocuments()))
        self.assertEqual(fetched_keys, inserted_keys)
        coll.drop()

    def test_3408_cursor(self):
        "3408 - test fetching documents from a cursor"
        self.connection.autocommit = True
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestFindViaCursor")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Mangalore'}},
        ]
        inserted_keys = list(sorted(coll.insertOneAndGet(v).key for v in data))
        fetched_keys = list(sorted(d.key for d in coll.find().getCursor()))
        self.assertEqual(fetched_keys, inserted_keys)
        coll.drop()

    def test_3409_multiple_document_remove(self):
        "3409 - test removing multiple documents using multiple keys"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestRemoveMultipleDocs")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Mangalore'}},
            {'name': 'Jibin', 'address': {'city': 'Secunderabad'}},
            {'name': 'Andrew', 'address': {'city': 'Hyderabad'}},
            {'name': 'Matthew', 'address': {'city': 'Mumbai'}}
        ]
        docs = [coll.insertOneAndGet(v) for v in data]
        keys = [docs[i].key for i in (1, 3, 5)]
        num_removed = coll.find().keys(keys).remove()
        self.assertEqual(num_removed, len(keys))
        self.assertEqual(coll.find().count(), len(data) - len(keys))
        self.connection.commit()
        coll.drop()

    def test_3410_document_version(self):
        "3410 - test using version to get documents and remove them"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestDocumentVersion")
        coll.find().remove()
        content = {'name': 'John', 'address': {'city': 'Bangalore'}}
        inserted_doc = coll.insertOneAndGet(content)
        key = inserted_doc.key
        version = inserted_doc.version
        doc = coll.find().key(key).version(version).getOne()
        self.assertEqual(doc.getContent(), content)
        new_content = {'name': 'James', 'address': {'city': 'Delhi'}}
        replacedDoc = coll.find().key(key).replaceOneAndGet(new_content)
        new_version = replacedDoc.version
        doc = coll.find().key(key).version(version).getOne()
        self.assertEqual(doc, None)
        doc = coll.find().key(key).version(new_version).getOne()
        self.assertEqual(doc.getContent(), new_content)
        self.assertEqual(coll.find().key(key).version(version).remove(), 0)
        self.assertEqual(coll.find().key(key).version(new_version).remove(), 1)
        self.assertEqual(coll.find().count(), 0)
        self.connection.commit()
        coll.drop()

    def test_3411_get_cursor(self):
        "3411 - test keys with GetCursor"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestKeysWithGetCursor")
        coll.find().remove()
        data = [
            {'name': 'John', 'address': {'city': 'Bangalore'}},
            {'name': 'Johnson', 'address': {'city': 'Banaras'}},
            {'name': 'Joseph', 'address': {'city': 'Mangalore'}},
            {'name': 'Jibin', 'address': {'city': 'Secunderabad'}},
            {'name': 'Andrew', 'address': {'city': 'Hyderabad'}},
            {'name': 'Matthew', 'address': {'city': 'Mumbai'}}
        ]
        docs = [coll.insertOneAndGet(v) for v in data]
        keys = [docs[i].key for i in (2, 4, 5)]
        fetched_keys = [d.key for d in coll.find().keys(keys).getCursor()]
        self.assertEqual(list(sorted(fetched_keys)), list(sorted(keys)))
        self.connection.commit()
        coll.drop()

    def test_3412_created_on(self):
        "3412 - test createdOn attribute of Document"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("CreatedOn")
        coll.find().remove()
        data = {'name': 'John', 'address': {'city': 'Bangalore'}}
        doc = coll.insertOneAndGet(data)
        self.assertEqual(doc.createdOn, doc.lastModified)

    @unittest.skipIf(test_env.get_client_version() < (20, 1),
                     "unsupported client")
    def test_3413_soda_truncate(self):
        "3413 - test Soda truncate"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("TestTruncateDocs")
        coll.find().remove()
        values_to_insert = [
            {"name": "George", "age": 47},
            {"name": "Susan", "age": 39},
            {"name": "John", "age": 50},
            {"name": "Jill", "age": 54}
        ]
        for value in values_to_insert:
            coll.insertOne(value)
        self.connection.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        coll.truncate()
        self.assertEqual(coll.find().count(), 0)
        coll.drop()

    def test_3414_soda_hint(self):
        "3414 - verify hints are reflected in the executed SQL statement"
        soda_db = self.connection.getSodaDatabase()
        cursor = self.connection.cursor()
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
        result, = cursor.fetchone()
        self.assertTrue('MONITOR' in result.read())

        coll.find().hint("MONITOR").getOne().getContent()
        cursor.execute(statement)
        result, = cursor.fetchone()
        self.assertTrue('MONITOR' in result.read())

        coll.insertOneAndGet(values_to_insert[1], hint="NO_MONITOR")
        cursor.execute(statement)
        result, = cursor.fetchone()
        self.assertTrue('NO_MONITOR' in result.read())

    def test_3415_soda_hint_with_invalid_type(self):
        "3415 - test error for invalid type for soda hint"
        soda_db = self.connection.getSodaDatabase()
        coll = soda_db.createCollection("InvalidSodaHint")
        self.assertRaises(TypeError, coll.insertOneAndGet,
                          dict(name="Fred", age=16), hint=5)
        self.assertRaises(TypeError, coll.insertManyAndGet,
                          dict(name="George", age=25), hint=10)
        self.assertRaises(TypeError, coll.saveAndGet,
                          dict(name="Sally", age=36), hint=5)

    def test_3416_collection_name_and_metadata(self):
        "3416 - test name and metadata attribute"
        soda_db = self.connection.getSodaDatabase()
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
            soda_db.createDocument(dict(name="Lucas", age=47))
        ]
        coll.insertMany(values_to_insert)
        self.connection.commit()
        fetched_docs = list(coll.find().getCursor())
        for fetched_doc, expected_doc in zip(fetched_docs, values_to_insert):
            if isinstance(expected_doc, dict):
                expected_doc = soda_db.createDocument(expected_doc)
            self.assertEqual(fetched_doc.getContent(),
                             expected_doc.getContent())
        self.assertRaisesRegex(oracledb.DatabaseError, "^DPI-1031:",
                               coll.insertMany, [])
        coll.drop()

    def test_3418_save(self):
        "3418 - test save"
        soda_db = self.get_soda_database(minclient=(19, 9))
        coll = soda_db.createCollection("TestSodaSave")
        values_to_save = [
            dict(name="Jill", age=37),
            soda_db.createDocument(dict(name="John", age=7)),
            soda_db.createDocument(dict(name="Charles", age=24))
        ]
        for value in values_to_save:
            coll.save(value)
        self.connection.commit()
        fetched_docs = coll.find().getDocuments()
        for fetched_doc, expected_doc in zip(fetched_docs, values_to_save):
            if isinstance(expected_doc, dict):
                expected_doc = soda_db.createDocument(expected_doc)
            self.assertEqual(fetched_doc.getContent(),
                             expected_doc.getContent())
        coll.drop()

    def test_3419_save_and_get_with_hint(self):
        "3419 - test saveAndGet with hint"
        soda_db = self.get_soda_database(minclient=(19, 11))
        cursor = self.connection.cursor()
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
            dict(name="Curry", age=34)
        ]
        hints = ["MONITOR", "NO_MONITOR"]

        for value, hint in zip(values_to_save, hints):
            coll.saveAndGet(value, hint=hint)
            coll.find().hint(hint).getOne().getContent()
            cursor.execute(statement)
            result, = cursor.fetchone()
            self.assertTrue(hint in result.read())

    def test_3420_save_and_get(self):
        "3420 - test saveAndGet"
        soda_db = self.get_soda_database(minclient=(19, 9))
        coll = soda_db.createCollection("TestSodaSaveAndGet")
        coll.find().remove()
        values_to_save = [
            dict(name="John", age=50),
            soda_db.createDocument(dict(name="Mark", age=45)),
            soda_db.createDocument(dict(name="Jill", age=32))
        ]
        inserted_keys = []
        for value in values_to_save:
            doc = coll.saveAndGet(value)
            inserted_keys.append(doc.key)
        fetched_docs = coll.find().getDocuments()
        self.connection.commit()
        self.assertEqual(coll.find().count(), len(values_to_save))
        for key, fetched_doc in zip(inserted_keys, fetched_docs):
            doc = coll.find().key(key).getOne()
            self.assertEqual(doc.getContent(), fetched_doc.getContent())
        coll.drop()

    def test_3421_insert_many_and_get(self):
        "3421 - test insert many and get"
        soda_db = self.get_soda_database(minclient=(18, 5))
        coll = soda_db.createCollection("TestInsertManyAndGet")
        values_to_insert = [
            dict(name="George", age=25),
            soda_db.createDocument(dict(name="Lucas", age=47))
        ]
        docs = coll.insertManyAndGet(values_to_insert)
        inserted_keys = [i.key for i in docs]
        self.connection.commit()
        self.assertEqual(coll.find().count(), len(values_to_insert))
        for key, expected_doc in zip(inserted_keys, values_to_insert):
            if isinstance(expected_doc, dict):
                expected_doc = soda_db.createDocument(expected_doc)
            doc = coll.find().key(key).getOne()
            self.assertEqual(doc.getContent(), expected_doc.getContent())
        coll.drop()

if __name__ == "__main__":
    test_env.run_test_cases()
