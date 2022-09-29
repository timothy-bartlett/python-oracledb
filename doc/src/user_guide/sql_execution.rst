.. _sqlexecution:

*************
Executing SQL
*************

Executing SQL statements is the primary way in which a Python application
communicates with Oracle Database.  Statements are executed using the methods
:meth:`Cursor.execute()` or :meth:`Cursor.executemany()`.  Statements include
queries, Data Manipulation Language (DML), and Data Definition Language (DDL).
A few other `specialty statements
<https://www.oracle.com/pls/topic/lookup?ctx=dblatest&
id=GUID-E1749EF5-2264-44DF-99EF-AEBEB943BED6>`__ can also be executed.

PL/SQL statements are discussed in :ref:`plsqlexecution`.  Other chapters
contain information on specific data types and features.  See :ref:`batchstmnt`,
:ref:`lobdata`, :ref:`jsondatatype`, and :ref:`xmldatatype`.

Python-oracledb can be used to execute individual statements, one at a time.  It does
not read SQL*Plus ".sql" files.  To read SQL files, use a technique like the one
in ``run_sql_script()`` in `samples/sample_env.py
<https://github.com/oracle/python-oracledb/blob/main/samples/sample_env.py>`__

SQL statements should not contain a trailing semicolon (";") or forward slash
("/").  This will fail:

.. code-block:: python

    cur.execute("select * from MyTable;")

This is correct:

.. code-block:: python

    cur.execute("select * from MyTable")


SQL Queries
===========

Queries (statements beginning with SELECT or WITH) can only be executed using
the method :meth:`Cursor.execute()`.  Rows can then be iterated over, or can be
fetched using one of the methods :meth:`Cursor.fetchone()`,
:meth:`Cursor.fetchmany()` or :meth:`Cursor.fetchall()`.  There is a
:ref:`default type mapping <defaultfetchtypes>` to Python types that can be
optionally :ref:`overridden <outputtypehandlers>`.

.. IMPORTANT::

    Interpolating or concatenating user data with SQL statements, for example
    ``cur.execute("SELECT * FROM mytab WHERE mycol = '" + myvar + "'")``, is a security risk
    and impacts performance.  Use :ref:`bind variables <bind>` instead. For
    example, ``cur.execute("SELECT * FROM mytab WHERE mycol = :mybv", mybv=myvar)``.

.. _fetching:

Fetch Methods
-------------

After :meth:`Cursor.execute()`, the cursor is returned as a convenience. This
allows code to iterate over rows like:

.. code-block:: python

    cur = connection.cursor()
    for row in cur.execute("select * from MyTable"):
        print(row)

Rows can also be fetched one at a time using the method
:meth:`Cursor.fetchone()`:

.. code-block:: python

    cur = connection.cursor()
    cur.execute("select * from MyTable")
    while True:
        row = cur.fetchone()
        if row is None:
            break
        print(row)

If rows need to be processed in batches, the method :meth:`Cursor.fetchmany()`
can be used. The size of the batch is controlled by the ``numRows`` parameter,
which defaults to the value of :attr:`Cursor.arraysize`.

.. code-block:: python

    cur = connection.cursor()
    cur.execute("select * from MyTable")
    num_rows = 10
    while True:
        rows = cur.fetchmany(num_rows)
        if not rows:
            break
        for row in rows:
            print(row)

If all of the rows need to be fetched and can be contained in memory, the
method :meth:`Cursor.fetchall()` can be used.

.. code-block:: python

    cur = connection.cursor()
    cur.execute("select * from MyTable")
    rows = cur.fetchall()
    for row in rows:
        print(row)

The fetch methods return data as tuples.  To return results as dictionaries, see
:ref:`rowfactories`.

Closing Cursors
---------------

A cursor may be used to execute multiple statements. Once it is no longer
needed, it should be closed by calling :meth:`~Cursor.close()` in order to
reclaim resources in the database. It will be closed automatically when the
variable referencing it goes out of scope (and no further references are
retained). One other way to control the lifetime of a cursor is to use a "with"
block, which ensures that a cursor is closed once the block is completed. For
example:

