import typing
import logging
import json

import telnetlib3

from . import exceptions
from ..libs import str_utils, http_client

logger = logging.getLogger(__name__)


class Handler(object):
    def __init__(self, stub_id: str, manager_endpoint: str):
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint.rstrip("/")
        self._session_count = 0

    async def handle(self, reader: typing.Any, writer: typing.Any) -> None:
        try:
            await self._handle(reader=reader, writer=writer)
        except Exception as e:
            logger.exception(e)
            await self._write(writer=writer, string=str(e))

        writer.close()

    async def _handle(self, reader: typing.Any, writer: typing.Any) -> None:
        self._session_count += 1
        session_id = self._session_count
        prompt = ""
        state: dict[typing.Any, typing.Any] = {}

        logger.debug(f"remote-echo: '{writer.will_echo}'")

        # login message
        response = await self._send_to_manager(
            input="",
            prompt=prompt,
            state=state,
            session_id=session_id,
            connection_status="login",
        )

        if response.code == 200:
            res_body = json.loads(response.body)
            prompt = res_body["prompt"]
            state = res_body["state"]
            sending = f"{res_body['output']}{prompt}"
            await self._write(writer=writer, string=sending)
        else:
            sending = f"{response.code}: {response.body}\n"
            raise exceptions.Error(sending)

        buff = ""
        while True:
            string = await reader.read(1024)
            if not string:
                # EOF
                return

            normalized_string = str_utils.normalize_line_ending(string, to="\r\n")
            # writer.echo(normalized_string)
            writer.write(normalized_string)
            await writer.drain()

            buff += normalized_string
            if "\r\n" not in buff:
                continue

            _temp = buff.split("\r\n")
            buff = _temp[-1]
            lines = _temp[:-1]

            for line in lines:
                logger.debug(line)

                response = await self._send_to_manager(
                    input=line,
                    prompt=prompt,
                    state=state,
                    session_id=session_id,
                    connection_status="established",
                )

                if response.code != 200:
                    sending = f"{response.code}: {response.body}\n"
                    raise exceptions.Error(sending)

                res_body = json.loads(response.body)
                prompt = res_body["prompt"]
                state = res_body["state"]
                sending = f"{res_body['output']}{prompt}"
                await self._write(writer=writer, string=sending)

    async def _write(self, writer: typing.Any, string: typing.Any) -> None:
        normalized_string = str_utils.normalize_line_ending(string=string, to="\r\n")
        writer.write(normalized_string)
        await writer.drain()

    async def _send_to_manager(
        self,
        input: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
        session_id: int,
        connection_status: str,
    ) -> http_client.ResponseData:
        url = f"{self._manager_endpoint}/stubs/{self._stub_id}:handle"
        body = {
            "id": self._stub_id,
            "protocol": "telnet",
            "connectionStatus": connection_status,
            "sessionId": session_id,
            "input": input,
            "prompt": prompt,
            "state": state,
        }

        async with http_client.Session() as sess:
            response = await sess.request(method="POST", url=url, body=json.dumps(body))

        return response


class Server(object):
    def __init__(
        self, host: str, port: int, stub_id: str, manager_endpoint: str
    ) -> None:
        if None in [host, port, stub_id, manager_endpoint]:
            raise ValueError("host, port, stub_id, and manager_endpoint must be set")

        self._host = host
        self._port = port
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint
        self._server: typing.Optional[typing.Any] = None

    async def start(self) -> None:
        handler = Handler(
            stub_id=self._stub_id, manager_endpoint=self._manager_endpoint
        )
        self._server = await telnetlib3.create_server(
            host=self._host,
            port=self._port,
            shell=handler.handle,
            timeout=3600,
        )  # type: ignore
        logger.info(f"Telnet server is running on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info(f"Stopped.")
