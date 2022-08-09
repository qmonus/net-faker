import logging
import typing
import json
import re

from aiohttp import web

from . import exceptions
from ..libs import http_client, validator, xml_utils
from ..application import (
    exceptions as app_exceptions,
    manager_application,
    plugin,
)
from ..domain import stub_domain, yang_tree_domain

logger = logging.getLogger(__name__)

STATUS_WAITING = "WAITING"
STATUS_RUNNING = "RUNNING"
STATUS_STOPPING = "STOPPING"
STATUS_STOPPED = "STOPPED"


class Server(object):
    def __init__(
        self,
        host: str,
        port: int,
        manager_app: manager_application.App,
    ) -> None:
        self._host = host
        self._port = port
        self._manager_app = manager_app
        self._runner: typing.Optional[web.AppRunner] = None
        self._status = STATUS_WAITING

        def _filename(v: typing.Any) -> bool:
            m = re.match(r"\A(?![.]+\Z)[a-zA-Z0-9\-_@.]+\Z", v)
            if m:
                return True
            else:
                return False

        def _filepath(v: typing.Any) -> bool:
            m = re.match(r"\A(/(?![.]+(\Z|/))[a-zA-Z0-9\-_@.]+)+\Z", v)
            if m:
                return True
            else:
                return False

        _validator = validator.Validator()
        _validator.add_format(name="filename", func=_filename)
        _validator.add_format(name="filepath", func=_filepath)
        self._validator = _validator

    async def _handle_echo(self, request: web.Request) -> web.Response:
        response = web.json_response(
            status=200,
            data={
                "echo": {
                    "method": request.method,
                    "path": request.path,
                    "query": http_client.to_query_dict(request.query_string),
                    "headers": dict(request.headers),
                    "body": await request.text(),
                }
            },
        )
        return response

    async def _create_stub(self, request: web.Request) -> web.Response:
        # Validate request format
        req_body = self._load_json(await request.text())
        self._validator.validate(
            value=req_body,
            schema={
                "type": "object",
                "required": ["stub"],
                "properties": {
                    "stub": {
                        "type": "object",
                        "required": [
                            "id",
                            "handler",
                        ],
                        "properties": {
                            "id": {"type": "string"},
                            "description": {"type": "string"},
                            "handler": {"type": "string"},
                            "yang": {"type": "string"},
                            "enabled": {"type": "boolean"},
                            "metadata": {"type": "object"},
                        },
                    }
                },
            },
        )

        # Setup variables
        req_stub = req_body["stub"]

        stub = await self._manager_app.create_stub(
            id=req_stub["id"],
            description=req_stub.get("description", ""),
            handler=req_stub["handler"],
            yang=req_stub.get("yang", ""),
            enabled=req_stub.get("enabled", True),
            metadata=req_stub.get("metadata", {}),
        )

        # Response
        response = web.json_response(
            status=200,
            data={"stub": await StubView.get(stub=stub)},
        )
        return response

    async def _list_stubs(self, request: web.Request) -> web.Response:
        # Validate request format
        query = http_client.to_query_dict(request.query_string)
        self._validator.validate(
            value=query,
            schema={
                "type": "object",
                "properties": {"id": {"type": "array", "items": {"type": "string"}}},
            },
        )

        # List
        stubs = await self._manager_app.list_stubs(
            id=query.get("id"),
        )

        # Response
        response = web.json_response(
            status=200,
            data={"stubs": await StubView.list(stubs=stubs)},
        )
        return response

    async def _get_stub(self, request: web.Request) -> web.Response:
        # Validate request format
        id = request.match_info["id"]

        # Get
        stub = await self._manager_app.get_stub(id=id)

        # Response
        response = web.json_response(
            data={"stub": await StubView.get(stub=stub)},
            status=200,
        )
        return response

    async def _get_stub_property(self, request: web.Request) -> web.Response:
        # Validate request format
        id = request.match_info["id"]
        property = request.match_info["property"]

        # Get
        stub = await self._manager_app.get_stub(id=id)
        stub_dict = await StubView.get(stub=stub)
        if property not in stub_dict:
            raise exceptions.NotFoundError(f"Not Found")
        stub_property = stub_dict[property]

        # Response
        if property in ["candidateConfig", "runningConfig", "startupConfig"]:
            response = web.Response(
                status=200,
                headers={"content-type": "application/xml"},
                text=stub_property,
            )
        elif property in ["metadata"]:
            response = web.json_response(status=200, body=stub_property)
        else:
            response = web.Response(status=200, text=str(stub_property))
        return response

    async def _update_stub(self, request: web.Request) -> web.Response:
        # Validate request format
        id = request.match_info["id"]
        req_body = self._load_json(await request.text())
        self._validator.validate(
            value=req_body,
            schema={
                "type": "object",
                "required": ["stub"],
                "properties": {
                    "stub": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "handler": {"type": "string"},
                            "yang": {"type": "string"},
                            "enabled": {"type": "boolean"},
                            "metadata": {"type": "object"},
                        },
                    }
                },
            },
        )
        req_stub = req_body["stub"]

        # Update
        stub = await self._manager_app.update_stub(
            id=id,
            description=req_stub.get("description"),
            handler=req_stub.get("handler"),
            yang=req_stub.get("yang"),
            enabled=req_stub.get("enabled"),
            metadata=req_stub.get("metadata"),
        )

        # Response
        response = web.json_response(
            data={"stub": await StubView.get(stub=stub)},
            status=200,
        )
        return response

    async def _delete_stub(self, request: web.Request) -> web.Response:
        # Validate request format
        id = request.match_info["id"]

        # Delete
        await self._manager_app.delete_stub(id=id)

        # Response
        response = web.Response(status=204)
        return response

    async def _reload_stubs(self, request: web.Request) -> web.Response:
        # Reset
        stubs = await self._manager_app.reload_stubs()

        # Response
        response = web.json_response(
            status=200,
            data={"stubs": await StubView.list(stubs=stubs)},
        )
        return response

    async def _reset_stubs(self, request: web.Request) -> web.Response:
        logger.warning(
            f"The 'stubs:reset' method is deprecated, use 'stubs:reload' instead"
        )
        return await self._reload_stubs(request=request)

    async def _list_yangs(self, request: web.Request) -> web.Response:
        query = http_client.to_query_dict(request.query_string)
        self._validator.validate(
            value=query,
            schema={
                "type": "object",
                "properties": {"id": {"type": "array", "items": {"type": "string"}}},
            },
        )

        # List
        yangs = await self._manager_app.list_yangs(
            id=query.get("id"),
        )

        # Response
        response = web.json_response(
            status=200,
            data={"yangs": await YangView.list(yangs=yangs)},
        )
        return response

    async def _get_yang(self, request: web.Request) -> web.Response:
        # Validate request format
        id = request.match_info["id"]
        self._validator.validate(
            value=id, schema={"type": "string", "format": "filename"}
        )

        # Get
        yang = await self._manager_app.get_yang(id=id)

        # Response
        response = web.json_response(
            status=200,
            data={"yang": await YangView.get(yang=yang)},
        )
        return response

    async def _handle_network_operation(self, request: web.Request) -> web.Response:
        # TODO: Validate request format
        id = request.match_info["id"]

        _request = plugin.Request(
            scheme=request.scheme,
            method=request.method,
            url=str(request.url),
            path=request.path,
            query=http_client.to_query_dict(request.query_string),
            headers=request.headers,
            body=await request.text(),
            stub_id=id,
        )

        # Handle
        _response = await self._manager_app.handle_network_operation(_request)

        # Response
        response = web.Response(
            body=_response.body,
            headers=_response.headers,
            status=_response.code,
        )
        return response

    async def _on_startup(self, app: typing.Any) -> None:
        logger.info("startup")

    async def _on_shutdown(self, app: typing.Any) -> None:
        logger.info("shutdown")

    async def _on_cleanup(self, app: typing.Any) -> None:
        logger.info("cleanup")

    def _load_json(self, data: str) -> typing.Any:
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as e:
            raise exceptions.ValidationError("Invalid json format")
        return obj

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
    async def _handle_error(
        self, request: web.Request, handler: typing.Any
    ) -> web.Response:
        try:
            logger.info(f"Received: {request.method} {request.path}")
            response: web.Response = await handler(request)
            logger.info(
                f"Responded: {response.status} (Request: {request.method} {request.path})"
            )
            return response
        except exceptions.ValidationError as e:
            logger.info(f"Responded: 400 (Request: {request.method} {request.path})")
            raise web.HTTPBadRequest(
                text=self._create_error_message(code=400, e=e),
                content_type="application/json",
            )
        except exceptions.NotFoundError as e:
            logger.info(f"Responded: 404 (Request: {request.method} {request.path})")
            raise web.HTTPNotFound(
                text=self._create_error_message(code=404, e=e),
                content_type="application/json",
            )
        except validator.ValidationError as e:
            logger.info(f"Responded: 400 (Request: {request.method} {request.path})")
            raise web.HTTPBadRequest(
                text=self._create_error_message(code=400, e=e),
                content_type="application/json",
            )
        except app_exceptions.RelatedResourceNotFoundError as e:
            logger.info(f"Responded: 400 (Request: {request.method} {request.path})")
            raise web.HTTPBadRequest(
                text=self._create_error_message(code=400, e=e),
                content_type="application/json",
            )
        except app_exceptions.ForbiddenError as e:
            logger.info(f"Responded: 403 (Request: {request.method} {request.path})")
            raise web.HTTPForbidden(
                text=self._create_error_message(code=403, e=e),
                content_type="application/json",
            )
        except app_exceptions.NotFoundError as e:
            logger.info(f"Responded: 404 (Request: {request.method} {request.path})")
            raise web.HTTPNotFound(
                text=self._create_error_message(code=404, e=e),
                content_type="application/json",
            )
        except app_exceptions.ConflictError as e:
            logger.info(f"Responded: 409 (Request: {request.method} {request.path})")
            raise web.HTTPConflict(
                text=self._create_error_message(code=409, e=e),
                content_type="application/json",
            )
        except web.HTTPException as e:
            logger.info(
                f"Responded: {e.status_code} (Request: {request.method} {request.path})"
            )
            e.text = self._create_error_message(code=e.status_code, e=e)
            e.content_type = "application/json"
            raise e
        except Exception as e:
            logger.info(f"Responded: 500 (Request: {request.method} {request.path})")
            logger.exception("ScriptError: ")
            raise web.HTTPInternalServerError(
                text=self._create_error_message(code=500, e=e),
                content_type="application/json",
            )

    async def start(self) -> None:
        aiohttp_app = web.Application(
            client_max_size=10 * 1024 * 1024,
            middlewares=[self._handle_error],
        )
        aiohttp_app.add_routes(
            [
                # echo
                web.route(method="*", path="/echo", handler=self._handle_echo),
                # stubs
                web.post(path="/stubs", handler=self._create_stub),
                web.get(path="/stubs", handler=self._list_stubs),
                web.get(path="/stubs/{id}", handler=self._get_stub),
                web.get(path="/stubs/{id}/{property}", handler=self._get_stub_property),
                web.patch(path="/stubs/{id}", handler=self._update_stub),
                web.delete(path="/stubs/{id}", handler=self._delete_stub),
                web.post(path="/stubs:reload", handler=self._reload_stubs),
                web.post(path="/stubs:reset", handler=self._reset_stubs),
                web.post(
                    path="/stubs/{id}:handle", handler=self._handle_network_operation
                ),
                # yangs
                web.get(path="/yangs", handler=self._list_yangs),
                web.get(path="/yangs/{id}", handler=self._get_yang),
            ]
        )

        aiohttp_app.on_startup.append(self._on_startup)
        aiohttp_app.on_shutdown.append(self._on_shutdown)
        aiohttp_app.on_cleanup.append(self._on_cleanup)

        # Start http server
        runner = web.AppRunner(aiohttp_app, handle_signals=False)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        self._runner = runner
        self._status = STATUS_RUNNING
        logger.info(f"Manager is running on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._runner is not None:
            self._status = STATUS_STOPPING
            await self._runner.cleanup()
            self._status = STATUS_STOPPED
            self._runner = None
            logger.info(f"Stopped.")


class StubView(object):
    @classmethod
    async def get(cls, stub: stub_domain.Entity) -> dict[typing.Any, typing.Any]:
        stub_dicts = await cls.list(stubs=[stub])
        return stub_dicts[0]

    @classmethod
    async def list(
        cls, stubs: typing.List[stub_domain.Entity]
    ) -> list[dict[typing.Any, typing.Any]]:
        stubs_dict: list[dict[typing.Any, typing.Any]] = []
        for stub in stubs:
            stub_dict = {
                "id": stub.id.value,
                "description": stub.description.value,
                "handler": stub.handler.value,
                "yang": stub.yang.value,
                "enabled": stub.enabled.value,
                "candidateConfig": xml_utils.to_string(
                    stub.get_candidate_config(),
                    pretty_print=True,
                ),
                "runningConfig": xml_utils.to_string(
                    stub.get_running_config(),
                    pretty_print=True,
                ),
                "startupConfig": xml_utils.to_string(
                    stub.get_startup_config(),
                    pretty_print=True,
                ),
                "metadata": stub.get_metadata(),
            }
            stubs_dict.append(stub_dict)
        return stubs_dict


class YangView(object):
    @classmethod
    async def get(cls, yang: yang_tree_domain.Entity) -> dict[typing.Any, typing.Any]:
        yang_dicts = await cls.list(yangs=[yang])
        return yang_dicts[0]

    @classmethod
    async def list(
        cls, yangs: typing.List[yang_tree_domain.Entity]
    ) -> list[dict[typing.Any, typing.Any]]:
        yang_dicts: list[dict[typing.Any, typing.Any]] = []
        for yang in yangs:
            yang_dict = {
                "id": yang.id.value,
            }
            yang_dicts.append(yang_dict)
        return yang_dicts
