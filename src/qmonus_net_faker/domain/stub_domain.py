from __future__ import annotations
import logging
import typing
import json
import copy
import abc

from ..libs import xml_utils, yang
from ..domain import yang_tree_domain

logger = logging.getLogger(__name__)


class Entity(object):
    def __init__(
        self,
        id: Id,
        description: Description,
        handler: Handler,
        yang: yang_tree_domain.Id,
        enabled: Enabled,
    ) -> None:
        self.id = id
        self.description = description
        self.enabled = enabled
        self.handler = handler
        self.yang = yang

        self._snmp_objects: typing.Dict[str, SnmpObject] = {}

        self._candidate_config = ConfigEntity(
            value=xml_utils.from_string(string="<root/>")
        )
        self._running_config = ConfigEntity(
            value=xml_utils.from_string(string="<root/>")
        )
        self._startup_config = ConfigEntity(
            value=xml_utils.from_string(string="<root/>")
        )
        self._metadata = MetadataEntity(value={})

    # candidate config
    def get_candidate_config(self) -> typing.Any:
        return xml_utils.copy_xml(self._candidate_config.value)

    def set_candidate_config(self, config: typing.Any) -> None:
        self._candidate_config = ConfigEntity(value=xml_utils.copy_xml(config))

    # running config
    def get_running_config(self) -> typing.Any:
        return xml_utils.copy_xml(self._running_config.value)

    def set_running_config(self, config: typing.Any) -> None:
        self._running_config = ConfigEntity(value=xml_utils.copy_xml(config))

    # startup_config
    def get_startup_config(self) -> typing.Any:
        return xml_utils.copy_xml(self._startup_config.value)

    def set_startup_config(self, config: typing.Any) -> None:
        self._startup_config = ConfigEntity(value=xml_utils.copy_xml(config))

    # metadata
    def get_metadata(self) -> dict[typing.Any, typing.Any]:
        return copy.deepcopy(self._metadata.value)

    def set_metadata(self, value: dict[typing.Any, typing.Any]) -> None:
        self._metadata = MetadataEntity(copy.deepcopy(value))

    # SNMP
    def get_snmp_object(self, oid: str) -> typing.Optional[SnmpObject]:
        return copy.deepcopy(self._snmp_objects.get(oid))

    def list_snmp_objects(self) -> dict[str, SnmpObject]:
        return copy.deepcopy(self._snmp_objects)

    def set_snmp_object(
        self,
        oid: str,
        type: typing.Literal[
            "OCTET_STRING",
            "INTEGER",
            "COUNTER32",
            "COUNTER64",
            "GAUGE32",
            "TIMETICKS",
            "OBJECT_IDENTIFIER",
            "NULL",
            "IP_ADDRESS",
            "NO_SUCH_OBJECT",
            "NO_SUCH_INSTANCE",
            "END_OF_MIB_VIEW",
        ],
        value: typing.Any,
    ) -> None:
        self._snmp_objects[oid] = SnmpObject(oid=oid, type=type, value=value)

    def delete_snmp_object(self, oid: str) -> None:
        del self._snmp_objects[oid]

    def delete_all_snmp_objects(self) -> None:
        self._snmp_objects = {}

    def edit_config(
        self,
        datastore: typing.Literal["candidate", "running", "startup"],
        config: typing.Any,
        yang_tree: yang_tree_domain.Entity,
        default_operation: typing.Literal["merge", "replace", "none"] = "merge",
    ) -> None:
        _config = xml_utils.copy_xml(config)
        xml_utils.delete_namespace(_config, backup_attr="namespace")

        if datastore == "candidate":
            target_config = self.get_candidate_config()
        elif datastore == "running":
            target_config = self.get_running_config()
        elif datastore == "startup":
            target_config = self.get_startup_config()
        else:
            raise ValueError(f"Invalid datastore: {datastore}")

        if default_operation not in ["merge", "replace", "none"]:
            raise ValueError(f"Invalid default_operation: '{default_operation}'")
        if yang_tree.id != self.yang:
            raise ValueError(f"yang_tree.id must be '{self.yang.value}'")

        root_node = yang_tree.get_root_node()
        self._edit_config_rec(
            node=root_node,
            target_config=target_config,
            request_config=_config[0],
            default_operation=default_operation,
        )
        self._delete_empty_containers(root_config=target_config)

        if datastore == "candidate":
            self.set_candidate_config(target_config)
        elif datastore == "running":
            self.set_running_config(target_config)
        elif datastore == "startup":
            self.set_startup_config(target_config)
        else:
            raise ValueError(f"Invalid datastore: {datastore}")

    def _edit_config_rec(
        self,
        node: yang.YangNode,
        target_config: typing.Any,
        request_config: typing.Any,
        default_operation: typing.Literal["merge", "replace", "none"],
    ) -> None:
        child_node = node.get_child(name=request_config.tag)
        operation = request_config.attrib.get("operation", default_operation)

        # delete
        choice_ids = child_node.get_choice_ids()
        if choice_ids:
            for child_target_config in target_config.xpath("./*"):
                _result = child_target_config.attrib.get("choice_ids")
                if _result:
                    config_choice_ids = json.loads(_result)
                    min_len = min(len(config_choice_ids), len(choice_ids))
                    if config_choice_ids[:min_len] != choice_ids[:min_len]:
                        xml_utils.delete(child_target_config)

        if child_node.type == "container":
            if operation == "replace":
                _results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}']"
                )
                for _result in _results:
                    xml_utils.delete(_result)

            _results = target_config.xpath(f"./*[local-name()='{request_config.tag}']")

            if operation in ("create", "merge", "replace", "none"):
                if len(_results) == 0:
                    candidate_el_child = xml_utils.create(
                        tag=request_config.tag,
                        namespace=child_node.namespace,
                    )
                    candidate_el_child.attrib["node_type"] = "container"
                    if choice_ids:
                        candidate_el_child.attrib["choice_ids"] = json.dumps(choice_ids)
                    target_config.append(candidate_el_child)
                else:
                    if operation == "create":
                        raise ValueError(
                            f"'{xml_utils.get_path(request_config)}' already exists."
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
            else:
                raise ValueError(f"Invalid operation: '{operation}'")
        elif child_node.type == "list":
            if operation == "replace":
                _results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}']"
                )
                for _result in _results:
                    xml_utils.delete(_result)

            if (
                operation in ("delete", "remove")
                and len(request_config.xpath("./*")) == 0
            ):
                # delete all items
                _results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}']"
                )
                if len(_results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError(f"'{request_config.tag}' not found")

                for _result in _results:
                    xml_utils.delete(_result)
                return

            keys = child_node.get_keys()

            conditions = [f"local-name()='{request_config.tag}'"]
            for key in keys:
                _results = request_config.xpath(f"./{key}")
                if len(_results) == 0:
                    raise ValueError(
                        f"'{xml_utils.get_path(request_config)}' must have key '{key}'"
                    )

                req_key_el = _results[0]
                if req_key_el.text is None:
                    condition = f"*[local-name()='{req_key_el.tag}' and not(text())]"
                else:
                    condition = f"*[local-name()='{req_key_el.tag}' and text()='{req_key_el.text}']"

                conditions.append(condition)

            condition_str = " and ".join(conditions)

            _results = target_config.xpath("./*[{}]".format(condition_str))

            if operation in ("create", "merge", "replace", "none"):
                if len(_results) == 0:
                    candidate_el_child = xml_utils.create(
                        tag=request_config.tag,
                        namespace=child_node.namespace,
                    )
                    candidate_el_child.attrib["node_type"] = "list"
                    if choice_ids:
                        candidate_el_child.attrib["choice_ids"] = json.dumps(choice_ids)
                    target_config.append(candidate_el_child)
                elif len(_results) == 1:
                    if operation == "create":
                        raise ValueError(
                            f"'{xml_utils.get_path(request_config)}' already exists."
                        )
                    candidate_el_child = _results[0]
                else:
                    raise Exception("FatalError: list nodes with same keys exist.")

                rec_el_children = request_config.xpath("./*")
                for rec_el_child in rec_el_children:
                    self._edit_config_rec(
                        node=child_node,
                        target_config=candidate_el_child,
                        request_config=rec_el_child,
                        default_operation=default_operation,
                    )
            elif operation in ("delete", "remove"):
                if len(_results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError(
                        f"'{xml_utils.get_path(request_config)}' does not exist."
                    )

                xml_utils.delete(_results[0])
            else:
                raise ValueError(f"Invalid operation: '{operation}'")

        elif child_node.type == "leaf-list":
            if operation in ("create", "merge", "replace", "none"):
                results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}' and text()='{request_config.text}']"
                )
                if len(results) != 0:
                    if operation == "create":
                        raise ValueError(
                            f"'{xml_utils.get_path(request_config)}' already exists."
                        )

                    xml_utils.delete(results[0])

                candidate_child = xml_utils.create(
                    tag=request_config.tag,
                    namespace=child_node.namespace,
                )
                candidate_child.attrib["node_type"] = "leaf-list"
                if choice_ids:
                    candidate_child.attrib["choice_ids"] = json.dumps(choice_ids)
                candidate_child.text = request_config.text
                target_config.append(candidate_child)
            elif operation in ("delete", "remove"):
                _results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}' and text()='{request_config.text}']"
                )
                if len(_results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError(
                        f"'{xml_utils.get_path(request_config)} {request_config.text}' does not exist."
                    )

                xml_utils.delete(_results[0])
            else:
                raise ValueError(f"Invalid operation: '{operation}'")
        elif child_node.type == "leaf":
            if operation in ("create", "merge", "replace", "none"):
                _results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}']"
                )
                if len(_results) != 0:
                    if operation == "create":
                        raise ValueError(
                            f"'{xml_utils.get_path(request_config)}' already exists."
                        )

                    xml_utils.delete(_results[0])

                candidate_child = xml_utils.create(
                    tag=request_config.tag,
                    namespace=child_node.namespace,
                )
                candidate_child.attrib["node_type"] = "leaf"
                if choice_ids:
                    candidate_child.attrib["choice_ids"] = json.dumps(choice_ids)
                candidate_child.text = request_config.text
                target_config.append(candidate_child)
            elif operation in ("delete", "remove"):
                if request_config.text is not None:
                    raise ValueError(
                        f"'{xml_utils.get_path(request_config)}' must not have "
                        f"text '{request_config.text}' for delete operation."
                    )

                results = target_config.xpath(
                    f"./*[local-name()='{request_config.tag}']"
                )
                if len(results) == 0:
                    if operation == "remove":
                        return
                    raise ValueError(
                        f"'{xml_utils.get_path(request_config)}' does not exist."
                    )

                xml_utils.delete(results[0])
            else:
                raise ValueError(f"Invalid operation: '{operation}'")
        else:
            raise Exception(f"Invalid node_type '{child_node.type}'")

    def _delete_empty_containers(self, root_config: typing.Any) -> None:
        containers = root_config.xpath(
            ".//*[@node_type='container' and not(.//*[@node_type='leaf' or @node_type='leaf-list'])]"
        )
        for container in containers:
            xml_utils.delete(xml=container)

    def get_config(
        self,
        datastore: typing.Literal["candidate", "running", "startup"],
        yang_tree: yang_tree_domain.Entity,
        filter: typing.Any = None,
    ) -> typing.Any:
        if filter is None:
            _filter = None
        else:
            _filter = xml_utils.copy_xml(filter)
            xml_utils.delete_namespace(_filter, backup_attr="namespace")

        if datastore == "candidate":
            target_config = self.get_candidate_config()
        elif datastore == "running":
            target_config = self.get_running_config()
        elif datastore == "startup":
            target_config = self.get_startup_config()
        else:
            raise ValueError(f"Invalid datastore: '{datastore}'")

        if _filter is not None:
            root_node = yang_tree.get_root_node()
            self._filter_config(
                node=root_node,
                target_config=target_config,
                filter=_filter,
            )

        xml_utils.delete_attribute(
            xml=target_config,
            name="node_type",
            recursive=True,
        )
        xml_utils.delete_attribute(
            xml=target_config,
            name="choice_ids",
            recursive=True,
        )
        return target_config

    def _filter_config(
        self, node: yang.YangNode, target_config: typing.Any, filter: typing.Any
    ) -> None:
        self._set_visible_flag(
            node=node,
            target_config=target_config,
            filter=filter,
        )
        self._delete_non_visible_element(target_config=target_config)
        self._unset_visible_flag(target_config=target_config)

    def _delete_non_visible_element(self, target_config: typing.Any) -> None:
        # delete non-visible element
        for element in target_config.xpath(".//*[not(@_visible)]"):
            xml_utils.delete(element)

    def _set_visible_flag(
        self, node: yang.YangNode, target_config: typing.Any, filter: typing.Any
    ) -> None:
        def _set_visible_flag(
            parent_node: typing.Any,
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
                            _set_visible_flag(
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
                                        child_target_configs = target_config.xpath(
                                            "./*"
                                        )
                                        for child_target_config in child_target_configs:
                                            child_target_config.attrib["_visible"] = (
                                                "true"
                                            )

                                    else:
                                        # non-key-nodes exist
                                        # at least key nodes are set to visible
                                        _set_visible_flag(
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
                                        _set_visible_flag(
                                            parent_node=node,
                                            parent_target_config=target_config,
                                            parent_filter=filter,
                                        )
                                    else:
                                        # non-key-nodes exist
                                        _set_visible_flag(
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
                                                xml_utils.get_localname(
                                                    child_target_config
                                                )
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
                            raise Exception(
                                "text is forbidden for leaf-list node filter"
                            )
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

        _set_visible_flag(
            parent_node=node,
            parent_target_config=target_config,
            parent_filter=filter,
        )

        for element in target_config.xpath(".//*[@_visible]"):
            for target_el in element.xpath(".//*"):
                target_el.attrib["_visible"] = "true"

            target_el = element
            while True:
                if target_el is None:
                    break
                target_el.attrib["_visible"] = "true"
                target_el = target_el.getparent()

    def _unset_visible_flag(self, target_config: typing.Any) -> None:
        xml_utils.delete_attribute(
            xml=target_config,
            name="_visible",
            recursive=True,
        )

    def validate_config(
        self,
        yang_tree: yang_tree_domain.Entity,
        datastore: typing.Literal["candidate", "running", "startup", None] = None,
        config: typing.Optional[typing.Any] = None,
    ) -> None:
        if [datastore, config].count(None) != 1:
            raise ValueError("Either datastore or config must be set")

        if datastore:
            if datastore == "candidate":
                _config = self.get_candidate_config()
            elif datastore == "running":
                _config = self.get_running_config()
            elif datastore == "startup":
                _config = self.get_startup_config()
            else:
                raise ValueError(f"Invalid datastore value: '{datastore}'")
        else:
            _config = config

        try:
            yang_tree.validate(config=_config)
        except Exception as e:
            raise Exception(f"ValidationError: {e}")

    def discard_config_changes(self) -> None:
        self._candidate_config = ConfigEntity(value=self.get_running_config())

    def commit_config(self) -> None:
        self._running_config = ConfigEntity(value=self.get_candidate_config())


class MetadataEntity(object):
    def __init__(self, value: dict[typing.Any, typing.Any]) -> None:
        self.id = "0"
        self.value = value


class ConfigEntity(object):
    def __init__(self, value: typing.Any) -> None:
        self.id = "0"
        self.value = value


class Id(object):
    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Description(object):
    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Handler(object):
    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Enabled(object):
    def __init__(self, value: bool) -> None:
        self._value = value

    @property
    def value(self) -> bool:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class SnmpObject(object):
    def __init__(self, oid: str, type: str, value: typing.Any) -> None:
        if not isinstance(oid, str):
            raise TypeError("oid must be str")

        if not isinstance(type, str):
            raise TypeError("type must be str")

        self.oid = oid
        self.type = type
        self.value = value

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Repository(abc.ABC):
    @abc.abstractmethod
    async def get(self, id: Id) -> typing.Optional[Entity]:
        pass

    @abc.abstractmethod
    async def list(
        self, id: typing.Union[Id, typing.List[Id], None] = None
    ) -> typing.List[Entity]:
        pass

    @abc.abstractmethod
    async def add(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def save(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def update(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def remove(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def remove_all(self) -> None:
        pass
