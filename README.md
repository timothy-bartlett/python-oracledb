# python-oracledb 1.2 (Development)

python-oracledb is a [Python programming language][python] extension module
allowing Python programs to connect to [Oracle Database][oracledb].  It is the
renamed, new major release of the popular cx_Oracle driver.

The module conforms to the [Python Database API 2.0 specification][pep249] with
a considerable number of additions and a couple of minor exclusions, see the
[feature list][features].

## Installation

Run `python -m pip install oracledb`

See [python-oracledb Installation][installation].

## Dependencies and Interoperability

- Python versions 3.6 through 3.11.

  Prebuilt packages are available on Windows for Python 3.7 or later, on macOS
  for Python 3.7 or later, and on Linux for Python 3.6 or later.

  Source code is also available.

- Oracle Client libraries are *optional*.

  **Thin mode**: By default python-oracledb runs in a 'Thin' mode which
  connects directly to Oracle Database.

  **Thick mode**: Some advanced Oracle Database functionality is currently only
  available when optional Oracle Client libraries are loaded by
  python-oracledb.  Libraries are available in the free [Oracle Instant
  Client][instantclient] packages. Python-oracledb can use Oracle Client
  libraries 11.2 through 21c.

- Oracle Database

  **Thin mode**: Oracle Database 12.1 (or later) is required.

  **Thick mode**: Oracle Database 11.2 (or later) is required, depending on the
  Oracle Client library version.  Oracle Database's standard client-server
  version interoperability allows connection to both older and newer
  databases. For example when python-oracledb uses Oracle Client 19c libraries,
  then it can connect to Oracle Database 11.2 or later.

## Documentation

See the [python-oracledb Documentation][documentation] and [Release
Notes][relnotes].

## Samples

Examples can be found in the [/samples][samples] directory and the
[Python and Oracle Database Tutorial][tutorial].

## Help

Questions can be asked in [Github Discussions][ghdiscussions].

Problem reports can be raised in [GitHub Issues][ghissues].

## Tests

See [/tests][tests]

## Contributing

See [CONTRIBUTING](https://github.com/oracle/python-oracledb/blob/main/CONTRIBUTING.md)

## License

See [LICENSE][license], [THIRD_PARTY_LICENSES][tplicense], and [NOTICE][notice].

[python]: https://www.python.org/
[oracledb]: https://www.oracle.com/database/
[instantclient]: https://www.oracle.com/database/technologies/instant-client.html
[pep249]: https://peps.python.org/pep-0249/
[documentation]: http://python-oracledb.readthedocs.io
[relnotes]: https://python-oracledb.readthedocs.io/en/latest/release_notes.html
[license]: https://github.com/oracle/python-oracledb/blob/main/LICENSE.txt
[tplicense]: https://github.com/oracle/python-oracledb/blob/main/THIRD_PARTY_LICENSES.txt
[notice]: https://github.com/oracle/python-oracledb/blob/main/NOTICE.txt
[tutorial]: https://oracle.github.io/python-oracledb/samples/tutorial/Python-and-Oracle-Database-The-New-Wave-of-Scripting.html
[ghdiscussions]: https://github.com/oracle/python-oracledb/discussions
[ghissues]: https://github.com/oracle/python-oracledb/issues
[tests]: https://github.com/oracle/python-oracledb/tree/main/tests
[samples]: https://github.com/oracle/python-oracledb/tree/main/samples
[installation]: https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html
[features]: https://oracle.github.io/python-oracledb/#features