.. code-block:: python

    with connection.cursor() as cursor:
        for row in cursor.execute("select * from MyTable"):
            print(row)

This code ensures that once the block is completed, the cursor is closed and
resources have been reclaimed by the database. In addition, any attempt to use
the variable ``cursor`` outside of the block will simply fail.

.. _querymetadata:

Query Column Metadata
---------------------

After executing a query, the column metadata such as column names and data types
can be obtained using :attr:`Cursor.description`:

.. code-block:: python

    cur = connection.cursor()
    cur.execute("select * from MyTable")
    for column in cur.description:
        print(column)

This could result in metadata like::

    ('ID', <class 'oracledb.DB_TYPE_NUMBER'>, 39, None, 38, 0, 0)
    ('NAME', <class 'oracledb.DB_TYPE_VARCHAR'>, 20, 20, None, None, 1)


.. _defaultfetchtypes:

Fetch Data Types
----------------

The following table provides a list of all of the data types that python-oracledb
knows how to fetch. The middle column gives the type that is returned in the
:ref:`query metadata <querymetadata>`.  The last column gives the type of
Python object that is returned by default. Python types can be changed with
:ref:`Output Type Handlers <outputtypehandlers>`.

.. list-table-with-summary::
    :header-rows: 1
    :class: wy-table-responsive
    :widths: 1 1 1
    :align: left
    :summary: The first column is the Oracle Database Type. The second column is the oracledb Database Type that is returned in the query metadata. The third column is the type of Python object that is returned by default.

    * - Oracle Database Type
      - oracledb Database Type
      - Default Python type
    * - BFILE
      - :attr:`oracledb.DB_TYPE_BFILE`
      - :ref:`oracledb.LOB <lobobj>`
    * - BINARY_DOUBLE
      - :attr:`oracledb.DB_TYPE_BINARY_DOUBLE`
      - float
    * - BINARY_FLOAT
      - :attr:`oracledb.DB_TYPE_BINARY_FLOAT`
      - float
    * - BLOB
      - :attr:`oracledb.DB_TYPE_BLOB`
      - :ref:`oracledb.LOB <lobobj>`
    * - CHAR
      - :attr:`oracledb.DB_TYPE_CHAR`
      - str
    * - CLOB
      - :attr:`oracledb.DB_TYPE_CLOB`
      - :ref:`oracledb.LOB <lobobj>`
    * - CURSOR
      - :attr:`oracledb.DB_TYPE_CURSOR`
      - :ref:`oracledb.Cursor <cursorobj>`
    * - DATE
      - :attr:`oracledb.DB_TYPE_DATE`
      - datetime.datetime
    * - INTERVAL DAY TO SECOND
      - :attr:`oracledb.DB_TYPE_INTERVAL_DS`
      - datetime.timedelta
    * - JSON
      - :attr:`oracledb.DB_TYPE_JSON`
      - dict, list or a scalar value [4]_
    * - LONG
      - :attr:`oracledb.DB_TYPE_LONG`
      - str
    * - LONG RAW
      - :attr:`oracledb.DB_TYPE_LONG_RAW`
      - bytes
    * - NCHAR
      - :attr:`oracledb.DB_TYPE_NCHAR`
      - str
    * - NCLOB
      - :attr:`oracledb.DB_TYPE_NCLOB`
      - :ref:`oracledb.LOB <lobobj>`
    * - NUMBER
      - :attr:`oracledb.DB_TYPE_NUMBER`
      - float or int [1]_
    * - NVARCHAR2
      - :attr:`oracledb.DB_TYPE_NVARCHAR`
      - str
    * - OBJECT [3]_
      - :attr:`oracledb.DB_TYPE_OBJECT`
      - :ref:`oracledb.Object <dbobjecttype>`
    * - RAW
      - :attr:`oracledb.DB_TYPE_RAW`
      - bytes
    * - ROWID
      - :attr:`oracledb.DB_TYPE_ROWID`
      - str
    * - TIMESTAMP
      - :attr:`oracledb.DB_TYPE_TIMESTAMP`
      - datetime.datetime
    * - TIMESTAMP WITH LOCAL TIME ZONE
      - :attr:`oracledb.DB_TYPE_TIMESTAMP_LTZ`
      - datetime.datetime [2]_
    * - TIMESTAMP WITH TIME ZONE
      - :attr:`oracledb.DB_TYPE_TIMESTAMP_TZ`
      - datetime.datetime [2]_
    * - UROWID
      - :attr:`oracledb.DB_TYPE_ROWID`, :attr:`oracledb.DB_TYPE_UROWID`
      - str
    * - VARCHAR2
      - :attr:`oracledb.DB_TYPE_VARCHAR`
      - str

