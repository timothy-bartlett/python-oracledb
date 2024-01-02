#------------------------------------------------------------------------------
# Copyright (c) 2020, 2024, Oracle and/or its affiliates.
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

#------------------------------------------------------------------------------
# protocol.pyx
#
# Cython file defining the protocol used by the client when communicating with
# the database (embedded in thin_impl.pyx).
#------------------------------------------------------------------------------

cdef class BaseProtocol:

    cdef:
        uint8_t _seq_num
        Transport _transport
        Capabilities _caps
        ReadBuffer _read_buf
        WriteBuffer _write_buf
        bint _in_connect
        bint _txn_in_progress
        bint _break_in_progress
        object _request_lock

    def __init__(self):
        self._caps = Capabilities()
        # mark protocol to indicate that connect is in progress; this prevents
        # the normal break/reset mechanism from firing, which is unnecessary
        # since the connection is going to be immediately closed anyway!
        self._in_connect = True
        self._transport = Transport.__new__(Transport)
        self._transport._max_packet_size = self._caps.sdu
        self._read_buf = ReadBuffer(self._transport, self._caps)
        self._write_buf = WriteBuffer(self._transport, self._caps)

    cdef int _break_external(self) except -1:
        """
        Method for sending a break to the server from an external request. A
        separate write buffer is used in order to avoid a potential conflict
        with any in progress writes.
        """
        cdef WriteBuffer buf
        if not self._break_in_progress:
            self._break_in_progress = True
            if self._caps.supports_oob:
                self._transport.send_oob_break()
            else:
                buf = WriteBuffer(self._transport, self._caps)
                self._send_marker(buf, TNS_MARKER_TYPE_INTERRUPT)

    cdef int _final_close(self, WriteBuffer buf) except -1:
        """
        Send the final close packet to the server and close the socket.
        """
        buf.start_request(TNS_PACKET_TYPE_DATA, 0, TNS_DATA_FLAGS_EOF)
        buf.end_request()
        self._transport.disconnect()
        self._transport = None

    cdef int _force_close(self) except -1:
        """
        Forces the connection closed. This is used when an unrecoverable error
        has taken place.
        """
        cdef Transport transport = self._transport
        if transport is not None:
            self._transport = None
            self._read_buf._transport = None
            self._write_buf._transport = None
            transport.disconnect()

    cdef int _send_marker(self, WriteBuffer buf, uint8_t marker_type):
        """
        Sends a marker of the specified type to the server.
        Internal method for sending a break to the server.
        """
        buf.start_request(TNS_PACKET_TYPE_MARKER)
        buf.write_uint8(1)
        buf.write_uint8(0)
        buf.write_uint8(marker_type)
        buf.end_request()


