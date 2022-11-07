.. _xmldatatype:

******************
Using XMLTYPE Data
******************

Oracle XMLType columns are fetched as strings by default in Thin and Thick
mode.  Note that in Thick mode you may need to use ``XMLTYPE.GETCLOBVAL()`` as
discussed below.

The examples below demonstrate using XMLType data with python-oracledb.  The
following table will be used in these examples:

.. code-block:: sql

    CREATE TABLE xml_table (
        id NUMBER,
        xml_data SYS.XMLTYPE
    );

Inserting into the table can be done by simply binding a string:

.. code-block:: python

    xml_data = """<?xml version="1.0"?>
            <customer>
                <name>John Smith</name>
                <Age>43</Age>
                <Designation>Professor</Designation>
                <Subject>Mathematics</Subject>
            </customer>"""
    cursor.execute("insert into xml_table values (:id, :xml)",
                   id=1, xml=xml_data)

This approach works with XML strings up to 1 GB in size. For longer strings, a
temporary CLOB must be created using :meth:`Connection.createlob()` and cast
when bound:

.. code-block:: python

    clob = connection.createlob(oracledb.DB_TYPE_CLOB)
    clob.write(xml_data)
    cursor.execute("insert into xml_table values (:id, sys.xmltype(:xml))",
                   id=2, xml=clob)

Fetching XML data can be done directly in Thin mode. This also works in Thick
mode for values that are shorter than the length of a VARCHAR2 column:

.. code-block:: python

    cursor.execute("select xml_data from xml_table where id = :id", id=1)
    xml_data, = cursor.fetchone()
    print(xml_data)

In Thick mode, for values that exceed the length of a VARCHAR2 column, a CLOB
must be returned by using the function ``XMLTYPE.GETCLOBVAL()``:

.. code-block:: python

    cursor.execute("""
            select xmltype.getclobval(xml_data)
            from xml_table
            where id = :id""", id=1)
    clob, = cursor.fetchone()
    print(clob.read())

The LOB that is returned can be streamed, as shown.  Alternatively a string can
be returned.  See :ref:`lobdata` for more information.