.. [1] If the precision and scale obtained from query column metadata indicate
       that the value can be expressed as an integer, the value will be
       returned as an int. If the column is unconstrained (no precision and
       scale specified), the value will be returned as a float or an int
       depending on whether the value itself is an integer. In all other cases
       the value is returned as a float.
.. [2] The timestamps returned are naive timestamps without any time zone
       information present.
.. [3] These include all user-defined types such as VARRAY, NESTED TABLE, etc.

.. [4] If the JSON is an object, then a dict is returned. If it is an array,
       then a list is returned. If it is a scalar value, then that particular
       scalar value is returned.


.. _outputtypehandlers:

Changing Fetched Data Types with Output Type Handlers
-----------------------------------------------------

Sometimes the default conversion from an Oracle Database type to a Python type
must be changed in order to prevent data loss or to fit the purposes of the
Python application. In such cases, an output type handler can be specified for
queries.  Output type handlers do not affect values returned from
:meth:`Cursor.callfunc()` or :meth:`Cursor.callproc()`.

Output type handlers can be specified on the :attr:`connection
<Connection.outputtypehandler>` or on the :attr:`cursor
<Cursor.outputtypehandler>`. If specified on the cursor, fetch type handling is
only changed on that particular cursor. If specified on the connection, all
cursors created by that connection will have their fetch type handling changed.

The output type handler is expected to be a function with the following
signature::

    handler(cursor, name, defaultType, size, precision, scale)

The parameters are the same information as the query column metadata found in
:attr:`Cursor.description`. The function is called once for each column that is
going to be fetched. The function is expected to return a
:ref:`variable object <varobj>` (generally by a call to :func:`Cursor.var()`)
or the value ``None``. The value ``None`` indicates that the default type
should be used.

Examples of output handlers are shown in :ref:`numberprecision`,
:ref:`directlobs` and :ref:`fetching-raw-data`.  Also see samples such as `samples/type_handlers.py
<https://github.com/oracle/python-oracledb/blob/main/samples/type_handlers.py>`__

.. _numberprecision:

Fetched Number Precision
------------------------

One reason for using an output type handler is to ensure that numeric precision
is not lost when fetching certain numbers. Oracle Database uses decimal numbers
and these cannot be converted seamlessly to binary number representations like
Python floats. In addition, the range of Oracle numbers exceeds that of
floating point numbers. Python has decimal objects which do not have these
limitations and python-oracledb knows how to perform the conversion between Oracle
numbers and Python decimal values if directed to do so.

The following code sample demonstrates the issue:

.. code-block:: python

    cur = connection.cursor()
    cur.execute("create table test_float (X number(5, 3))")
    cur.execute("insert into test_float values (7.1)")
    connection.commit()
    cur.execute("select * from test_float")
    val, = cur.fetchone()
    print(val, "* 3 =", val * 3)

This displays ``7.1 * 3 = 21.299999999999997``

Using Python decimal objects, however, there is no loss of precision:

.. code-block:: python

    import decimal

    def number_to_decimal(cursor, name, default_type, size, precision, scale):
        if default_type == oracledb.DB_TYPE_NUMBER:
            return cursor.var(decimal.Decimal, arraysize=cursor.arraysize)

    cur = connection.cursor()
    cur.outputtypehandler = number_to_decimal
    cur.execute("select * from test_float")
    val, = cur.fetchone()
    print(val, "* 3 =", val * 3)

