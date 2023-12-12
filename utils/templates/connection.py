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

# -----------------------------------------------------------------------------
# connection.py
#
# Contains the Connection class and the factory method connect() used for
# establishing connections to the database.
#
# # {{ generated_notice }}
# -----------------------------------------------------------------------------

import collections
import functools

import oracledb

from . import __name__ as MODULE_NAME

from typing import Any, Callable, Type, Union
from . import constants, driver_mode, errors
from . import base_impl, thick_impl, thin_impl
from . import pool as pool_module
from .connect_params import ConnectParams
from .cursor import Cursor
from .lob import LOB
from .subscr import Subscription
from .aq import Queue, MessageProperties
from .soda import SodaDatabase
from .dbobject import DbObjectType, DbObject
from .base_impl import DB_TYPE_BLOB, DB_TYPE_CLOB, DB_TYPE_NCLOB, DbType

# named tuple used for representing global transactions
Xid = collections.namedtuple(
    "Xid", ["format_id", "global_transaction_id", "branch_qualifier"]
)


class Connection:
    __module__ = MODULE_NAME

    def __init__(
        self,
        dsn: str = None,
        *,
        pool: "pool_module.ConnectionPool" = None,
        params: ConnectParams = None,
        **kwargs,
    ) -> None:
        """
        Constructor for creating a connection to the database.

        The dsn parameter (data source name) can be a string in the format
        user/password@connect_string or can simply be the connect string (in
        which case authentication credentials such as the username and password
        need to be specified separately). See the documentation on connection
        strings for more information.

        The pool parameter is expected to be a pool object and the use of this
        parameter is the equivalent of calling acquire() on the pool.

        The params parameter is expected to be of type ConnectParams and
        contains connection parameters that will be used when establishing the
        connection. See the documentation on ConnectParams for more
        information. If this parameter is not specified, the additional keyword
        parameters will be used to create an instance of ConnectParams. If both
        the params parameter and additional keyword parameters are specified,
        the values in the keyword parameters have precedence. Note that if a
        dsn is also supplied, then in the python-oracledb Thin mode, the values
        of the parameters specified (if any) within the dsn will override the
        values passed as additional keyword parameters, which themselves
        override the values set in the params parameter object.
        """

        # if this variable is not present, exceptions raised during
        # construction can result in cascading exceptions; the __repr__()
        # method depends on this variable being present, too, so make it
        # available first thing
        self._impl = None

        # determine if thin mode is being used
        with driver_mode.get_manager() as mode_mgr:
            thin = mode_mgr.thin

            # determine which connection parameters to use
            if params is None:
                params_impl = base_impl.ConnectParamsImpl()
            elif not isinstance(params, ConnectParams):
                errors._raise_err(errors.ERR_INVALID_CONNECT_PARAMS)
            else:
                params_impl = params._impl.copy()
            dsn = params_impl.process_args(dsn, kwargs, thin)

            # see if connection is being acquired from a pool
            if pool is None:
                pool_impl = None
            else:
                pool._verify_open()
                pool_impl = pool._impl

            # create thin or thick implementation object
            if thin:
                if pool is not None:
                    impl = pool_impl.acquire(params_impl)
                else:
                    impl = thin_impl.ThinConnImpl(dsn, params_impl)
                    impl.connect(params_impl)
            else:
                impl = thick_impl.ThickConnImpl(dsn, params_impl)
                impl.connect(params_impl, pool_impl)
            self._impl = impl
            self._version = None

            # invoke callback, if applicable
            if (
                impl.invoke_session_callback
                and pool is not None
                and pool.session_callback is not None
                and callable(pool.session_callback)
            ):
                pool.session_callback(self, params_impl.tag)
                impl.invoke_session_callback = False

    def __del__(self):
        if self._impl is not None:
            self._impl.close(in_del=True)
            self._impl = None

    def __enter__(self):
        self._verify_connected()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self._impl is not None:
            self._impl.close(in_del=True)
            self._impl = None

    def __repr__(self):
        typ = type(self)
        cls_name = f"{typ.__module__}.{typ.__qualname__}"
        if self._impl is None:
            return f"<{cls_name} disconnected>"
        elif self.username is None:
            return f"<{cls_name} to externally identified user>"
        return f"<{cls_name} to {self.username}@{self.dsn}>"

    def _get_oci_attr(
        self, handle_type: int, attr_num: int, attr_type: int
    ) -> Any:
        """
        Returns the value of the specified OCI attribute from the internal
        handle. This is only supported in python-oracledb thick mode and should
        only be used as directed by Oracle.
        """
        self._verify_connected()
        return self._impl._get_oci_attr(handle_type, attr_num, attr_type)

    def _set_oci_attr(
        self, handle_type: int, attr_num: int, attr_type: int, value: Any
    ) -> None:
        """
        Sets the value of the specified OCI attribute on the internal handle.
        This is only supported in python-oracledb thick mode and should only
        be used as directed by Oracle.
        """
        self._verify_connected()
        self._impl._set_oci_attr(handle_type, attr_num, attr_type, value)

    def _verify_connected(self) -> None:
        """
        Verifies that the connection is connected to the database. If it is
        not, an exception is raised.
        """
        if self._impl is None:
            errors._raise_err(errors.ERR_NOT_CONNECTED)

    def _verify_xid(self, xid: Xid) -> None:
        """
        Verifies that the supplied xid is of the correct type.
        """
        if not isinstance(xid, Xid):
            message = "expecting transaction id created with xid()"
            raise TypeError(message)

    @property
    def action(self) -> None:
        raise AttributeError("action is not readable")

    @action.setter
    def action(self, value: str) -> None:
        """
        Specifies the action column in the v$session table. It is a string
        attribute but the value None is also accepted and treated as an empty
        string.
        """
        self._verify_connected()
        self._impl.set_action(value)

    @property
    def autocommit(self) -> bool:
        """
        Specifies whether autocommit mode is on or off. When autocommit mode is
        on, all statements are committed as soon as they have completed
        executing successfully.
        """
        self._verify_connected()
        return self._impl.autocommit

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        self._verify_connected()
        self._impl.autocommit = value

    def begin(
        self,
        format_id: int = -1,
        transaction_id: str = "",
        branch_id: str = "",
    ) -> None:
        """
        Deprecated. Use tpc_begin() instead.
        """
        if format_id != -1:
            self.tpc_begin(self.xid(format_id, transaction_id, branch_id))

    @property
    def call_timeout(self) -> int:
        """
        Specifies the amount of time (in milliseconds) that a single round-trip
        to the database may take before a timeout will occur. A value of 0
        means that no timeout will take place.
        """
        self._verify_connected()
        return self._impl.get_call_timeout()

    @call_timeout.setter
    def call_timeout(self, value: int) -> None:
        self._verify_connected()
        self._impl.set_call_timeout(value)

    @property
    def callTimeout(self) -> int:
        """
        Deprecated. Use property call_timeout instead.
        """
        return self.call_timeout

    @callTimeout.setter
    def callTimeout(self, value: int) -> None:
        self._verify_connected()
        self._impl.set_call_timeout(value)

    def cancel(self) -> None:
        """
        Break a long-running transaction.
        """
        self._verify_connected()
        self._impl.cancel()

    def changepassword(self, old_password: str, new_password: str) -> None:
        """
        Changes the password for the user to which the connection is connected.
        """
        self._verify_connected()
        self._impl.change_password(old_password, new_password)

    @property
    def client_identifier(self) -> None:
        raise AttributeError("client_identifier is not readable")

    @client_identifier.setter
    def client_identifier(self, value: str) -> None:
        """
        Specifies the client_identifier column in the v$session table.
        """
        self._verify_connected()
        self._impl.set_client_identifier(value)

    @property
    def clientinfo(self) -> None:
        raise AttributeError("clientinfo is not readable")

    @clientinfo.setter
    def clientinfo(self, value: str) -> None:
        """
        Specifies the client_info column in the v$session table.
        """
        self._verify_connected()
        self._impl.set_client_info(value)

    def close(self) -> None:
        """
        Closes the connection and makes it unusable for further operations. An
        Error exception will be raised if any operation is attempted with this
        connection after this method completes successfully.
        """
        self._verify_connected()
        self._impl.close()
        self._impl = None

    def commit(self) -> None:
        """
        Commits any pending transactions to the database.
        """
        self._verify_connected()
        self._impl.commit()

    def createlob(self, lob_type: DbType) -> LOB:
        """
        Create and return a new temporary LOB of the specified type.
        """
        self._verify_connected()
        if lob_type not in (DB_TYPE_CLOB, DB_TYPE_NCLOB, DB_TYPE_BLOB):
            message = (
                "parameter should be one of oracledb.DB_TYPE_CLOB, "
                "oracledb.DB_TYPE_BLOB or oracledb.DB_TYPE_NCLOB"
            )
            raise TypeError(message)
        impl = self._impl.create_temp_lob_impl(lob_type)
        return LOB._from_impl(impl)

    @property
    def current_schema(self) -> str:
        """
        Specifies the current schema for the session. Setting this value is the
        same as executing the SQL statement "ALTER SESSION SET CURRENT_SCHEMA".
        The attribute is set (and verified) on the next call that does a round
        trip to the server. The value is placed before unqualified database
        objects in SQL statements you then execute.
        """
        self._verify_connected()
        return self._impl.get_current_schema()

    @current_schema.setter
    def current_schema(self, value: str) -> None:
        self._verify_connected()
        self._impl.set_current_schema(value)

    def cursor(self, scrollable: bool = False) -> Cursor:
        """
        Returns a cursor associated with the connection.
        """
        self._verify_connected()
        return Cursor(self, scrollable)

    @property
    def dbop(self) -> None:
        raise AttributeError("dbop is not readable")

    @dbop.setter
    def dbop(self, value: str) -> None:
        """
        Specifies the database operation that is to be monitored. This can be
        viewed in the DBOP_NAME column of the V$SQL_MONITOR table.
        """
        self._verify_connected()
        self._impl.set_dbop(value)

    @property
    def dsn(self) -> str:
        """
        Specifies the connection string (TNS entry) of the database to which a
        connection has been established.
        """
        self._verify_connected()
        return self._impl.dsn

    @property
    def econtext_id(self) -> None:
        raise AttributeError("econtext_id is not readable")

    @econtext_id.setter
    def econtext_id(self, value: str) -> None:
        """
        Specifies the execution context id. This value can be found as ecid in
        the v$session table and econtext_id in the auditing tables. The maximum
        length is 64 bytes.
        """
        self._verify_connected()
        self._impl.set_econtext_id(value)

    @property
    def db_domain(self) -> str:
        """
        Specifies the name of the database domain.
        """
        self._verify_connected()
        return self._impl.get_db_domain()

    @property
    def db_name(self) -> str:
        """
        Specifies the name of the database.
        """
        self._verify_connected()
        return self._impl.get_db_name()

    @property
    def edition(self) -> str:
        """
        Specifies the session edition.
        """
        self._verify_connected()
        return self._impl.get_edition()

    @property
    def encoding(self) -> str:
        """
        Specifies the IANA character set name of the character set in use. This
        is always the value "UTF-8".
        """
        return "UTF-8"

    @property
    def external_name(self) -> str:
        """
        Specifies the external name that is used by the connection when logging
        distributed transactions.
        """
        self._verify_connected()
        return self._impl.get_external_name()

    @external_name.setter
    def external_name(self, value: str) -> None:
        self._verify_connected()
        self._impl.set_external_name(value)

    def getSodaDatabase(self) -> SodaDatabase:
        """
        Return a SODA database object for performing all operations on Simple
        Oracle Document Access (SODA).
        """
        self._verify_connected()
        db_impl = self._impl.create_soda_database_impl(self)
        return SodaDatabase._from_impl(self, db_impl)

    def gettype(self, name: str) -> DbObjectType:
        """
        Return a type object given its name. This can then be used to create
        objects which can be bound to cursors created by this connection.
        """
        self._verify_connected()
        obj_type_impl = self._impl.get_type(self, name)
        return DbObjectType._from_impl(obj_type_impl)

    @property
    def handle(self) -> int:
        """
        Returns the OCI service context handle for the connection. It is
        primarily provided to facilitate testing the creation of a connection
        using the OCI service context handle.

        This property is only relevant to python-oracledb's thick mode.
        """
        self._verify_connected()
        return self._impl.get_handle()

    @property
    def inputtypehandler(self) -> Callable:
        """
        Specifies a method called for each value that is bound to a statement
        executed on any cursor associated with this connection. The method
        signature is handler(cursor, value, arraysize) and the return value is
        expected to be a variable object or None in which case a default
        variable object will be created. If this attribute is None, the default
        behavior will take place for all values bound to statements.
        """
        self._verify_connected()
        return self._impl.inputtypehandler

    @inputtypehandler.setter
    def inputtypehandler(self, value: Callable) -> None:
        self._verify_connected()
        self._impl.inputtypehandler = value

    @property
    def instance_name(self) -> str:
        """
        Returns the instance name associated with the connection. This is the
        equivalent of the SQL expression:

        sys_context('userenv', 'instance_name')
        """
        self._verify_connected()
        return self._impl.get_instance_name()

    @property
    def internal_name(self) -> str:
        """
        Specifies the internal name that is used by the connection when logging
        distributed transactions.
        """
        self._verify_connected()
        return self._impl.get_internal_name()

    @internal_name.setter
    def internal_name(self, value: str) -> None:
        self._verify_connected()
        self._impl.set_internal_name(value)

    def is_healthy(self) -> bool:
        """
        Returns a boolean indicating the health status of a connection.

        Connections may become unusable in several cases, such as if the
        network socket is broken, if an Oracle error indicates the connection
        is unusable, or after receiving a planned down notification from the
        database.

        This function is best used before starting a new database request on an
        existing standalone connection. Pooled connections internally perform
        this check before returning a connection to the application.

        If this function returns False, the connection should be not be used by
        the application and a new connection should be established instead.

        This function performs a local check. To fully check a connection's
        health, use ping() which performs a round-trip to the database.
        """
        return self._impl is not None and self._impl.get_is_healthy()

    @property
    def ltxid(self) -> bytes:
        """
        Returns the logical transaction id for the connection. It is used
        within Oracle Transaction Guard as a means of ensuring that
        transactions are not duplicated. See the Oracle documentation and the
        provided sample for more information.
        """
        self._verify_connected()
        return self._impl.get_ltxid()

    @property
    def maxBytesPerCharacter(self) -> int:
        """
        Deprecated. Use the constant value 4 instead.
        """
        return 4

    @property
    def max_open_cursors(self) -> int:
        """
        Specifies the maximum number of cursors that the database can have open
        concurrently.
        """
        self._verify_connected()
        return self._impl.get_max_open_cursors()

    @property
    def module(self) -> None:
        raise AttributeError("module is not readable")

    @module.setter
    def module(self, value: str) -> None:
        """
        Specifies the module column in the v$session table. The maximum length
        for this string is 48 and if you exceed this length you will get
        ORA-24960.
        """
        self._verify_connected()
        self._impl.set_module(value)

    def msgproperties(
        self,
        payload: Union[bytes, str, DbObject] = None,
        correlation: str = None,
        delay: int = None,
        exceptionq: str = None,
        expiration: int = None,
        priority: int = None,
        recipients: list = None,
    ) -> MessageProperties:
        """
        Create and return a message properties object. If the parameters are
        not None, they act as a shortcut for setting each of the equivalently
        named properties.
        """
        impl = self._impl.create_msg_props_impl()
        props = MessageProperties._from_impl(impl)
        if payload is not None:
            props.payload = payload
        if correlation is not None:
            props.correlation = correlation
        if delay is not None:
            props.delay = delay
        if exceptionq is not None:
            props.exceptionq = exceptionq
        if expiration is not None:
            props.expiration = expiration
        if priority is not None:
            props.priority = priority
        if recipients is not None:
            props.recipients = recipients
        return props

    @property
    def nencoding(self) -> str:
        """
        Specifies the IANA character set name of the national character set in
        use. This is always the value "UTF-8".
        """
        return "UTF-8"

    @property
    def outputtypehandler(self) -> Callable:
        """
        Specifies a method called for each column that is going to be fetched
        from any cursor associated with this connection. The method signature
        is handler(cursor, name, defaultType, length, precision, scale) and the
        return value is expected to be a variable object or None in which case
        a default variable object will be created. If this attribute is None,
        the default behavior will take place for all columns fetched from
        cursors associated with this connection.
        """
        self._verify_connected()
        return self._impl.outputtypehandler

    @outputtypehandler.setter
    def outputtypehandler(self, value: Callable) -> None:
        self._verify_connected()
        self._impl.outputtypehandler = value

    def ping(self) -> None:
        """
        Pings the database to verify the connection is valid.
        """
        self._verify_connected()
        self._impl.ping()

    def prepare(self) -> bool:
        """
        Deprecated. Use tpc_prepare() instead.
        """
        return self.tpc_prepare()

    @property
    def proxy_user(self) -> Union[str, None]:
        """
        Returns the name of the proxy user, if applicable.
        """
        self._verify_connected()
        return self._impl.proxy_user

    def queue(
        self,
        name: str,
        payload_type: Union[DbObjectType, str] = None,
        *,
        payloadType: DbObjectType = None,
    ) -> Queue:
        """
        Creates and returns a queue which is used to enqueue and dequeue
        messages in Advanced Queueing (AQ).

        The name parameter is expected to be a string identifying the queue in
        which messages are to be enqueued or dequeued.

        The payload_type parameter, if specified, is expected to be an
        object type that identifies the type of payload the queue expects.
        If the string "JSON" is specified, JSON data is enqueued and dequeued.
        If not specified, RAW data is enqueued and dequeued.
        """
        self._verify_connected()
        payload_type_impl = None
        is_json = False
        if payloadType is not None:
            if payload_type is not None:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="payloadType",
                    new_name="payload_type",
                )
            payload_type = payloadType
        if payload_type is not None:
            if payload_type == "JSON":
                is_json = True
            elif not isinstance(payload_type, DbObjectType):
                raise TypeError("expecting DbObjectType")
            else:
                payload_type_impl = payload_type._impl
        impl = self._impl.create_queue_impl()
        impl.initialize(self._impl, name, payload_type_impl, is_json)
        return Queue._from_impl(self, impl)

    def rollback(self) -> None:
        """
        Rolls back any pending transactions.
        """
        self._verify_connected()
        self._impl.rollback()

    @property
    def service_name(self) -> str:
        """
        Specifies the name of the service that was used to connect to the
        database.
        """
        self._verify_connected()
        return self._impl.get_service_name()

    def shutdown(self, mode: int = 0) -> None:
        """
        Shutdown the database. In order to do this the connection must be
        connected as SYSDBA or SYSOPER. Two calls must be made unless the mode
        specified is DBSHUTDOWN_ABORT.
        """
        self._verify_connected()
        self._impl.shutdown(mode)

    def startup(
        self, force: bool = False, restrict: bool = False, pfile: str = None
    ) -> None:
        """
        Startup the database. This is equivalent to the SQL*Plus command
        “startup nomount”. The connection must be connected as SYSDBA or
        SYSOPER with the PRELIM_AUTH option specified for this to work.

        The pfile parameter, if specified, is expected to be a string
        identifying the location of the parameter file (PFILE) which will be
        used instead of the stored parameter file (SPFILE).
        """
        self._verify_connected()
        self._impl.startup(force, restrict, pfile)

    @property
    def stmtcachesize(self) -> int:
        """
        Specifies the size of the statement cache. This value can make a
        significant difference in performance (up to 100x) if you have a small
        number of statements that you execute repeatedly.
        """
        self._verify_connected()
        return self._impl.get_stmt_cache_size()

    @stmtcachesize.setter
    def stmtcachesize(self, value: int) -> None:
        self._verify_connected()
        self._impl.set_stmt_cache_size(value)

    def subscribe(
        self,
        namespace: int = constants.SUBSCR_NAMESPACE_DBCHANGE,
        protocol: int = constants.SUBSCR_PROTO_CALLBACK,
        callback: Callable = None,
        timeout: int = 0,
        operations: int = constants.OPCODE_ALLOPS,
        port: int = 0,
        qos: int = constants.SUBSCR_QOS_DEFAULT,
        ip_address: str = None,
        grouping_class: int = constants.SUBSCR_GROUPING_CLASS_NONE,
        grouping_value: int = 0,
        grouping_type: int = constants.SUBSCR_GROUPING_TYPE_SUMMARY,
        name: str = None,
        client_initiated: bool = False,
        *,
        ipAddress: str = None,
        groupingClass: int = constants.SUBSCR_GROUPING_CLASS_NONE,
        groupingValue: int = 0,
        groupingType: int = constants.SUBSCR_GROUPING_TYPE_SUMMARY,
        clientInitiated: bool = False,
    ) -> Subscription:
        """
        Return a new subscription object that receives notification for events
        that take place in the database that match the given parameters.

        The namespace parameter specifies the namespace the subscription uses.
        It can be one of SUBSCR_NAMESPACE_DBCHANGE or SUBSCR_NAMESPACE_AQ.

        The protocol parameter specifies the protocol to use when notifications
        are sent. Currently the only valid value is SUBSCR_PROTO_CALLBACK.

        The callback is expected to be a callable that accepts a single
        parameter. A message object is passed to this callback whenever a
        notification is received.

        The timeout value specifies that the subscription expires after the
        given time in seconds. The default value of 0 indicates that the
        subscription never expires.

        The operations parameter enables filtering of the messages that are
        sent (insert, update, delete). The default value will send
        notifications for all operations. This parameter is only used when the
        namespace is set to SUBSCR_NAMESPACE_DBCHANGE.

        The port parameter specifies the listening port for callback
        notifications from the database server. If not specified, an unused
        port will be selected by the Oracle Client libraries.

        The qos parameter specifies quality of service options. It should be
        one or more of the following flags, OR'ed together:
        SUBSCR_QOS_RELIABLE,
        SUBSCR_QOS_DEREG_NFY,
        SUBSCR_QOS_ROWIDS,
        SUBSCR_QOS_QUERY,
        SUBSCR_QOS_BEST_EFFORT.

        The ip_address parameter specifies the IP address (IPv4 or IPv6) in
        standard string notation to bind for callback notifications from the
        database server. If not specified, the client IP address will be
        determined by the Oracle Client libraries.

        The grouping_class parameter specifies what type of grouping of
        notifications should take place. Currently, if set, this value can
        only be set to the value SUBSCR_GROUPING_CLASS_TIME, which will group
        notifications by the number of seconds specified in the grouping_value
        parameter. The grouping_type parameter should be one of the values
        SUBSCR_GROUPING_TYPE_SUMMARY (the default) or
        SUBSCR_GROUPING_TYPE_LAST.

        The name parameter is used to identify the subscription and is specific
        to the selected namespace. If the namespace parameter is
        SUBSCR_NAMESPACE_DBCHANGE then the name is optional and can be any
        value. If the namespace parameter is SUBSCR_NAMESPACE_AQ, however, the
        name must be in the format '<QUEUE_NAME>' for single consumer queues
        and '<QUEUE_NAME>:<CONSUMER_NAME>' for multiple consumer queues, and
        identifies the queue that will be monitored for messages. The queue
        name may include the schema, if needed.

        The client_initiated parameter is used to determine if client initiated
        connections or server initiated connections (the default) will be
        established. Client initiated connections are only available in Oracle
        Client 19.4 and Oracle Database 19.4 and higher.
        """
        self._verify_connected()
        if ipAddress is not None:
            if ip_address is not None:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="ipAddress",
                    new_name="ip_address",
                )
            ip_address = ipAddress
        if groupingClass != constants.SUBSCR_GROUPING_CLASS_NONE:
            if grouping_class != constants.SUBSCR_GROUPING_CLASS_NONE:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="groupingClass",
                    new_name="grouping_class",
                )
            grouping_class = groupingClass
        if groupingValue != 0:
            if grouping_value != 0:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="groupingValue",
                    new_name="grouping_value",
                )
            grouping_value = groupingValue
        if groupingType != constants.SUBSCR_GROUPING_TYPE_SUMMARY:
            if grouping_type != constants.SUBSCR_GROUPING_TYPE_SUMMARY:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="groupingType",
                    new_name="grouping_type",
                )
            grouping_type = groupingType
        if clientInitiated:
            if client_initiated:
                errors._raise_err(
                    errors.ERR_DUPLICATED_PARAMETER,
                    deprecated_name="clientInitiated",
                    new_name="client_initiated",
                )
            client_initiated = clientInitiated
        impl = self._impl.create_subscr_impl(
            self,
            callback,
            namespace,
            name,
            protocol,
            ip_address,
            port,
            timeout,
            operations,
            qos,
            grouping_class,
            grouping_value,
            grouping_type,
            client_initiated,
        )
        subscr = Subscription._from_impl(impl)
        impl.subscribe(subscr, self._impl)
        return subscr

    @property
    def tag(self) -> str:
        """
        This property initially contains the actual tag of the session that was
        acquired from a pool. If the connection was not acquired from a pool or
        no tagging parameters were specified (tag and matchanytag) when the
        connection was acquired from the pool, this value will be None. If the
        value is changed, it must be a string containing name=value pairs like
        “k1=v1;k2=v2”.

        If this value is not None when the connection is released back to the
        pool it will be used to retag the session. This value can be overridden
        in the call to SessionPool.release().
        """
        self._verify_connected()
        return self._impl.tag

    @tag.setter
    def tag(self, value: str) -> None:
        self._verify_connected()
        self._impl.tag = value

    @property
    def thin(self) -> bool:
        """
        Returns a boolean indicating if the connection was established in
        python-oracledb's thin mode (True) or thick mode (False).
        """
        self._verify_connected()
        return isinstance(self._impl, thin_impl.ThinConnImpl)

    @property
    def tnsentry(self) -> str:
        """
        Deprecated. Use dsn property instead.
        """
        return self.dsn

    def tpc_begin(
        self, xid: Xid, flags: int = constants.TPC_BEGIN_NEW, timeout: int = 0
    ) -> None:
        """
        Begins a TPC (two-phase commit) transaction with the given transaction
        id. This method should be called outside of a transaction (i.e. nothing
        may have executed since the last commit() or rollback() was performed).
        """
        self._verify_connected()
        self._verify_xid(xid)
        self._impl.tpc_begin(xid, flags, timeout)

    def tpc_commit(self, xid: Xid = None, one_phase: bool = False) -> None:
        """
        Prepare the global transaction for commit. Return a boolean indicating
        if a transaction was actually prepared in order to avoid the error
        ORA-24756 (transaction does not exist).

        When called with no arguments, commits a transaction previously
        prepared with tpc_prepare(). If tpc_prepare() is not called, a single
        phase commit is performed. A transaction manager may choose to do this
        if only a single resource is participating in the global transaction.

        When called with a transaction id, the database commits the given
        transaction. This form should be called outside of a transaction and is
        intended for use in recovery.
        """
        self._verify_connected()
        if xid is not None:
            self._verify_xid(xid)
        self._impl.tpc_commit(xid, one_phase)

    def tpc_end(
        self, xid: Xid = None, flags: int = constants.TPC_END_NORMAL
    ) -> None:
        """
        Ends (detaches from) a TPC (two-phase commit) transaction.
        """
        self._verify_connected()
        if xid is not None:
            self._verify_xid(xid)
        self._impl.tpc_end(xid, flags)

    def tpc_forget(self, xid: Xid) -> None:
        """
        Forgets a TPC (two-phase commit) transaction.
        """
        self._verify_connected()
        self._verify_xid(xid)
        self._impl.tpc_forget(xid)

    def tpc_prepare(self, xid: Xid = None) -> bool:
        """
        Prepares a global transaction for commit. After calling this function,
        no further activity should take place on this connection until either
        tpc_commit() or tpc_rollback() have been called.

        A boolean is returned indicating whether a commit is needed or not. If
        a commit is performed when one is not needed the error ORA-24756:
        transaction does not exist is raised.
        """
        self._verify_connected()
        if xid is not None:
            self._verify_xid(xid)
        return self._impl.tpc_prepare(xid)

    def tpc_recover(self) -> list:
        """
        Returns a list of pending transaction ids suitable for use with
        tpc_commit() or tpc_rollback().

        This function requires select privilege on the view
        DBA_PENDING_TRANSACTIONS.
        """
        with self.cursor() as cursor:
            cursor.rowfactory = Xid
            cursor.execute(
                """
                    select
                        formatid,
                        globalid,
                        branchid
                    from dba_pending_transactions"""
            )
            return cursor.fetchall()

    def tpc_rollback(self, xid: Xid = None) -> None:
        """
        When called with no arguments, rolls back the transaction previously
        started with tpc_begin().

        When called with a transaction id, the database rolls back the given
        transaction. This form should be called outside of a transaction and is
        intended for use in recovery.
        """
        self._verify_connected()
        if xid is not None:
            self._verify_xid(xid)
        self._impl.tpc_rollback(xid)

    @property
    def transaction_in_progress(self) -> bool:
        """
        Specifies whether a transaction is currently in progress on the
        database using this connection.
        """
        self._verify_connected()
        return self._impl.get_transaction_in_progress()

    def unsubscribe(self, subscr: Subscription) -> None:
        """
        Unsubscribe from events in the database that were originally subscribed
        to using subscribe(). The connection used to unsubscribe should be the
        same one used to create the subscription, or should access the same
        database and be connected as the same user name.
        """
        self._verify_connected()
        if not isinstance(subscr, Subscription):
            raise TypeError("expecting subscription")
        subscr._impl.unsubscribe(self._impl)

    @property
    def username(self) -> str:
        """
        Returns the name of the user which established the connection to the
        database.
        """
        self._verify_connected()
        return self._impl.username

    @property
    def version(self) -> str:
        """
        Returns the version of the database to which the connection has been
        established.
        """
        if self._version is None:
            self._verify_connected()
            self._version = ".".join(str(c) for c in self._impl.server_version)
        return self._version

    @property
    def warning(self) -> errors._Error:
        """
        Returns any warning that was generated when the connection was created,
        or the value None if no warning was generated. The value will be
        cleared for pooled connections after they are returned to the pool.
        """
        self._verify_connected()
        return self._impl.warning

    def xid(
        self,
        format_id: int,
        global_transaction_id: Union[bytes, str],
        branch_qualifier: Union[bytes, str],
    ) -> Xid:
        """
        Returns a global transaction identifier that can be used with the TPC
        (two-phase commit) functions.

        The format_id parameter should be a non-negative 32-bit integer. The
        global_transaction_id and branch_qualifier parameters should be bytes
        (or a string which will be UTF-8 encoded to bytes) of no more than 64
        bytes.
        """
        return Xid(format_id, global_transaction_id, branch_qualifier)


