import typing
import logging
import json
import pathlib

from asyncssh import misc
from asyncssh import server
from asyncssh import connection
from asyncssh import process

from . import exceptions
from ..libs import xml_utils, http_client

logger = logging.getLogger(__name__)


class SSHServer(server.SSHServer):
    def __init__(self) -> None:
        self.conn: typing.Optional[connection.SSHServerConnection] = None
        self.peer = ""

    def connection_made(self, conn: connection.SSHServerConnection) -> None:
        self.conn = conn
        self.peer = (
            f"{conn.get_extra_info('peername')[0]}:{conn.get_extra_info('peername')[1]}"
        )
        logger.info(f"SSH connection to '{self.peer}' established.")

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        if exc:
            logger.info(f"SSH connection to '{self.peer}' closed: {exc}")
        else:
            logger.info(f"SSH connection to '{self.peer}' closed.")

    def password_auth_supported(self) -> bool:
        return True

    def public_key_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        return True

    def validate_public_key(self, username: str, key: typing.Any) -> bool:
        return True


class Handler(object):
    def __init__(self, stub_id: str, manager_endpoint: str) -> None:
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint.rstrip("/")
        self._session_count = 0

    async def handle(self, process: process.SSHServerProcess[typing.Any]) -> None:
        try:
            if process.subsystem is None:
                await self._handle_ssh(process=process)
            elif process.subsystem == "netconf":
                await self._handle_netconf(process=process)
            else:
                raise exceptions.InputValueError(
                    f"Invalid subsystem '{process.subsystem}'"
                )
        except Exception as e:
            # logger.exception(e)
            logger.info(e)
            process.stdout.write(str(e) + "\n")

        process.exit(0)

    async def _handle_ssh(self, process: process.SSHServerProcess[typing.Any]) -> None:
        self._session_count += 1
        session_id = self._session_count
        username = process.get_extra_info("username")
        prompt = ""
        state: dict[typing.Any, typing.Any] = {}

        # login message
        response = await self._send_ssh_data_to_manager(
            session_id=session_id,
            username=username,
            connection_status="login",
            input="",
            prompt=prompt,
            state=state,
        )
        if response.code == 200:
            res_body = json.loads(response.body)
            prompt = res_body["prompt"]
            state = res_body["state"]
            sending = f"{res_body['output']}{prompt}"
            process.stdout.write(sending)
        else:
            sending = f"{response.code}: {response.body}"
            raise exceptions.Error(sending)

        try:
            async for line in process.stdin:
                line = line.rstrip("\n")
                logger.debug(line)

                response = await self._send_ssh_data_to_manager(
                    session_id=session_id,
                    username=username,
                    connection_status="established",
                    input=line,
                    prompt=prompt,
                    state=state,
                )

                if response.code != 200:
                    sending = f"{response.code}: {response.body}\n"
                    raise exceptions.Error(sending)

                res_body = json.loads(response.body)
                prompt = res_body["prompt"]
                state = res_body["state"]
                sending = f"{res_body['output']}{prompt}"
                process.stdout.write(sending)
        except misc.BreakReceived:
            pass

    async def _handle_netconf(
        self, process: process.SSHServerProcess[typing.Any]
    ) -> None:
        self._session_count += 1
        session_id = self._session_count
        username = process.get_extra_info("username")

        # hello to client
        response = await self._send_netconf_data_to_manager(
            session_id=session_id,
            username=username,
            connection_status="login",
            rpc="",
        )
        if response.code != 200:
            sending = f"{response.code}: {response.body}"
            raise exceptions.Error(sending)

        xml_utils.from_string(response.body)
        sending = response.body + "]]>]]>"
        process.stdout.write(sending)

        # hello from client
        received_with_sep = await process.stdin.readuntil("]]>]]>")
        logger.debug("Received: " + received_with_sep)
        received_str = received_with_sep.replace("]]>]]>", "")
        xml_utils.from_string(received_str)

        while True:
            received_with_sep = await process.stdin.readuntil("]]>]]>")
            logger.debug("Received: " + received_with_sep)

            received_str = received_with_sep.replace("]]>]]>", "")
            received_xml = xml_utils.from_string(received_str)
            message_id = received_xml.attrib["message-id"]

            if received_xml.xpath(
                "./nc:close-session",
                namespaces={"nc": "urn:ietf:params:xml:ns:netconf:base:1.0"},
            ):
                sending = f"""
                <rpc-reply message-id="{message_id}" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
                    <ok/>
                </rpc-reply>]]>]]>
                """

                logger.debug("Sending: " + sending)
                process.stdout.write(sending)
                break
            else:
                response = await self._send_netconf_data_to_manager(
                    session_id=session_id,
                    username=username,
                    connection_status="established",
                    rpc=received_str,
                )

                if response.code == 200:
                    sending = response.body + "]]>]]>"
                    logger.debug("Sending: " + sending)
                    process.stdout.write(sending)
                else:
                    msg = f"Invalid response from manager: {response.code}: {response.body}"
                    logger.error(msg)
                    sending = f"""
                    <rpc-reply message-id="{message_id}" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
                        <rpc-error>
                            <error-type>protocol</error-type>
                            <error-tag>operation-failed</error-tag>
                            <error-severity>error</error-severity>
                            <error-message>{msg}</error-message>
                            <error-info></error-info>
                        </rpc-error>
                    </rpc-reply>]]>]]>
                    """
                    process.stdout.write(sending)

    async def _send_ssh_data_to_manager(
        self,
        session_id: int,
        username: str,
        connection_status: str,
        input: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
    ) -> http_client.ResponseData:
        url = f"{self._manager_endpoint}/stubs/{self._stub_id}:handle"
        body = {
            "id": self._stub_id,
            "protocol": "ssh",
            "connectionStatus": connection_status,
            "sessionId": session_id,
            "username": username,
            "input": input,
            "prompt": prompt,
            "state": state,
        }

        async with http_client.Session() as sess:
            response = await sess.request(method="POST", url=url, body=json.dumps(body))

        return response

    async def _send_netconf_data_to_manager(
        self, session_id: int, username: str, connection_status: str, rpc: str
    ) -> http_client.ResponseData:
        url = f"{self._manager_endpoint}/stubs/{self._stub_id}:handle"
        body = {
            "id": self._stub_id,
            "protocol": "netconf",
            "connectionStatus": connection_status,
            "sessionId": session_id,
            "username": username,
            "rpc": rpc,
        }

        async with http_client.Session() as sess:
            response = await sess.request(method="POST", url=url, body=json.dumps(body))

        return response


class Server(object):
    def __init__(self, host: str, port: int, stub_id: str, manager_endpoint: str):
        if None in [host, port, stub_id, manager_endpoint]:
            raise ValueError("host, port, stub_id, and manager_endpoint must be set")

        self._host = host
        self._port = port
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint
        self._server: typing.Optional[connection.SSHAcceptor] = None

    async def start(self) -> None:
        handler = Handler(
            stub_id=self._stub_id, manager_endpoint=self._manager_endpoint
        )

        def create_ssh_server() -> SSHServer:
            return SSHServer()

        ssh_host_key = pathlib.Path(__file__).with_name("ssh_host_key").resolve()
        self._server = await connection.create_server(
            create_ssh_server,
            self._host,
            self._port,
            server_host_keys=[ssh_host_key],
            process_factory=handler.handle,
        )

        logger.info(f"SSH server is running on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info(f"Stopped.")