This displays ``7.1 * 3 = 21.3``

The Python ``decimal.Decimal`` converter gets called with the string
representation of the Oracle number.  The output from ``decimal.Decimal`` is
returned in the output tuple.

See `samples/return_numbers_as_decimals.py
<https://github.com/oracle/python-oracledb/blob/main/samples/return_numbers_as_decimals.py>`__


.. _outconverters:

Changing Query Results with Outconverters
-----------------------------------------

Python-oracledb "outconverters" can be used with :ref:`output type handlers
<outputtypehandlers>` to change returned data.

For example, to make queries return empty strings instead of NULLs:

.. code-block:: python

    def out_converter(value):
        if value is None:
            return ''
        return value

    def output_type_handler(cursor, name, default_type, size, precision, scale):
        if default_type in (oracledb.DB_TYPE_VARCHAR, oracledb.DB_TYPE_CHAR):
            return cursor.var(str, size, arraysize=cur.arraysize,
                              outconverter=out_converter)

    connection.outputtypehandler = output_type_handler


.. _rowfactories:

Changing Query Results with Rowfactories
----------------------------------------

Python-oracledb "rowfactories" are methods called for each row that is retrieved from
the database. The :meth:`Cursor.rowfactory` method is called with the tuple that
would normally be returned from the database.  The method can convert the tuple
to a different value and return it to the application in place of the tuple.

For example, to fetch each row of a query as a dictionary:

.. code-block:: python

    cursor.execute("select * from locations where location_id = 1000")
    columns = [col[0] for col in cursor.description]
    cursor.rowfactory = lambda *args: dict(zip(columns, args))
    data = cursor.fetchone()
    print(data)

The output is::

    {'LOCATION_ID': 1000, 'STREET_ADDRESS': '1297 Via Cola di Rie', 'POSTAL_CODE': '00989', 'CITY': 'Roma', 'STATE_PROVINCE': None, 'COUNTRY_ID': 'IT'}

If you join tables where the same column name occurs in both tables with
different meanings or values, then use a column alias in the query.  Otherwise,
only one of the similarly named columns will be included in the dictionary:

.. code-block:: sql

    select
        cat_name,
        cats.color as cat_color,
        dog_name,
        dogs.color
    from cats, dogs

.. _scrollablecursors:

Scrollable Cursors
------------------

Scrollable cursors enable applications to move backwards, forwards, to skip
rows, and to move to a particular row in a query result set. The result set is
cached on the database server until the cursor is closed. In contrast, regular
cursors are restricted to moving forward.

.. note::

  Scrollable cursors are only supported in the python-oracledb Thick mode. See
  :ref:`enablingthick`.

A scrollable cursor is created by setting the parameter ``scrollable=True``
when creating the cursor. The method :meth:`Cursor.scroll()` is used to move to
different locations in the result set.

Examples are:

.. code-block:: python

    cursor = connection.cursor(scrollable=True)
    cursor.execute("select * from ChildTable order by ChildId")

    cursor.scroll(mode="last")
    print("LAST ROW:", cursor.fetchone())

    cursor.scroll(mode="first")
    print("FIRST ROW:", cursor.fetchone())

    cursor.scroll(8, mode="absolute")
    print("ROW 8:", cursor.fetchone())

    cursor.scroll(6)
    print("SKIP 6 ROWS:", cursor.fetchone())

    cursor.scroll(-4)
    print("SKIP BACK 4 ROWS:", cursor.fetchone())

.. _fetchobjects:

Fetching Oracle Database Objects and Collections
------------------------------------------------

Oracle Database named object types and user-defined types can be fetched
directly in queries.  Each item is represented as a :ref:`Python object
<dbobjecttype>` corresponding to the Oracle Database object.  This Python object
can be traversed to access its elements.  Attributes including
:attr:`DbObjectType.name` and :attr:`DbObjectType.iscollection`, and methods
including :meth:`DbObject.aslist` and :meth:`DbObject.asdict` are available.

