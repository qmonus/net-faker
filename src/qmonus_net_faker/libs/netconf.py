import typing

from . import str_utils
from . import yang, xml_utils

import logging

logger = logging.getLogger(__name__)

YANG_NAMESPACE = "urn:ietf:params:xml:ns:netconf:base:1.0"


class Netconf(object):
    """Support basic protocol only"""

    def __init__(
        self,
        yang_tree: yang.YangTree,
        candidate_config: typing.Any = None,
        running_config: typing.Any = None,
        startup_config: typing.Any = None,
    ) -> None:
        if candidate_config is None:
            _candidate_config = xml_utils.create(tag="root")
        else:
            _candidate_config = xml_utils.copy_xml(candidate_config)

        if running_config is None:
            _running_config = xml_utils.create(tag="root")
        else:
            _running_config = xml_utils.copy_xml(running_config)

        if startup_config is None:
            _startup_config = xml_utils.create(tag="root")
        else:
            _startup_config = xml_utils.copy_xml(startup_config)

        self.yang_tree = yang_tree
        self.candidate_config = _candidate_config
        self.running_config = _running_config
        self.startup_config = _startup_config
        self.config_updated: bool = False

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

    @classmethod
    def create_hello_message(
        cls, session_id: str, capabilities: list[str]
    ) -> typing.Any:
        variables = {"session_id": session_id, "capabilities": capabilities}
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

    def execute(self, rpc: typing.Any) -> typing.Any:
        protocol_operation = self.get_protocol_operation(rpc=rpc)

        if protocol_operation in ["get-config"]:
            rpc_reply = self.get_config(rpc=rpc)
        elif protocol_operation in ["get"]:
            rpc_reply = self.get(rpc=rpc)
        elif protocol_operation in ["validate"]:
            rpc_reply = self.validate(rpc=rpc)
        elif protocol_operation in ["edit-config"]:
            rpc_reply = self.edit_config(rpc=rpc)
        elif protocol_operation in ["discard-changes"]:
            rpc_reply = self.discard_changes(rpc=rpc)
        elif protocol_operation in ["commit"]:
            rpc_reply = self.commit(rpc=rpc)
        else:
            raise ValueError("'{}' not supported".format(protocol_operation))

        return rpc_reply

    def edit_config(self, rpc: typing.Any) -> typing.Any:
        # TODO: Support error-option rollback-on-error, stop-on-error

        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        try:
            if rpc.xpath("./edit-config/target/candidate"):
                target_config = self.candidate_config
            elif rpc.xpath("./edit-config/target/running"):
                target_config = self.running_config
            else:
                raise ValueError("Invalid request: {}".format(xml_utils.to_string(rpc)))

            results = rpc.xpath("./edit-config/default-operation")
            default_operation: str
            if len(results) == 0:
                default_operation = "merge"
            else:
                default_operation = results[0].text

            request_config = rpc.xpath("./edit-config/config")[0][0]

            root_node = self.yang_tree.get_root_node()
            self._edit_config_rec(
                node=root_node,
                target_config=target_config,
                request_config=request_config,
                default_operation=default_operation,
            )

            res_xml = self.create_rpc_ok_reply(message_id=message_id)

        except Exception as e:
            logger.exception(e)
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        self.config_updated = True
        return res_xml

    def _edit_config_rec(
        self,
        node: yang.YangNode,
        target_config: typing.Any,
        request_config: typing.Any,
        default_operation: str,
    ) -> None:
        child_node = node.get_child(name=request_config.tag)
        operation = request_config.attrib.get("operation", default_operation)

        if child_node.type == "container":
            if operation == "replace":
                _results = target_config.xpath(
                    "./*[local-name()='{}']".format(request_config.tag)
                )
                for _result in _results:
                    xml_utils.delete(_result)

            _results = target_config.xpath(
                "./*[local-name()='{}']".format(request_config.tag)
            )

            if operation in ["create", "merge", "replace", "none"]:
                if len(_results) == 0:
                    candidate_el_child = xml_utils.create(
                        tag=request_config.tag, namespace=child_node.namespace
                    )
                    target_config.append(candidate_el_child)
                else:
                    if operation == "create":
                        raise ValueError(
                            "'{}' already exists".format(
                                xml_utils.get_path(request_config)
                            )
                        )

                    candidate_el_child = _results[0]

                req_el_children = request_config.xpath("./*")
                for req_el_child in req_el_children:
                    self._edit_config_rec(
                        node=child_node,
                        target_config=candidate_el_child,
                        request_config=req_el_child,
                        default_operation=default_operation,
                    )

            elif operation in ["delete", "remove"]:
                if len(_results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError(
                        "'{}' not exists".format(xml_utils.get_path(request_config))
                    )

                child_target_config = _results[0]
                xml_utils.delete(child_target_config)
                self._delete_empty_config_rec(node=node, target_config=target_config)

            else:
                raise ValueError("Invalid operation: '{}'".format(operation))

        elif child_node.type == "list":
            if operation == "replace":
                _results = target_config.xpath(
                    "./*[local-name()='{}']".format(request_config.tag)
                )
                for _result in _results:
                    xml_utils.delete(_result)

            if (
                operation in ["delete", "remove"]
                and len(request_config.xpath("./*")) == 0
            ):
                # delete all items
                _results = target_config.xpath(
                    "./*[local-name()='{}']".format(request_config.tag)
                )
                if len(_results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError("'{}' not found".format(request_config.tag))

                for _result in _results:
                    xml_utils.delete(_result)

                self._delete_empty_config_rec(node=node, target_config=target_config)
                return

            keys = child_node.get_keys()

            conditions = ["local-name()='{}'".format(request_config.tag)]
            for key in keys:
                _results = request_config.xpath("./{}".format(key))
                if len(_results) == 0:
                    raise ValueError(
                        "'{}' must have key '{}'".format(
                            xml_utils.get_path(request_config), key
                        )
                    )

                req_key_el = _results[0]
                if req_key_el.text is None:
                    condition = "*[local-name()='{}' and not(text())]".format(
                        req_key_el.tag
                    )
                else:
                    condition = "*[local-name()='{}' and text()='{}']".format(
                        req_key_el.tag, req_key_el.text
                    )

                conditions.append(condition)

            condition_str = " and ".join(conditions)

            _results = target_config.xpath("./*[{}]".format(condition_str))

            if operation in ["create", "merge", "replace", "none"]:
                if len(_results) == 0:
                    candidate_el_child = xml_utils.create(
                        tag=request_config.tag, namespace=child_node.namespace
                    )
                    target_config.append(candidate_el_child)

                elif len(_results) == 1:
                    if operation == "create":
                        raise ValueError(
                            "'{}' already exists".format(
                                xml_utils.get_path(request_config)
                            )
                        )

                    candidate_el_child = _results[0]
                else:
                    raise Exception("FatalError: list nodes with same keys exist")

                rec_el_children = request_config.xpath("./*")
                for rec_el_child in rec_el_children:
                    self._edit_config_rec(
                        node=child_node,
                        target_config=candidate_el_child,
                        request_config=rec_el_child,
                        default_operation=default_operation,
                    )

            elif operation in ["delete", "remove"]:
                if len(_results) == 0:
                    if operation == "remove":
                        return

                    raise ValueError(
                        "'{}' not exists".format(xml_utils.get_path(request_config))
                    )

                xml_utils.delete(_results[0])
                self._delete_empty_config_rec(node=node, target_config=target_config)

            else:
                raise ValueError("Invalid operation: '{}'".format(operation))

        elif child_node.type == "leaf-list":
            if operation in ["create", "merge", "replace", "none"]:
                results = target_config.xpath(
                    "./*[local-name()='{}' and text()='{}']".format(
                        request_config.tag, request_config.text
                    )
                )
                if len(results) != 0:
                    if operation == "create":
                        raise ValueError(
                            "'{}' already exists".format(
                                xml_utils.get_path(request_config)
                            )
                        )

                    xml_utils.delete(results[0])

                candidate_child = xml_utils.create(
                    tag=request_config.tag, namespace=child_node.namespace
                )
                candidate_child.text = request_config.text
                target_config.append(candidate_child)

            elif operation in ["delete", "remove"]:
                _results = target_config.xpath(
                    "./*[local-name()='{}' and text()='{}']".format(
                        request_config.tag, request_config.text
                    )
                )
                if len(_results) == 0:
                    if operation == "remove":
                        return

                    raise ValueError(
                        "'{} {}' not exists".format(
                            xml_utils.get_path(request_config), request_config.text
                        )
                    )

                xml_utils.delete(_results[0])
                self._delete_empty_config_rec(node=node, target_config=target_config)

            else:
                raise ValueError("Invalid operation: '{}'".format(operation))

        elif child_node.type == "leaf":
            if operation in ["create", "merge", "replace", "none"]:
                _results = target_config.xpath(
                    "./*[local-name()='{}']".format(request_config.tag)
                )
                if len(_results) != 0:
                    if operation == "create":
                        raise ValueError(
                            "'{}' already exists".format(
                                xml_utils.get_path(request_config)
                            )
                        )

                    xml_utils.delete(_results[0])

                candidate_child = xml_utils.create(
                    tag=request_config.tag, namespace=child_node.namespace
                )
                candidate_child.text = request_config.text
                target_config.append(candidate_child)

            elif operation in ["delete", "remove"]:
                if request_config.text is not None:
                    raise ValueError(
                        "'{}' must not have text '{}' for delete operation".format(
                            xml_utils.get_path(request_config), request_config.text
                        )
                    )

                results = target_config.xpath(
                    "./*[local-name()='{}']".format(request_config.tag)
                )

                if len(results) == 0:
                    if operation == "remove":
                        return

                    raise ValueError(
                        "'{}' not exists".format(xml_utils.get_path(request_config))
                    )

                xml_utils.delete(results[0])
                self._delete_empty_config_rec(node=node, target_config=target_config)

            else:
                raise ValueError("Invalid operation: '{}'".format(operation))

        else:
            raise Exception("Invalid node_type '{}'".format(child_node.type))

    def _delete_empty_config_rec(
        self, node: yang.YangNode, target_config: typing.Any
    ) -> None:
        if node.type in ["container", "list"]:
            child_configs = target_config.xpath("./*")
            if len(child_configs) == 0:
                parent_node = node.get_parent()
                if parent_node is None:
                    raise ValueError(f"Invalid node")
                parent_config = target_config.getparent()
                xml_utils.delete(target_config)
                self._delete_empty_config_rec(
                    node=parent_node, target_config=parent_config
                )

    def get_config(self, rpc: typing.Any) -> typing.Any:
        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        try:
            if rpc.xpath("./get-config/source/candidate"):
                target_config = xml_utils.copy_xml(self.candidate_config)
            elif rpc.xpath("./get-config/source/running"):
                target_config = xml_utils.copy_xml(self.running_config)
            else:
                raise ValueError("Invalid request")

            root_node = self.yang_tree.get_root_node()
            results = rpc.xpath("./get-config/filter")
            if len(results) != 0:
                filter = results[0]
                self._filter_config(
                    node=root_node, target_config=target_config, filter=filter
                )

            # Create response xml
            data = xml_utils.create(
                tag="data", namespace="urn:ietf:params:xml:ns:netconf:base:1.0"
            )
            if target_config.xpath("./*"):
                xml_utils.append(parent=data, child=target_config[0])

            res_xml = self.create_rpc_reply(message_id=message_id, xml=data)

        except Exception as e:
            logger.exception(e)
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        return res_xml

    def get(self, rpc: typing.Any) -> typing.Any:
        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        try:
            target_config = xml_utils.copy_xml(self.running_config)

            results = rpc.xpath("./get/filter")
            if len(results) != 0:
                filter = results[0]
                root_node = self.yang_tree.get_root_node()
                self._filter_config(
                    node=root_node, target_config=target_config, filter=filter
                )

            # Create response xml
            data = xml_utils.create(
                tag="data", namespace="urn:ietf:params:xml:ns:netconf:base:1.0"
            )
            if target_config.xpath("./*"):
                xml_utils.append(parent=data, child=target_config[0])

            res_xml = self.create_rpc_reply(message_id=message_id, xml=data)

        except Exception as e:
            logger.exception(e)
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        return res_xml

    def _filter_config(
        self, node: yang.YangNode, target_config: typing.Any, filter: typing.Any
    ) -> None:
        self._set_visible_flag(
            parent_node=node, parent_target_config=target_config, parent_filter=filter
        )

        self._delete_non_visible_element(target_config=target_config)

    def _delete_non_visible_element(self, target_config: typing.Any) -> None:
        # set visible flag
        for element in target_config.xpath(".//*[@_visible]"):
            for target_el in element.xpath(".//*"):
                target_el.attrib["_visible"] = "true"

            target_el = element
            while True:
                if target_el is None:
                    break

                target_el.attrib["_visible"] = "true"
                target_el = target_el.getparent()

        # delete non-visible element
        for element in target_config.xpath(".//*[not(@_visible)]"):
            xml_utils.delete(element)

        # delete visible attribute
        for element in target_config.xpath("//*[@_visible]"):
            del element.attrib["_visible"]

    def _set_visible_flag(
        self,
        parent_node: yang.YangNode,
        parent_target_config: typing.Any,
        parent_filter: typing.Any,
    ) -> None:
        for filter in parent_filter.xpath("./*"):
            node = parent_node.get_child(name=filter.tag)

            if node.type == "container":
                results = parent_target_config.xpath(
                    './*[local-name()="{}"]'.format(filter.tag)
                )

                if len(results) == 0:
                    pass
                else:
                    target_config = results[0]

                    if len(filter.xpath("./*")) == 0:
                        target_config.attrib["_visible"] = "true"
                    else:
                        self._set_visible_flag(
                            parent_node=node,
                            parent_target_config=target_config,
                            parent_filter=filter,
                        )

            elif node.type == "list":
                target_configs = parent_target_config.xpath(
                    "./*[local-name()='{}']".format(filter.tag)
                )

                if len(target_configs) == 0:
                    pass

                else:
                    if len(filter.xpath("./*")) == 0:
                        for target_config in target_configs:
                            target_config.attrib["_visible"] = "true"
                    else:
                        # get key values
                        keys = node.get_keys()

                        keys_are_match_nodes = False
                        for key in keys:
                            filter_key = filter.xpath("./{}".format(key))[0]
                            if filter_key.text is not None:
                                keys_are_match_nodes = True
                                break

                        if keys_are_match_nodes:
                            conditions = ["local-name()='{}'".format(filter.tag)]
                            for key in keys:
                                filter_key = filter.find("./{}".format(key))
                                condition = (
                                    "*[local-name()='{}' and text()='{}']".format(
                                        filter_key.tag, filter_key.text
                                    )
                                )
                                conditions.append(condition)

                            condition_str = " and ".join(conditions)

                            _results = parent_target_config.xpath(
                                "./*[{}]".format(condition_str)
                            )

                            if len(_results) == 0:
                                # no match
                                pass
                            elif len(_results) == 1:
                                target_config = _results[0]
                                child_filters = filter.xpath("./*")
                                non_key_filters = [
                                    node
                                    for node in child_filters
                                    if node.tag not in keys
                                ]
                                if len(non_key_filters) == 0:
                                    # only key nodes specified in filter
                                    child_target_configs = target_config.xpath("./*")
                                    for child_target_config in child_target_configs:
                                        child_target_config.attrib["_visible"] = "true"

                                else:
                                    # non-key-nodes exist
                                    # at least key nodes are set to visible
                                    self._set_visible_flag(
                                        parent_node=node,
                                        parent_target_config=target_config,
                                        parent_filter=filter,
                                    )

                                    # check if other_nodes are visible
                                    visible = False
                                    for child_target_config in target_config.xpath(
                                        "./*"
                                    ):
                                        if child_target_config.tag in keys:
                                            continue

                                        if "_visible" in child_target_config.attrib:
                                            visible = True
                                            break

                                        els = child_target_config.xpath(
                                            ".//*[@_visible]"
                                        )
                                        if len(els) > 0:
                                            visible = True
                                            break

                                    if not visible:
                                        for el in target_config.xpath(
                                            ".//*[@_visible]"
                                        ):
                                            del el.attrib["_visible"]

                            else:
                                raise Exception(
                                    "FatalError: lists with same keys exist"
                                )

                        else:
                            # keys are selection nodes
                            for target_config in parent_target_config.xpath("./*"):
                                child_filters = filter.xpath("./*")
                                non_key_filters = [
                                    node
                                    for node in child_filters
                                    if node.tag not in keys
                                ]

                                if len(non_key_filters) == 0:
                                    # only key nodes specified in filter
                                    self._set_visible_flag(
                                        parent_node=node,
                                        parent_target_config=target_config,
                                        parent_filter=filter,
                                    )

                                else:
                                    # non-key-nodes exist
                                    self._set_visible_flag(
                                        parent_node=node,
                                        parent_target_config=target_config,
                                        parent_filter=filter,
                                    )

                                    # check if other_nodes are visible
                                    visible = False
                                    for child_target_config in target_config.xpath(
                                        "./*"
                                    ):
                                        if (
                                            xml_utils.get_localname(child_target_config)
                                            in keys
                                        ):
                                            continue

                                        if "_visible" in child_target_config.attrib:
                                            visible = True
                                            break

                                        els = child_target_config.xpath(
                                            ".//*[@_visible]"
                                        )
                                        if len(els) > 0:
                                            visible = True
                                            break

                                    if not visible:
                                        for el in target_config.xpath(
                                            ".//*[@_visible]"
                                        ):
                                            del el.attrib["_visible"]

            elif node.type == "leaf-list":
                results = parent_target_config.xpath(
                    "./*[local-name()='{}']".format(filter.tag)
                )
                if len(results) == 0:
                    pass

                else:
                    target_config = results[0]
                    if filter.text is None:
                        target_config.attrib["_visible"] = "true"
                    else:
                        # correct?
                        raise Exception("text is forbidden for leaf-list node filter?")

            elif node.type == "leaf":
                results = parent_target_config.xpath(
                    "./*[local-name()='{}']".format(filter.tag)
                )
                if len(results) == 0:
                    pass

                else:
                    target_config = results[0]
                    if filter.text is None:
                        target_config.attrib["_visible"] = "true"
                    else:
                        if filter.text == target_config.text:
                            target_config.attrib["_visible"] = "true"

    def validate(self, rpc: typing.Any) -> typing.Any:
        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc=rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        source = rpc.xpath("./validate/source/*")[0].tag
        if source == "candidate":
            config = self.candidate_config
        elif source == "running":
            config = self.running_config
        elif source == "startup":
            config = self.startup_config
        else:
            raise ValueError("source '{}' is not supported".format(source))

        try:
            self.yang_tree.validate(config=config)
            res_xml = self.create_rpc_ok_reply(message_id=message_id)
        except Exception as e:
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        return res_xml

    def discard_changes(self, rpc: typing.Any) -> typing.Any:
        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc=rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        try:
            self.candidate_config = xml_utils.copy_xml(self.running_config)
            res_xml = self.create_rpc_ok_reply(message_id=message_id)

        except Exception as e:
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        self.config_updated = True
        return res_xml

    def commit(self, rpc: typing.Any) -> typing.Any:
        rpc = xml_utils.copy_xml(rpc)
        message_id = self.get_message_id(rpc=rpc)
        xml_utils.delete_namespace(rpc, backup_attr="namespace")

        try:
            self.running_config = xml_utils.copy_xml(self.candidate_config)
            res_xml = self.create_rpc_ok_reply(message_id=self.get_message_id(rpc))

        except Exception as e:
            res_xml = self.create_rpc_error_reply(message_id=message_id, message=str(e))

        self.config_updated = True
        return res_xml
