import logging
import typing
import json

import snmp_agent

from . import exceptions
from ..libs import http_client

logger = logging.getLogger(__name__)


class Handler(object):
    def __init__(self, stub_id: str, manager_endpoint: str):
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint.rstrip("/")

    async def handle(self, request: snmp_agent.SNMPRequest) -> snmp_agent.SNMPResponse:
        pdu_type: typing.Literal["GET", "GET_NEXT", "GET_BULK"]
        if isinstance(request.context, snmp_agent.snmp.SnmpGetContext):
            pdu_type = "GET"
        elif isinstance(request.context, snmp_agent.snmp.SnmpGetNextContext):
            pdu_type = "GET_NEXT"
        elif isinstance(request.context, snmp_agent.snmp.SnmpGetBulkContext):
            pdu_type = "GET_BULK"
        else:
            raise exceptions.FatalError(f"Invalid snmp context")

        objects = [
            {"oid": vb.oid, "value": None, "type": None}
            for vb in request.variable_bindings
        ]

        version: typing.Literal["v1", "v2c"]
        if request.version == snmp_agent.snmp.VERSION.V1:
            version = "v1"
        elif request.version == snmp_agent.snmp.VERSION.V2C:
            version = "v2c"
        else:
            raise exceptions.FatalError(
                f"Invalid snmp version '{request.version.name}'"
            )

        r = await self._send_to_manager(
            pdu_type=pdu_type,
            version=version,
            request_id=request.request_id,
            community=request.community,
            non_repeaters=request.non_repeaters,
            max_repetitions=request.max_repetitions,
            objects=objects,
        )
        if r.code != 200:
            raise exceptions.Error(f"Failed to get oids: {r.code} {r.body}")

        objects = json.loads(r.body)["objects"]

        vbs = []
        for o in objects:
            oid = o["oid"]
            type = o["type"]
            value = o["value"]

            if type == "OCTET_STRING":
                snmp_value = snmp_agent.OctetString(value)
            elif type == "INTEGER":
                snmp_value = snmp_agent.Integer(value)
            elif type == "COUNTER32":
                snmp_value = snmp_agent.Counter32(value)
            elif type == "COUNTER64":
                snmp_value = snmp_agent.Counter64(value)
            elif type == "GAUGE32":
                snmp_value = snmp_agent.Gauge32(value)
            elif type == "TIMETICKS":
                snmp_value = snmp_agent.TimeTicks(value)
            elif type == "OBJECT_IDENTIFIER":
                snmp_value = snmp_agent.ObjectIdentifier(value)
            elif type == "NULL":
                snmp_value = snmp_agent.Null()
            elif type == "IP_ADDRESS":
                snmp_value = snmp_agent.IPAddress(value)
            elif type == "NO_SUCH_OBJECT":
                snmp_value = snmp_agent.NoSuchObject()
            elif type == "NO_SUCH_INSTANCE":
                snmp_value = snmp_agent.NoSuchInstance()
            elif type == "END_OF_MIB_VIEW":
                snmp_value = snmp_agent.EndOfMibView()
            else:
                raise exceptions.FatalError(f"Invalid type '{type}'")

            vbs.append(snmp_agent.VariableBinding(oid=oid, value=snmp_value))

        response = request.create_response(variable_bindings=vbs)
        return response

    async def _send_to_manager(
        self,
        pdu_type: typing.Literal["GET", "GET_NEXT", "GET_BULK"],
        version: typing.Literal["v1", "v2c"],
        request_id: int,
        community: str,
        non_repeaters: int,
        max_repetitions: int,
        objects: list[dict[str, typing.Any]],
    ) -> http_client.ResponseData:
        url = f"{self._manager_endpoint}/stubs/{self._stub_id}:handle"
        body = {
            "id": self._stub_id,
            "protocol": "snmp",
            "pduType": pdu_type,
            "version": version,
            "requestId": request_id,
            "community": community,
            "non_repeaters": non_repeaters,
            "max_repetitions": max_repetitions,
            "objects": objects,
        }
        async with http_client.Session() as sess:
            response = await sess.request(
                method="POST",
                url=url,
                body=json.dumps(body),
            )
        return response


class Server(object):
    def __init__(
        self,
        host: str,
        port: int,
        stub_id: str,
        manager_endpoint: str,
    ):
        if None in [host, port, stub_id, manager_endpoint]:
            raise ValueError("host, port, stub_id, and manager_endpoint must be set")

        self._host = host
        self._port = port
        self._stub_id = stub_id
        self._manager_endpoint = manager_endpoint
        self._server: typing.Optional[snmp_agent.Server] = None

    async def start(self) -> None:
        handler = Handler(
            stub_id=self._stub_id, manager_endpoint=self._manager_endpoint
        )

        server = snmp_agent.Server(
            handler=handler.handle, host=self._host, port=self._port
        )
        await server.start()
        self._server = server

        logger.info(f"SNMP server is running on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.stop()
            self._server = None
            logger.info(f"Stopped.")