For example, if a table ``mygeometrytab`` contains a column ``geometry`` of
Oracle's predefined Spatial object type `SDO_GEOMETRY
<https://www.oracle.com/pls/topic/lookup?ctx=dblatest&id=GUID-683FF8C5-A773-4018-932D-2AF6EC8BC119>`__,
then it can be queried and printed:

.. code-block:: python

    cur.execute("select geometry from mygeometrytab")
    for obj, in cur:
        dumpobject(obj)

Where ``dumpobject()`` is defined as:

.. code-block:: python

    def dumpobject(obj, prefix = ""):
        if obj.type.iscollection:
            print(prefix, "[")
            for value in obj.aslist():
                if isinstance(value, oracledb.Object):
                    dumpobject(value, prefix + "  ")
                else:
                    print(prefix + "  ", repr(value))
            print(prefix, "]")
        else:
            print(prefix, "{")
            for attr in obj.type.attributes:
                value = getattr(obj, attr.name)
                if isinstance(value, oracledb.Object):
                    print(prefix + "   " + attr.name + ":")
                    dumpobject(value, prefix + "  ")
                else:
                    print(prefix + "   " + attr.name + ":", repr(value))
            print(prefix, "}")

This might produce output like::

    {
      SDO_GTYPE: 2003
      SDO_SRID: None
      SDO_POINT:
      {
        X: 1
        Y: 2
        Z: 3
      }
      SDO_ELEM_INFO:
      [
        1
        1003
        3
      ]
      SDO_ORDINATES:
      [
        1
        1
        5
        7
      ]
    }

Other information on using Oracle objects is in :ref:`Using Bind Variables
<bind>`.

Performance-sensitive applications should consider using scalar types instead of
objects. If you do use objects, avoid calling :meth:`Connection.gettype()`
unnecessarily, and avoid objects with large numbers of attributes.

.. _rowlimit:

Limiting Rows
-------------

Query data is commonly broken into one or more sets:

- To give an upper bound on the number of rows that a query has to process,
  which can help improve database scalability.

- To perform 'Web pagination' that allows moving from one set of rows to a
  next, or previous, set on demand.

- For fetching of all data in consecutive small sets for batch processing.
  This happens because the number of records is too large for Python to handle
  at one time.

The latter can be handled by calling :meth:`Cursor.fetchmany()` with one
execution of the SQL query.

'Web pagination' and limiting the maximum number of rows are detailed in this
section.  For each 'page' of results, a SQL query is executed to get the
appropriate set of rows from a table.  Since the query may be executed more
than once, ensure to use :ref:`bind variables <bind>` for row numbers and
row limits.

Oracle Database 12c SQL introduced an ``OFFSET`` / ``FETCH`` clause which is
similar to the ``LIMIT`` keyword of MySQL.  In Python, you can fetch a set of
rows using:

.. code-block:: python

    myoffset = 0       // do not skip any rows (start at row 1)
    mymaxnumrows = 20  // get 20 rows

    sql =
      """SELECT last_name
         FROM employees
         ORDER BY last_name
         OFFSET :offset ROWS FETCH NEXT :maxnumrows ROWS ONLY"""

    cur = connection.cursor()
    for row in cur.execute(sql, offset=myoffset, maxnumrows=mymaxnumrows):
        print(row)

In applications where the SQL query is not known in advance, this method
sometimes involves appending the ``OFFSET`` clause to the 'real' user query. Be
very careful to avoid SQL injection security issues.

For Oracle Database 11g and earlier there are several alternative ways
to limit the number of rows returned.  The old, canonical paging query
is::

    SELECT *
    FROM (SELECT a.*, ROWNUM AS rnum
          FROM (YOUR_QUERY_GOES_HERE -- including the order by) a
          WHERE ROWNUM <= MAX_ROW)
    WHERE rnum >= MIN_ROW