def _connection_factory(f):
    """
    Decorator which checks the validity of the supplied keyword parameters by
    calling the original function (which does nothing), then creates and
    returns an instance of the requested Connection class. The base Connection
    class constructor does not check the validity of the supplied keyword
    parameters.
    """

    @functools.wraps(f)
    def connect(
        dsn: str = None,
        *,
        pool: "pool_module.ConnectionPool" = None,
        conn_class: Type[Connection] = Connection,
        params: ConnectParams = None,
        **kwargs,
    ) -> Connection:
        f(dsn=dsn, pool=pool, conn_class=conn_class, params=params, **kwargs)
        if not issubclass(conn_class, Connection):
            errors._raise_err(errors.ERR_INVALID_CONN_CLASS)
        if pool is not None and not isinstance(
            pool, pool_module.ConnectionPool
        ):
            message = "pool must be an instance of oracledb.ConnectionPool"
            raise TypeError(message)
        return conn_class(dsn=dsn, pool=pool, params=params, **kwargs)

    return connect


@_connection_factory
def connect(
    dsn: str = None,
    *,
    pool: "pool_module.ConnectionPool" = None,
    conn_class: Type[Connection] = Connection,
    params: ConnectParams = None,
    # {{ args_with_defaults }}
) -> Connection:
    """
    Factory function which creates a connection to the database and returns it.

    The dsn parameter (data source name) can be a string in the format
    user/password@connect_string or can simply be the connect string (in
    which case authentication credentials such as the username and password
    need to be specified separately). See the documentation on connection
    strings for more information.

    The pool parameter is expected to be a pool object and the use of this
    parameter is the equivalent of calling pool.acquire().

    The conn_class parameter is expected to be Connection or a subclass of
    Connection.

    The params parameter is expected to be of type ConnectParams and contains
    connection parameters that will be used when establishing the connection.
    See the documentation on ConnectParams for more information. If this
    parameter is not specified, the additional keyword parameters will be used
    to create an instance of ConnectParams. If both the params parameter and
    additional keyword parameters are specified, the values in the keyword
    parameters have precedence. Note that if a dsn is also supplied,
    then in the python-oracledb Thin mode, the values of the parameters
    specified (if any) within the dsn will override the values passed as
    additional keyword parameters, which themselves override the values set in
    the params parameter object.

    The following parameters are all optional. A brief description of each
    parameter follows:

    # {{ args_help_with_defaults }}
    """
    pass