cdef class Protocol(BaseProtocol):

    def __init__(self):
        BaseProtocol.__init__(self)
        self._request_lock = threading.Lock()

    cdef int _close(self, ThinConnImpl conn_impl) except -1:
        """
        Closes the connection. If a transaction is in progress it will be
        rolled back. DRCP sessions will be released. For standalone
        connections, the session will be logged off. For pooled connections,
        the connection will be returned to the pool for subsequent use.
        """
        cdef:
            uint32_t release_mode = DRCP_DEAUTHENTICATE \
                    if conn_impl._pool is None else 0
            ThinPoolImpl pool_impl
            Message message

        with self._request_lock:

            # if a read failed on the socket earlier, clear the socket
            if self._read_buf._transport is None:
                self._transport = None

            # if the session was marked as needing to be closed, force it
            # closed immediately (unless it was already closed)
            if self._read_buf._session_needs_to_be_closed \
                    and self._transport is not None:
                self._force_close()

            # rollback any open transaction and release the DRCP session, if
            # applicable
            if self._transport is not None:
                if self._txn_in_progress:
                    message = conn_impl._create_message(RollbackMessage)
                    self._process_message(message)
                if conn_impl._drcp_enabled:
                    self._release_drcp_session(conn_impl, release_mode)
                    conn_impl._drcp_establish_session = True

            # if the connection is part of a pool, return it to the pool
            if conn_impl._pool is not None:
                pool_impl = <ThinPoolImpl> conn_impl._pool
                return pool_impl._return_connection(conn_impl)

            # otherwise, destroy the database object type cache, send the
            # logoff message and final close packet
            if conn_impl._dbobject_type_cache_num > 0:
                remove_dbobject_type_cache(conn_impl._dbobject_type_cache_num)
                conn_impl._dbobject_type_cache_num = 0
            if self._transport is not None:
                if not conn_impl._drcp_enabled:
                    message = conn_impl._create_message(LogoffMessage)
                    self._process_message(message)
                self._final_close(self._write_buf)

    cdef ConnectionCookie _connect_phase_one(self,
                                             ThinConnImpl conn_impl,
                                             ConnectParamsImpl params,
                                             Description description,
                                             Address address,
                                             str connect_string):
        """
        Method for performing the required steps for establishing a connection
        within the scope of a retry. If the listener refuses the connection, a
        retry will be performed, if retry_count is set.
        """
        cdef:
            ConnectMessage connect_message = None
            uint8_t packet_type, packet_flags = 0
            object ssl_context, connect_info
            ConnectParamsImpl temp_params
            str host, redirect_data
            Address temp_address
            int port, pos

        # store whether OOB processing is possible or not
        self._caps.supports_oob = not params.disable_oob \
                and sys.platform != "win32"

        # establish initial TCP connection and get initial connect string
        host = address.host
        port = address.port
        self._connect_tcp(params, description, address, host, port)

        # send connect message and process response; this may request the
        # message to be resent multiple times; if a redirect packet is
        # detected, a new TCP connection is established first
        while True:

            # create connection message, if needed
            if connect_message is None:
                connect_message = conn_impl._create_message(ConnectMessage)
                connect_message.host = host
                connect_message.port = port
                connect_message.description = description
                connect_message.connect_string_bytes = connect_string.encode()
                connect_message.connect_string_len = \
                        <uint16_t> len(connect_message.connect_string_bytes)
                connect_message.packet_flags = packet_flags

            # process connection message
            self._process_message(connect_message)
            packet_type = self._read_buf._current_packet.packet_type
            if connect_message.redirect_data is not None:
                redirect_data = connect_message.redirect_data
                pos = redirect_data.find('\x00')
                if pos < 0:
                    errors._raise_err(errors.ERR_INVALID_REDIRECT_DATA,
                                      data=redirect_data)
                temp_params = ConnectParamsImpl()
                temp_params._parse_connect_string(redirect_data[:pos])
                temp_address = temp_params._get_addresses()[0]
                host = temp_address.host
                port = temp_address.port
                connect_string = redirect_data[pos + 1:]
                self._connect_tcp(params, description, address, host, port)
                connect_message = None
                packet_flags = TNS_PACKET_FLAG_REDIRECT
            elif packet_type == TNS_PACKET_TYPE_ACCEPT:
                self._transport._max_packet_size = self._caps.sdu
                self._write_buf._size_for_sdu()
                return connect_message.cookie

            # for TCPS connections, OOB processing is not supported; if the
            # packet flags indicate that TLS renegotiation is required, this is
            # performed now
            if address.protocol == "tcps":
                self._caps.supports_oob = False
                packet_flags = self._read_buf._current_packet.packet_flags
                if packet_flags & TNS_PACKET_FLAG_TLS_RENEG:
                    self._transport.renegotiate_tls(description)

    cdef int _connect_phase_two(self, ThinConnImpl conn_impl,
                                ConnectionCookie cookie,
                                Description description,
                                ConnectParamsImpl params) except -1:
        """"
        Method for perfoming the required steps for establishing a connection
        oustide the scope of a retry. If any of the steps in this method fail,
        an exception will be raised.
        """
        cdef:
            ConnectionCookieMessage cookie_message
            DataTypesMessage data_types_message
            ProtocolMessage protocol_message
            AuthMessage auth_message
            bint sent_cookie = False

        # check if the protocol version supported by the database is high
        # enough; if not, reject the connection immediately
        if self._caps.protocol_version < TNS_VERSION_MIN_ACCEPTED:
            errors._raise_err(errors.ERR_SERVER_VERSION_NOT_SUPPORTED)

        # if we can use OOB, send an urgent message now followed by a reset
        # marker to see if the server understands it
        if self._caps.supports_oob \
                and self._caps.protocol_version >= TNS_VERSION_MIN_OOB_CHECK:
            self._transport.send_oob_break()
            self._send_marker(self._write_buf, TNS_MARKER_TYPE_RESET)

        # create the messages that need to be sent to the server
        protocol_message = conn_impl._create_message(ProtocolMessage)
        data_types_message = conn_impl._create_message(DataTypesMessage)
        auth_message = conn_impl._create_message(AuthMessage)
        auth_message._set_params(params, description)

        # starting in 23c, a cookie can be sent along with the protocol, data
        # types and authorization messages without waiting for the server to
        # respond to each of the messages in turn
        if cookie is not None and cookie.populated:
            cookie_message = conn_impl._create_message(ConnectionCookieMessage)
            cookie_message.cookie = cookie
            cookie_message.protocol_message = protocol_message
            cookie_message.data_types_message = data_types_message
            cookie_message.auth_message = auth_message
            self._process_message(cookie_message)
            sent_cookie = True
        else:
            self._process_message(protocol_message)

        # if database is not 23c or later, or renegotiation has been requested,
        # use the regular approach for the remaining messages
        if not sent_cookie or not cookie.populated:
            self._process_message(data_types_message)
            self._process_message(auth_message)
            if cookie is not None and not cookie.populated:
                cookie.protocol_version = protocol_message.server_version
                cookie.server_banner = protocol_message.server_banner
                cookie.charset_id = self._caps.charset_id
                cookie.ncharset_id = self._caps.ncharset_id
                cookie.flags = protocol_message.server_flags
                cookie.compile_caps = protocol_message.server_compile_caps
                cookie.runtime_caps = protocol_message.server_runtime_caps
                cookie.populated = True

        # send authorization message a second time, if needed, to respond to
        # the challenge sent by the server
        if auth_message.resend:
            self._process_message(auth_message)

        # mark protocol to indicate that connect is no longer in progress; this
        # allows the normal break/reset mechanism to fire
        conn_impl.warning = auth_message.warning
        self._in_connect = False

    cdef int _connect_tcp(self, ConnectParamsImpl params,
                          Description description, Address address, str host,
                          int port) except -1:
        """
        Creates a socket on which to communicate using the provided parameters.
        If a proxy is configured, a connection to the proxy is established and
        the target host and port is forwarded to the proxy.
        """
        cdef:
            bint use_proxy = (address.https_proxy is not None)
            double timeout = description.tcp_connect_timeout
            bint use_tcps = (address.protocol == "tcps")
            object connect_info, sock, data, reply, m

        # establish connection to appropriate host/port
        if use_proxy:
            if not use_tcps:
                errors._raise_err(errors.ERR_HTTPS_PROXY_REQUIRES_TCPS)
            connect_info = (address.https_proxy, address.https_proxy_port)
        else:
            connect_info = (host, port)
            if not use_tcps and (params._token is not None
                    or params.access_token_callback is not None):
                errors._raise_err(errors.ERR_ACCESS_TOKEN_REQUIRES_TCPS)
        sock = socket.create_connection(connect_info, timeout)

        # complete connection through proxy, if applicable
        if use_proxy:
            data = f"CONNECT {host}:{port} HTTP/1.0\r\n\r\n"
            sock.send(data.encode())
            reply = sock.recv(1024)
            m = re.search('HTTP/1.[01]\\s+(\\d+)\\s+', reply.decode())
            if m is None or m.groups()[0] != '200':
                errors._raise_err(errors.ERR_PROXY_FAILURE,
                                  response=reply.decode())

        # set socket on transport
        self._transport.set_from_socket(sock, params, description, address)

        # negotiate TLS, if applicable
        if use_tcps:
            self._transport.create_ssl_context(params, description, address)
            self._transport.negotiate_tls(sock, description)

    cdef int _process_message(self, Message message) except -1:
        cdef uint32_t timeout = message.conn_impl._call_timeout
        try:
            self._read_buf.reset_packets()
            message.send(self._write_buf)
            self._receive_packet(message)
            message.process(self._read_buf)
        except socket.timeout:
            try:
                self._break_external()
                self._receive_packet(message)
                self._break_in_progress = False
                errors._raise_err(errors.ERR_CALL_TIMEOUT_EXCEEDED,
                                  timeout=timeout)
            except socket.timeout:
                self._force_close()
                errors._raise_err(errors.ERR_CONNECTION_CLOSED,
                                  "socket timed out while recovering from " \
                                  "previous socket timeout")
            raise
        except Exception as e:
            if not self._in_connect \
                    and self._write_buf._packet_sent \
                    and self._read_buf._transport is not None \
                    and self._read_buf._transport._transport is not None:
                self._send_marker(self._write_buf, TNS_MARKER_TYPE_BREAK)
                self._reset(message)
            raise
        if message.flush_out_binds:
            self._write_buf.start_request(TNS_PACKET_TYPE_DATA)
            self._write_buf.write_uint8(TNS_MSG_TYPE_FLUSH_OUT_BINDS)
            self._write_buf.end_request()
            self._reset(message)
            message.process(self._read_buf)
        if self._break_in_progress:
            try:
                if self._caps.supports_oob:
                    self._send_marker(self._write_buf,
                                      TNS_MARKER_TYPE_INTERRUPT)
                self._receive_packet(message)
            except socket.timeout:
                errors._raise_err(errors.ERR_CONNECTION_CLOSED,
                                  "socket timed out while awaiting break " \
                                  "response from server")
            message.process(self._read_buf)
            self._break_in_progress = False
        self._txn_in_progress = message.call_status & TNS_TXN_IN_PROGRESS
        if message.error_occurred:
            if message.retry:
                message.error_occurred = False
                return self._process_message(message)
            error = errors._Error(message.error_info.message,
                                  code=message.error_info.num,
                                  offset=message.error_info.pos)

            # if a connection has received dead connection error then it is no
            # longer usable
            if error.is_session_dead:
                self._force_close()
            exc_type = get_exception_class(message.error_info.num)
            raise exc_type(error)

    cdef int _process_single_message(self, Message message) except -1:
        """
        Process a single message within a request.
        """
        with self._request_lock:
            self._process_message(message)
            if message.resend:
                self._process_message(message)
        message.postprocess()

    cdef int _receive_packet(self, Message message) except -1:
        cdef:
            ReadBuffer buf = self._read_buf
            uint16_t refuse_message_len
            const char_type* ptr
        buf.wait_for_packets_sync()
        if buf._current_packet.packet_type == TNS_PACKET_TYPE_MARKER:
            self._reset(message)
        elif buf._current_packet.packet_type == TNS_PACKET_TYPE_REFUSE:
            self._write_buf._packet_sent = False
            buf.skip_raw_bytes(2)
            buf.read_uint16(&refuse_message_len)
            if refuse_message_len == 0:
                message.error_info.message = None
            else:
                ptr = buf.read_raw_bytes(refuse_message_len)
                message.error_info.message = ptr[:refuse_message_len].decode()

    cdef int _release_drcp_session(self, ThinConnImpl conn_impl,
                                   uint32_t release_mode) except -1:
        """
        Release the session back to DRCP. Standalone sessions are marked for
        deauthentication.
        """
        cdef SessionReleaseMessage message
        message = conn_impl._create_message(SessionReleaseMessage)
        message.release_mode = release_mode
        message.send(self._write_buf)

    cdef int _reset(self, Message message) except -1:
        cdef uint8_t marker_type, packet_type

        # send reset marker
        self._send_marker(self._write_buf, TNS_MARKER_TYPE_RESET)

        # read and discard all packets until a marker packet is received
        while True:
            packet_type = self._read_buf._current_packet.packet_type
            if packet_type == TNS_PACKET_TYPE_MARKER:
                self._read_buf.skip_raw_bytes(2)
                self._read_buf.read_ub1(&marker_type)
                if marker_type == TNS_MARKER_TYPE_RESET:
                    break
            self._read_buf.wait_for_packets_sync()

        # read error packet; first skip as many marker packets as may be sent
        # by the server; if the server doesn't handle out-of-band breaks
        # properly, some quit immediately and others send multiple reset
        # markers (this addresses both situations without resulting in strange
        # errors)
        while packet_type == TNS_PACKET_TYPE_MARKER:
            self._read_buf.wait_for_packets_sync()
            packet_type = self._read_buf._current_packet.packet_type
        self._break_in_progress = False