Here, ``MIN_ROW`` is the row number of first row and ``MAX_ROW`` is the row
number of the last row to return.  For example::

   SELECT *
   FROM (SELECT a.*, ROWNUM AS rnum
         FROM (SELECT last_name FROM employees ORDER BY last_name) a
         WHERE ROWNUM <= 20)
   WHERE rnum >= 1

This always has an 'extra' column, here called RNUM.

An alternative and preferred query syntax for Oracle Database 11g uses the
analytic ``ROW_NUMBER()`` function. For example, to get the 1st to 20th names the
query is::

    SELECT last_name FROM
    (SELECT last_name,
            ROW_NUMBER() OVER (ORDER BY last_name) AS myr
            FROM employees)
    WHERE myr BETWEEN 1 and 20

Ensure to use :ref:`bind variables <bind>` for the upper and lower limit
values.

.. _crc:

Client Result Cache
-------------------

Python-oracledb applications can use Oracle Database's `Client Result Cache
<https://www.oracle.com/pls/topic/lookup?ctx=dblatest&id=GUID-35CB2592-7588-4C2D-9075-6F639F25425E>`__
The CRC enables client-side caching of SQL query (SELECT statement) results in
client memory for immediate use when the same query is re-executed.  This is
useful for reducing the cost of queries for small, mostly static, lookup tables,
such as for postal codes.  CRC reduces network :ref:`round-trips <roundtrips>`,
and also reduces database server CPU usage.

.. note::

  Client Result Caching is only supported in the python-oracledb Thick mode.
  See :ref:`enablingthick`.

The cache is at the application process level.  Access and invalidation is
managed by the Oracle Client libraries.  This removes the need for extra
application logic, or external utilities, to implement a cache.

CRC can be enabled by setting the `database parameters
<https://www.oracle.com/pls/topic/lookup?ctx=dblatest&id=GUID-A9D4A5F5-B939-48FF-80AE-0228E7314C7D>`__
``CLIENT_RESULT_CACHE_SIZE`` and ``CLIENT_RESULT_CACHE_LAG``, and then
restarting the database.  For example, to set the parameters:

.. code-block:: sql

    SQL> ALTER SYSTEM SET CLIENT_RESULT_CACHE_LAG = 3000 SCOPE=SPFILE;
    SQL> ALTER SYSTEM SET CLIENT_RESULT_CACHE_SIZE = 64K SCOPE=SPFILE;

CRC can alternatively be configured in an :ref:`oraaccess.xml <optclientfiles>`
or :ref:`sqlnet.ora <optnetfiles>` file on the Python host, see `Client
Configuration Parameters
<https://www.oracle.com/pls/topic/lookup?ctx=dblatest&id=GUID-E63D75A1-FCAA-4A54-A3D2-B068442CE766>`__.

Tables can then be created, or altered, so repeated queries use CRC.  This
allows existing applications to use CRC without needing modification.  For example:

.. code-block:: sql

    SQL> CREATE TABLE cities (id number, name varchar2(40)) RESULT_CACHE (MODE FORCE);
    SQL> ALTER TABLE locations RESULT_CACHE (MODE FORCE);

Alternatively, hints can be used in SQL statements.  For example:

.. code-block:: sql

    SELECT /*+ result_cache */ postal_code FROM locations


.. _fetching-raw-data:

Fetching Raw Data
-----------------

Sometimes python-oracledb may have problems converting data stored in the database to
Python strings. This can occur if the data stored in the database does not match
the character set defined by the database. The ``encoding_errors`` parameter to
:meth:`Cursor.var()` permits the data to be returned with some invalid data
replaced, but for additional control the parameter ``bypass_decode`` can be set
to True and python-oracledb will bypass the decode step and return `bytes` instead
of `str` for data stored in the database as strings. The data can then be
examined and corrected as required. This approach should only be used for
troubleshooting and correcting invalid data, not for general use!

