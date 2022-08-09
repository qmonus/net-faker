import logging
import typing

import snmp_agent

from . import stub_domain, exceptions

logger = logging.getLogger(__name__)


class SNMPService(object):
    def __init__(self) -> None:
        pass

    def _objects_to_vbs(
        self, objects: list[dict[str, typing.Any]]
    ) -> list[snmp_agent.VariableBinding]:
        vbs: list[snmp_agent.VariableBinding] = []
        for obj in objects:
            oid = obj["oid"]
            type = obj["type"]
            value = obj["value"]

            if type is None:
                snmp_value = snmp_agent.Null()
            elif type == "OCTET_STRING":
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

        return vbs

    def _vbs_to_objects(
        self, vbs: list[snmp_agent.VariableBinding]
    ) -> list[dict[str, typing.Any]]:
        objects: list[dict[str, typing.Any]] = []
        for vb in vbs:
            oid = vb.oid
            value = vb.value

            if isinstance(value, snmp_agent.OctetString):
                type = "OCTET_STRING"
            elif isinstance(value, snmp_agent.Integer):
                type = "INTEGER"
            elif isinstance(value, snmp_agent.Counter32):
                type = "COUNTER32"
            elif isinstance(value, snmp_agent.Counter64):
                type = "COUNTER64"
            elif isinstance(value, snmp_agent.Gauge32):
                type = "GAUGE32"
            elif isinstance(value, snmp_agent.TimeTicks):
                type = "TIMETICKS"
            elif isinstance(value, snmp_agent.ObjectIdentifier):
                type = "OBJECT_IDENTIFIER"
            elif isinstance(value, snmp_agent.Null):
                type = "NULL"
            elif isinstance(value, snmp_agent.IPAddress):
                type = "IP_ADDRESS"
            elif isinstance(value, snmp_agent.NoSuchObject):
                type = "NO_SUCH_OBJECT"
            elif isinstance(value, snmp_agent.NoSuchInstance):
                type = "NO_SUCH_INSTANCE"
            elif isinstance(value, snmp_agent.EndOfMibView):
                type = "END_OF_MIB_VIEW"
            else:
                raise exceptions.FatalError(f"Invalid value '{value}'")

            objects.append(
                {
                    "oid": oid,
                    "type": type,
                    "value": value.value,
                }
            )

        return objects

    def _get_vbs_from_stub(
        self, stub: stub_domain.Entity
    ) -> list[snmp_agent.VariableBinding]:
        snmp_objects = stub.list_snmp_objects()
        objects = [
            {
                "oid": o.oid,
                "type": o.type,
                "value": o.value,
            }
            for o in snmp_objects.values()
        ]
        vbs = self._objects_to_vbs(objects)
        return vbs

    async def execute(
        self,
        stub: stub_domain.Entity,
        pdu_type: typing.Literal["GET", "GET_NEXT", "GET_BULK"],
        objects: list[dict[str, typing.Any]],
        non_repeaters: int = 0,
        max_repetitions: int = 0,
    ) -> list[dict[str, typing.Any]]:
        if pdu_type == "GET":
            objects = await self.get(
                stub=stub,
                objects=objects,
            )
        elif pdu_type == "GET_NEXT":
            objects = await self.get_next(
                stub=stub,
                objects=objects,
            )
        elif pdu_type == "GET_BULK":
            objects = await self.get_bulk(
                stub=stub,
                objects=objects,
                non_repeaters=non_repeaters,
                max_repetitions=max_repetitions,
            )
        else:
            raise NotImplementedError(f"Invalid pdu_type: '{pdu_type}'")

        return objects

    async def get(
        self,
        stub: stub_domain.Entity,
        objects: list[dict[str, typing.Any]],
    ) -> list[dict[str, typing.Any]]:
        req_vbs = self._objects_to_vbs(objects=objects)
        vbs = self._get_vbs_from_stub(stub=stub)
        res_vbs = snmp_agent.utils.get(req_vbs=req_vbs, vbs=vbs)
        res_objects = self._vbs_to_objects(res_vbs)
        return res_objects

    async def get_next(
        self,
        stub: stub_domain.Entity,
        objects: list[dict[str, typing.Any]],
    ) -> list[dict[str, typing.Any]]:
        req_vbs = self._objects_to_vbs(objects=objects)
        vbs = self._get_vbs_from_stub(stub=stub)
        res_vbs = snmp_agent.utils.get_next(req_vbs=req_vbs, vbs=vbs)
        res_objects = self._vbs_to_objects(res_vbs)
        return res_objects

    async def get_bulk(
        self,
        stub: stub_domain.Entity,
        objects: list[dict[str, typing.Any]],
        non_repeaters: int,
        max_repetitions: int,
    ) -> list[dict[str, typing.Any]]:
        req_vbs = self._objects_to_vbs(objects=objects)
        vbs = self._get_vbs_from_stub(stub=stub)
        res_vbs = snmp_agent.utils.get_bulk(
            req_vbs=req_vbs,
            vbs=vbs,
            non_repeaters=non_repeaters,
            max_repetitions=max_repetitions,
        )
        res_objects = self._vbs_to_objects(res_vbs)
        return res_objects