cdef class BaseAsyncProtocol(BaseProtocol):

    def __init__(self):
        BaseProtocol.__init__(self)
        self._request_lock = asyncio.Lock()
        self._transport._is_async = True

    async def _close(self, AsyncThinConnImpl conn_impl):
        """
        Closes the connection. If a transaction is in progress it will be
        rolled back. DRCP sessions will be released. For standalone
        connections, the session will be logged off. For pooled connections,
        the connection will be returned to the pool for subsequent use.
        """
        cdef:
            uint32_t release_mode = DRCP_DEAUTHENTICATE \
                    if conn_impl._pool is None else 0
            AsyncThinPoolImpl pool_impl
            Message message

        async with self._request_lock:

            # if a read failed on the socket earlier, clear the socket
            if self._read_buf._transport is None:
                self._transport = None

            # if the session was marked as needing to be closed, force it
            # closed immediately (unless it was already closed)
            if self._read_buf._session_needs_to_be_closed \
                    and self._transport is not None:
                self._force_close()

            # rollback any open transaction and release the DRCP session, if
            # applicable
            if self._transport is not None:
                if self._txn_in_progress:
                    message = conn_impl._create_message(RollbackMessage)
                    await self._process_message(message)
                if conn_impl._drcp_enabled:
                    self._release_drcp_session(conn_impl, release_mode)
                    conn_impl._drcp_establish_session = True

            # if the connection is part of a pool, return it to the pool
            if conn_impl._pool is not None:
                pool_impl = <AsyncThinPoolImpl> conn_impl._pool
                return await pool_impl._return_connection(conn_impl)

            # otherwise, destroy the database object type cache, send the
            # logoff message and final close packet
            if conn_impl._dbobject_type_cache_num > 0:
                remove_dbobject_type_cache(conn_impl._dbobject_type_cache_num)
                conn_impl._dbobject_type_cache_num = 0
            if self._transport is not None:
                if not conn_impl._drcp_enabled:
                    message = conn_impl._create_message(LogoffMessage)
                    await self._process_message(message)
                self._final_close(self._write_buf)

    async def _connect_phase_one(self,
                                 AsyncThinConnImpl conn_impl,
                                 ConnectParamsImpl params,
                                 Description description,
                                 Address address,
                                 str connect_string):
        """
        Method for performing the required steps for establishing a connection
        within the scope of a retry. If the listener refuses the connection, a
        retry will be performed, if retry_count is set.
        """
        cdef:
            ConnectMessage connect_message = None
            uint8_t packet_type, packet_flags = 0
            object ssl_context, connect_info
            ConnectParamsImpl temp_params
            str host, redirect_data
            object orig_transport
            Address temp_address
            int port, pos

        # asyncio doesn't support OOB processing
        self._caps.supports_oob = False

        # establish initial TCP connection and get initial connect string
        host = address.host
        port = address.port
        orig_transport = await self._connect_tcp(params, description, address,
                                                 host, port)

        # send connect message and process response; this may request the
        # message to be resent multiple times; if a redirect packet is
        # detected, a new TCP connection is established first
        while True:

            # create connection message, if needed
            if connect_message is None:
                connect_message = conn_impl._create_message(ConnectMessage)
                connect_message.host = host
                connect_message.port = port
                connect_message.description = description
                connect_message.connect_string_bytes = connect_string.encode()
                connect_message.connect_string_len = \
                        <uint16_t> len(connect_message.connect_string_bytes)
                connect_message.packet_flags = packet_flags

            # process connection message
            await self._process_message(connect_message)
            packet_type = self._read_buf._current_packet.packet_type
            if connect_message.redirect_data is not None:
                redirect_data = connect_message.redirect_data
                pos = redirect_data.find('\x00')
                if pos < 0:
                    errors._raise_err(errors.ERR_INVALID_REDIRECT_DATA,
                                      data=redirect_data)
                temp_params = ConnectParamsImpl()
                temp_params._parse_connect_string(redirect_data[:pos])
                temp_address = temp_params._get_addresses()[0]
                host = temp_address.host
                port = temp_address.port
                connect_string = redirect_data[pos + 1:]
                orig_transport = await self._connect_tcp(params, description,
                                                         address, host, port)
                connect_message = None
                packet_flags = TNS_PACKET_FLAG_REDIRECT
            elif packet_type == TNS_PACKET_TYPE_ACCEPT:
                return connect_message.cookie

            # for TCPS connections, OOB processing is not supported; if the
            # packet flags indicate that TLS renegotiation is required, this is
            # performed now
            if address.protocol == "tcps":
                self._caps.supports_oob = False
                packet_flags = self._read_buf._current_packet.packet_flags
                if packet_flags & TNS_PACKET_FLAG_TLS_RENEG:
                    self._transport._transport = orig_transport
                    await self._transport.negotiate_tls_async(self,
                                                              description)

    async def _connect_phase_two(self, AsyncThinConnImpl conn_impl,
                                 ConnectionCookie cookie,
                                 Description description,
                                 ConnectParamsImpl params):
        """"
        Method for perfoming the required steps for establishing a connection
        oustide the scope of a retry. If any of the steps in this method fail,
        an exception will be raised.
        """
        cdef:
            ConnectionCookieMessage cookie_message
            DataTypesMessage data_types_message
            ProtocolMessage protocol_message
            AuthMessage auth_message
            bint sent_cookie = False

        # check if the protocol version supported by the database is high
        # enough; if not, reject the connection immediately
        if self._caps.protocol_version < TNS_VERSION_MIN_ACCEPTED:
            errors._raise_err(errors.ERR_SERVER_VERSION_NOT_SUPPORTED)

        # create the messages that need to be sent to the server
        protocol_message = conn_impl._create_message(ProtocolMessage)
        data_types_message = conn_impl._create_message(DataTypesMessage)
        auth_message = conn_impl._create_message(AuthMessage)
        auth_message._set_params(params, description)

        # starting in 23c, a cookie can be sent along with the protocol, data
        # types and authorization messages without waiting for the server to
        # respond to each of the messages in turn
        if cookie is not None and cookie.populated:
            cookie_message = conn_impl._create_message(ConnectionCookieMessage)
            cookie_message.cookie = cookie
            cookie_message.protocol_message = protocol_message
            cookie_message.data_types_message = data_types_message
            cookie_message.auth_message = auth_message
            await self._process_message(cookie_message)
            sent_cookie = True
        else:
            await self._process_message(protocol_message)

        # if database is not 23c or later, or renegotiation has been requested,
        # use the regular approach for the remaining messages
        if not sent_cookie or not cookie.populated:
            await self._process_message(data_types_message)
            await self._process_message(auth_message)
            if cookie is not None and not cookie.populated:
                cookie.protocol_version = protocol_message.server_version
                cookie.server_banner = protocol_message.server_banner
                cookie.charset_id = self._caps.charset_id
                cookie.ncharset_id = self._caps.ncharset_id
                cookie.flags = protocol_message.server_flags
                cookie.compile_caps = protocol_message.server_compile_caps
                cookie.runtime_caps = protocol_message.server_runtime_caps
                cookie.populated = True

        # send authorization message a second time, if needed, to respond to
        # the challenge sent by the server
        if auth_message.resend:
            await self._process_message(auth_message)

        # mark protocol to indicate that connect is no longer in progress; this
        # allows the normal break/reset mechanism to fire
        conn_impl.warning = auth_message.warning
        self._in_connect = False

    async def _connect_tcp(self, ConnectParamsImpl params,
                           Description description, Address address, str host,
                           int port):
        """
        Creates a socket on which to communicate using the provided parameters.
        If a proxy is configured, a connection to the proxy is established and
        the target host and port is forwarded to the proxy.
        """
        cdef:
            bint use_proxy = (address.https_proxy is not None)
            double timeout = description.tcp_connect_timeout
            bint use_tcps = (address.protocol == "tcps")
            object connect_info, data, reply, m
            str connect_host
            int connect_port

        # establish connection to appropriate host/port
        if use_proxy:
            if not use_tcps:
                errors._raise_err(errors.ERR_HTTPS_PROXY_REQUIRES_TCPS)
            connect_host = address.https_proxy
            connect_port = address.https_proxy_port
        else:
            connect_host = host
            connect_port = port
            if not use_tcps and (params._token is not None
                    or params.access_token_callback is not None):
                errors._raise_err(errors.ERR_ACCESS_TOKEN_REQUIRES_TCPS)
        transport, protocol = await self._read_buf._loop.create_connection(
            lambda: self,
            connect_host,
            connect_port
        )

        # complete connection through proxy, if applicable
        if use_proxy:
            data = f"CONNECT {host}:{port} HTTP/1.0\r\n\r\n"
            transport.write(data.encode())
            reply = transport.read(1024)
            m = re.search('HTTP/1.[01]\\s+(\\d+)\\s+', reply.decode())
            if m is None or m.groups()[0] != '200':
                errors._raise_err(errors.ERR_PROXY_FAILURE,
                                  response=reply.decode())

        # set socket on transport
        self._transport.set_from_socket(transport, params, description,
                                        address)

        # negotiate TLS, if applicable
        if use_tcps:
            self._transport.create_ssl_context(params, description, address)
            return await self._transport.negotiate_tls_async(self, description)

    async def _process_message(self, Message message):
        """
        Sends a message to the server and processes its response.
        """
        cdef:
            uint32_t timeout = message.conn_impl._call_timeout
            object timeout_obj = (timeout / 1000) or None
        try:
            coroutine = self._process_message_helper(message)
            await asyncio.wait_for(coroutine, timeout_obj)
        except asyncio.TimeoutError:
            try:
                coroutine = self._process_timeout_helper(message, timeout)
                await asyncio.wait_for(coroutine, timeout_obj)
            except asyncio.TimeoutError:
                self._force_close()
                errors._raise_err(errors.ERR_CONNECTION_CLOSED,
                                  "socket timed out while recovering from " \
                                  "previous socket timeout")
            raise
        except:
            if not self._in_connect \
                    and self._write_buf._packet_sent \
                    and self._read_buf._transport is not None:
                self._send_marker(self._write_buf, TNS_MARKER_TYPE_BREAK)
                await self._reset()
            raise
        if message.flush_out_binds:
            self._write_buf.start_request(TNS_PACKET_TYPE_DATA)
            self._write_buf.write_uint8(TNS_MSG_TYPE_FLUSH_OUT_BINDS)
            self._write_buf.end_request()
            await self._reset()
            message.process(self._read_buf)
        if self._break_in_progress:
            try:
                coroutine = self._receive_packet(message)
                await asyncio.wait_for(coroutine, timeout_obj)
            except asyncio.TimeoutError:
                self._force_close()
                errors._raise_err(errors.ERR_CONNECTION_CLOSED,
                                  "socket timed out while awaiting break " \
                                  "response from server")
            message.process(self._read_buf)
            self._break_in_progress = False
        self._txn_in_progress = message.call_status & TNS_TXN_IN_PROGRESS
        if message.error_occurred:
            if message.retry:
                message.error_occurred = False
                return await self._process_message(message)
            error = errors._Error(message.error_info.message,
                                  code=message.error_info.num,
                                  offset=message.error_info.pos)

            # if a connection has received dead connection error then it is no
            # longer usable
            if error.is_session_dead:
                self._force_close()
            exc_type = get_exception_class(message.error_info.num)
            raise exc_type(error)

    async def _process_message_helper(self, Message message):
        """
        Helper routine that is called to process a message within a timeout.
        """
        self._read_buf.reset_packets()
        message.send(self._write_buf)
        await self._receive_packet(message)
        while True:
            try:
                message.process(self._read_buf)
                break
            except OutOfPackets:
                await self._receive_packet(message)
                self._read_buf.restore_point()

    async def _process_single_message(self, Message message):
        """
        Process a single message within a request.
        """
        async with self._request_lock:
            await self._process_message(message)
            if message.resend:
                await self._process_message(message)
        await message.postprocess_async()

    async def _process_timeout_helper(self, Message message, uint32_t timeout):
        """
        Helper routine that is called to process a timeout.
        """
        self._break_external()
        await self._receive_packet(message)
        self._break_in_progress = False
        errors._raise_err(errors.ERR_CALL_TIMEOUT_EXCEEDED, timeout=timeout)

    async def _receive_packet(self, Message message):
        cdef:
            ReadBuffer buf = self._read_buf
            uint16_t refuse_message_len
            const char_type* ptr
        await buf.wait_for_packets_async()
        if buf._current_packet.packet_type == TNS_PACKET_TYPE_MARKER:
            await self._reset()
        elif buf._current_packet.packet_type == TNS_PACKET_TYPE_REFUSE:
            self._write_buf._packet_sent = False
            buf.skip_raw_bytes(2)
            buf.read_uint16(&refuse_message_len)
            if refuse_message_len == 0:
                message.error_info.message = None
            else:
                ptr = buf.read_raw_bytes(refuse_message_len)
                message.error_info.message = ptr[:refuse_message_len].decode()

    async def _reset(self):
        cdef uint8_t marker_type, packet_type

        # send reset marker
        self._send_marker(self._write_buf, TNS_MARKER_TYPE_RESET)

        # read and discard all packets until a marker packet is received
        while True:
            packet_type = self._read_buf._current_packet.packet_type
            if packet_type == TNS_PACKET_TYPE_MARKER:
                self._read_buf.skip_raw_bytes(2)
                self._read_buf.read_ub1(&marker_type)
                if marker_type == TNS_MARKER_TYPE_RESET:
                    break
            await self._read_buf.wait_for_packets_async()

        # read error packet; first skip as many marker packets as may be sent
        # by the server; if the server doesn't handle out-of-band breaks
        # properly, some quit immediately and others send multiple reset
        # markers (this addresses both situations without resulting in strange
        # errors)
        while packet_type == TNS_PACKET_TYPE_MARKER:
            await self._read_buf.wait_for_packets_async()
            packet_type = self._read_buf._current_packet.packet_type
        self._break_in_progress = False

    def connection_lost(self, exc):
        """
        Called when a connection has been lost. The presence of an exception
        indicates an abornmal loss of the connection.
        """
        self._transport = None

    def data_received(self, data):
        """
        Called when data has been received on the transport.
        """
        cdef:
            bint notify_waiter = False
            Packet packet
        packet = self._transport.extract_packet(data)
        while packet is not None:
            self._read_buf._process_packet(packet, &notify_waiter)
            if notify_waiter:
                self._read_buf.notify_packet_received()
            packet = self._transport.extract_packet()


class AsyncProtocol(BaseAsyncProtocol, asyncio.Protocol):
    pass
