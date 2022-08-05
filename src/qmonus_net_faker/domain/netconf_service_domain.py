import logging
import typing

from ..libs import netconf, xml_utils, str_utils
from . import yang_tree_domain, stub_domain

logger = logging.getLogger(__name__)

YANG_NAMESPACE = "urn:ietf:params:xml:ns:netconf:base:1.0"


class NetconfService(object):
    def __init__(
        self,
        session_id: typing.Optional[int],
        yang_tree_repo: yang_tree_domain.Repository,
    ):
        self._session_id = session_id
        self._yang_tree_repo = yang_tree_repo

    async def execute(self, stub: stub_domain.Entity, rpc: typing.Any) -> typing.Any:
        message_id = netconf.Netconf.get_message_id(rpc)
        protocol_operation = netconf.Netconf.get_protocol_operation(rpc=rpc)
        rpc = xml_utils.copy_xml(rpc)
        xml_utils.delete_namespace(rpc)

        datastore: typing.Any
        if protocol_operation in ["get-config"]:
            if rpc.xpath("./get-config/source/candidate"):
                datastore = "candidate"
            elif rpc.xpath("./get-config/source/running"):
                datastore = "running"
            elif rpc.xpath("./get-config/source/startup"):
                datastore = "startup"
            else:
                raise ValueError("Invalid request: {}".format(xml_utils.to_string(rpc)))

            results = rpc.xpath("./get-config/filter")
            if len(results) != 0:
                filter = results[0]
            else:
                filter = None

            rpc_reply = await self.get_config(
                message_id=message_id,
                stub=stub,
                datastore=datastore,
                filter=filter,
            )
        elif protocol_operation in ["get"]:
            results = rpc.xpath("./get/filter")
            if len(results) != 0:
                filter = results[0]
            else:
                filter = None

            rpc_reply = await self.get(
                message_id=message_id,
                stub=stub,
                filter=filter,
            )
        elif protocol_operation in ["validate"]:
            if rpc.xpath("./validate/source/candidate"):
                datastore = "candidate"
                config = None
            elif rpc.xpath("./validate/source/running"):
                datastore = "running"
                config = None
            elif rpc.xpath("./validate/source/startup"):
                datastore = "startup"
                config = None
            elif rpc.xpath("./validate/source/config"):
                datastore = None
                config = rpc.xpath("./validate/source/config")[0]
            else:
                raise ValueError("Invalid request: {}".format(xml_utils.to_string(rpc)))

            rpc_reply = await self.validate(
                message_id=message_id,
                stub=stub,
                datastore=datastore,
                config=config,
            )
        elif protocol_operation in ["lock"]:
            rpc_reply = await self.lock(
                message_id=message_id,
                stub=stub,
            )
        elif protocol_operation in ["unlock"]:
            rpc_reply = await self.unlock(
                message_id=message_id,
                stub=stub,
            )
        elif protocol_operation in ["edit-config"]:
            if rpc.xpath("./edit-config/target/candidate"):
                datastore = "candidate"
            elif rpc.xpath("./edit-config/target/running"):
                datastore = "running"
            else:
                raise ValueError("Invalid request: {}".format(xml_utils.to_string(rpc)))

            config = rpc.xpath("./edit-config/config")[0]

            results = rpc.xpath("./edit-config/default-operation")
            default_operation: typing.Any
            if len(results) == 0:
                default_operation = "merge"
            else:
                default_operation = results[0].text

            rpc_reply = await self.edit_config(
                message_id=message_id,
                stub=stub,
                datastore=datastore,
                config=config,
                default_operation=default_operation,
            )
        elif protocol_operation in ["discard-changes"]:
            rpc_reply = await self.discard_changes(
                message_id=message_id,
                stub=stub,
            )
        elif protocol_operation in ["commit"]:
            rpc_reply = await self.commit(
                message_id=message_id,
                stub=stub,
            )
        else:
            raise ValueError("'{}' not supported".format(protocol_operation))

        return rpc_reply

    async def get_config(
        self,
        message_id: str,
        stub: stub_domain.Entity,
        datastore: typing.Literal["candidate", "running", "startup"],
        filter: typing.Optional[typing.Any] = None,
    ) -> typing.Any:
        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError(f"YANG '{stub.yang.value}' does not exist.")

        try:
            config = stub.get_config(
                datastore=datastore,
                yang_tree=yang_tree,
                filter=filter,
            )

            data = xml_utils.create(
                tag="data",
                namespace="urn:ietf:params:xml:ns:netconf:base:1.0",
            )
            if config.xpath("./*"):
                xml_utils.append(parent=data, child=config[0])

            rpc_reply = self.create_rpc_reply(message_id=message_id, xml=data)
        except Exception as e:
            logger.exception(e)
            rpc_reply = self.create_rpc_error_reply(
                message_id=message_id,
                message=str(e),
            )

        return rpc_reply

    async def get(
        self,
        message_id: str,
        stub: stub_domain.Entity,
        filter: typing.Optional[typing.Any] = None,
    ) -> typing.Any:
        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError(f"YANG '{stub.yang}' does not exist.")

        try:
            config = stub.get_config(
                datastore="running",
                yang_tree=yang_tree,
                filter=filter,
            )

            xml_utils.delete_attribute(
                xml=config,
                name="node_type",
                recursive=True,
            )

            data = xml_utils.create(
                tag="data",
                namespace="urn:ietf:params:xml:ns:netconf:base:1.0",
            )
            if config.xpath("./*"):
                xml_utils.append(parent=data, child=config[0])

            rpc_reply = self.create_rpc_reply(message_id=message_id, xml=data)

        except Exception as e:
            logger.exception(e)
            rpc_reply = self.create_rpc_error_reply(
                message_id=message_id,
                message=str(e),
            )

        return rpc_reply

    async def lock(
        self,
        message_id: str,
        stub: stub_domain.Entity,
    ) -> typing.Any:
        rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        return rpc_reply

    async def unlock(
        self,
        message_id: str,
        stub: stub_domain.Entity,
    ) -> typing.Any:
        rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        return rpc_reply

    async def validate(
        self,
        message_id: str,
        stub: stub_domain.Entity,
        datastore: typing.Literal["candidate", "running", "startup", None] = None,
        config: typing.Optional[typing.Any] = None,
    ) -> typing.Any:
        if [datastore, config].count(None) != 1:
            raise ValueError("Either datastore or config must be set")

        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError("YANG '{}' not exists".format(stub.yang))

        try:
            stub.validate_config(
                datastore=datastore,
                config=config,
                yang_tree=yang_tree,
            )
            rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        except Exception as e:
            logger.exception(e)
            rpc_reply = self.create_rpc_error_reply(
                message_id=message_id,
                message=str(e),
            )

        return rpc_reply

    async def edit_config(
        self,
        message_id: str,
        stub: stub_domain.Entity,
        datastore: typing.Literal["candidate", "running", "startup"],
        config: typing.Any,
        default_operation: typing.Literal["merge", "replace", "none"] = "merge",
    ) -> typing.Any:
        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError("YANG '{}' not exists".format(stub.yang))

        try:
            stub.edit_config(
                datastore=datastore,
                config=config,
                yang_tree=yang_tree,
                default_operation=default_operation,
            )
            rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        except Exception as e:
            logger.exception(e)
            rpc_reply = netconf.Netconf.create_rpc_error_reply(
                message_id=message_id,
                message=str(e),
            )

        return rpc_reply

    async def discard_changes(
        self,
        message_id: str,
        stub: stub_domain.Entity,
    ) -> typing.Any:
        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError("YANG '{}' not exists".format(stub.yang))

        try:
            stub.discard_config_changes()
            rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        except Exception as e:
            logger.exception(e)
            rpc_reply = netconf.Netconf.create_rpc_error_reply(
                message_id=message_id, message=str(e)
            )

        return rpc_reply

    async def commit(
        self,
        message_id: str,
        stub: stub_domain.Entity,
    ) -> typing.Any:
        yang_tree = await self._yang_tree_repo.get(id=stub.yang)
        if yang_tree is None:
            raise ValueError("YANG '{}' not exists".format(stub.yang))

        try:
            stub.commit_config()
            rpc_reply = self.create_rpc_ok_reply(message_id=message_id)
        except Exception as e:
            logger.exception(e)
            rpc_reply = netconf.Netconf.create_rpc_error_reply(
                message_id=message_id, message=str(e)
            )

        return rpc_reply

    @staticmethod
    def get_protocol_operation(rpc: typing.Any) -> str:
        protocol_operation = xml_utils.get_localname(rpc[0])
        return protocol_operation

    @classmethod
    def get_message_id(cls, rpc: typing.Any) -> str:
        message_id: str = rpc.attrib["message-id"]
        return message_id

    @classmethod
    def create_rpc_reply(cls, message_id: str, xml: typing.Any) -> typing.Any:
        rpc_reply = xml_utils.create(
            tag="rpc-reply",
            namespace=YANG_NAMESPACE,
        )
        rpc_reply.attrib["message-id"] = message_id
        rpc_reply.append(xml)
        return rpc_reply

    @classmethod
    def create_rpc_ok_reply(cls, message_id: str) -> typing.Any:
        ok_xml = xml_utils.create("ok")
        xml = cls.create_rpc_reply(message_id=message_id, xml=ok_xml)
        return xml

    @classmethod
    def create_rpc_error_reply(
        cls, message_id: str, message: typing.Optional[str] = None
    ) -> typing.Any:
        if message is None:
            message = "syntax error"

        rpc_error_str = """
        <rpc-error>
            <error-type>protocol</error-type>
            <error-tag>operation-failed</error-tag>
            <error-severity>error</error-severity>
            <error-message>{message}</error-message>
            <error-info></error-info>
        </rpc-error>
        """.format(
            message=message
        )

        rpc_error_xml = xml_utils.from_string(rpc_error_str)
        xml_utils.replace_namespace(
            xml=rpc_error_xml, src=None, dst=YANG_NAMESPACE, recursive=True
        )

        xml = cls.create_rpc_reply(message_id=message_id, xml=rpc_error_xml)
        return xml

    def create_hello_message(self, capabilities: list[str]) -> typing.Any:
        variables = {"session_id": self._session_id, "capabilities": capabilities}
        template = """
        <hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            <capabilities>
                {% for capability in capabilities %}
                <capability>{{ capability }}</capability>
                {% endfor %}
            </capabilities>
            <session-id>{{ session_id }}</session-id>
        </hello>
        """
        hello_str = str_utils.render(template=template, variables=variables)
        hello = xml_utils.from_string(hello_str)
        return hello
