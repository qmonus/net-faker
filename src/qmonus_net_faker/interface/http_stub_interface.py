import typing
import json
import pathlib
import asyncio
import ssl
import logging

from aiohttp import web

from . import exceptions
from ..libs import http_client

logger = logging.getLogger(__name__)


class Server(object):
    def __init__(
        self, host: str, port: int, stub_id: str, manager_endpoint: str, ssl: bool,
    ) -> None:
        if None in [host, port, stub_id, manager_endpoint]:
            raise ValueError("host, port, stub_id, and manager_endpoint must be set")

        self._host = host
        self._port = port
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint.rstrip("/")
        self._ssl = ssl
        self._runner: typing.Optional[web.AppRunner] = None

    async def _aiohttp_handler(self, aiohttp_request: web.Request) -> web.Response:
        url = f"{self._manager_endpoint}/stubs/{self._stub_id}:handle"
        body = {
            "id": self._stub_id,
            "protocol": "https" if self._ssl else "http",
            "method": aiohttp_request.method,
            "path": aiohttp_request.path,
            "query": http_client.to_query_dict(aiohttp_request.query_string),
            "headers": dict(aiohttp_request.headers),
            "body": await aiohttp_request.text(),
        }

        async with http_client.Session() as sess:
            response = await sess.request(
                method="POST",
                url=url,
                body=json.dumps(body),
            )
        if response.code != 200:
            raise exceptions.Error(f"Failed: {response.code} {response.body}")

        res_body = json.loads(response.body)

        aiohttp_response = web.Response(
            status=res_body["code"],
            headers=res_body["headers"],
            body=res_body["body"],
        )
        return aiohttp_response

    def _create_error_message(self, code: int, e: Exception) -> str:
        message = json.dumps(
            {
                "errorCode": code,
                "errorMessage": f"{e.__class__.__name__}: {str(e)}",
                "moreInfo": None,
            }
        )
        return message

    @web.middleware
    async def _middleware(
        self, request: web.Request, handler: typing.Any
    ) -> web.Response:
        try:
            logger.info(f"Received: {request.method} {request.path}")
            response: web.Response = await handler(request)
            logger.info(
                f"Responded: {response.status} (Request: {request.method} {request.path})"
            )
            return response
        except Exception as e:
            logger.info(f"Responded: 500 (Request: {request.method} {request.path})")
            logger.exception("ScriptError: ")
            raise web.HTTPInternalServerError(
                text=self._create_error_message(code=500, e=e),
                content_type="application/json",
            )

    async def _on_startup(self, app: typing.Any) -> None:
        pass

    async def _on_shutdown(self, app: typing.Any) -> None:
        pass

    async def _on_cleanup(self, app: typing.Any) -> None:
        pass

    async def start(self) -> None:
        aiohttp_app = web.Application(
            client_max_size=10 * 1024 * 1024,
            middlewares=[self._middleware],
        )

        aiohttp_app.add_routes(
            [
                web.route(method="*", path="/{path:.*}", handler=self._aiohttp_handler),
            ]
        )

        aiohttp_app.on_startup.append(self._on_startup)
        aiohttp_app.on_shutdown.append(self._on_shutdown)
        aiohttp_app.on_cleanup.append(self._on_cleanup)

        # Start http server
        if self._ssl:
            current_dir = pathlib.Path(__file__).parent.resolve()
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                str(current_dir.joinpath("server.crt")),
                str(current_dir.joinpath("server.key")),
            )
        else:
            ssl_context = None

        runner = web.AppRunner(aiohttp_app, handle_signals=False)
        await runner.setup()
        site = web.TCPSite(
            runner=runner, host=self._host, port=self._port, ssl_context=ssl_context
        )
        await site.start()
        self._runner = runner

        if self._ssl:
            logger.info(f"HTTPS server is running on {self._host}:{self._port}")
        else:
            logger.info(f"HTTP server is running on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            logger.info(f"Stopped.")