The following sample demonstrates how to use this feature:

    .. code-block:: python

        # define output type handler
        def return_strings_as_bytes(cursor, name, default_type, size,
                                    precision, scale):
            if default_type == oracledb.DB_TYPE_VARCHAR:
                return cursor.var(str, arraysize=cursor.arraysize,
                                  bypass_decode=True)

        # set output type handler on cursor before fetching data
        with connection.cursor() as cursor:
            cursor.outputtypehandler = return_strings_as_bytes
            cursor.execute("select content, charset from SomeTable")
            data = cursor.fetchall()

This will produce output as::

    [(b'Fianc\xc3\xa9', b'UTF-8')]


Note that last ``\xc3\xa9`` is é in UTF-8. Since this is valid UTF-8 you can then
perform a decode on the data (the part that was bypassed):

    .. code-block:: python

        value = data[0][0].decode("UTF-8")

This will return the value "Fiancé".

If you want to save ``b'Fianc\xc3\xa9'`` into the database directly without
using a Python string, you will need to create a variable using
:meth:`Cursor.var()` that specifies the type as
:data:`~oracledb.DB_TYPE_VARCHAR` (otherwise the value will be treated as
:data:`~oracledb.DB_TYPE_RAW`). The following sample demonstrates this:

    .. code-block:: python

        with oracledb.connect(user="hr", password=userpwd,
                               dsn="dbhost.example.com/orclpdb") as conn:
            with conn.cursor() cursor:
                var = cursor.var(oracledb.DB_TYPE_VARCHAR)
                var.setvalue(0, b"Fianc\xc4\x9b")
                cursor.execute("""
                    update SomeTable set
                        SomeColumn = :param
                    where id = 1""",
                    param=var)

.. warning::

    The database will assume that the bytes provided are in the character set
    expected by the database so only use this for troubleshooting or as
    directed.


.. _codecerror:

Querying Corrupt Data
---------------------

If queries fail with the error "codec can't decode byte" when you select data,
then:

* Check if your :ref:`character set <globalization>` is correct.  Review the
  :ref:`database character sets <findingcharset>`.  Check with
  :ref:`fetching-raw-data`. Note that the encoding used for all character
  data in python-oracledb is "UTF-8".

* Check for corrupt data in the database.

If data really is corrupt, you can pass options to the internal `decode()
<https://docs.python.org/3/library/stdtypes.html#bytes.decode>`__ used by
python-oracledb to allow it to be selected and prevent the whole query failing.  Do
this by creating an :ref:`outputtypehandler <outputtypehandlers>` and setting
``encoding_errors``.  For example to replace corrupt characters in character
columns:

.. code-block:: python

    def output_type_handler(cursor, name, default_type, size, precision, scale):
        if default_type == oracledb.DB_TYPE_VARCHAR:
            return cursor.var(default_type, size, arraysize=cursor.arraysize,
                              encoding_errors="replace")

    cursor.outputtypehandler = output_type_handler

    cursor.execute("select column1, column2 from SomeTableWithBadData")

Other codec behaviors can be chosen for ``encoding_errors``, see `Error Handlers
<https://docs.python.org/3/library/codecs.html#error-handlers>`__.

.. _dml:


INSERT and UPDATE Statements
============================

SQL Data Manipulation Language statements (DML) such as INSERT and UPDATE can
easily be executed with python-oracledb.  For example:

.. code-block:: python

    cur = connection.cursor()
    cur.execute("insert into MyTable values (:idbv, :nmbv)", [1, "Fredico"])

Do not concatenate or interpolate user data into SQL statements.  See
:ref:`bind` instead.

See :ref:`txnmgmnt` for best practices on committing and rolling back data
changes.

When handling multiple data values, use :meth:`~Cursor.executemany()` for
performance.  See :ref:`batchstmnt`


Inserting NULLs
---------------

Oracle requires a type, even for null values. When you pass the value None, then
python-oracledb assumes the type is STRING.  If this is not the desired type, you can
explicitly set it.  For example, to insert a null :ref:`Oracle Spatial
SDO_GEOMETRY <spatial>` object:

.. code-block:: python

    type_obj = connection.gettype("SDO_GEOMETRY")
    cur = connection.cursor()
    cur.setinputsizes(type_obj)
    cur.execute("insert into sometable values (:1)", [None])
