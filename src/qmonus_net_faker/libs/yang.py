from __future__ import annotations
import typing
import re
import copy
import logging

from . import pyang_wrapper, xml_utils

logger = logging.getLogger(__name__)


class YangTreeBuilder(object):
    def __init__(self) -> None:
        self._yang_map: typing.Dict[str, str] = {}

    def add_yang(
        self,
        filename: str,
        text: str,
    ) -> None:
        module_name = filename.split(".")[0].split("@")[0]
        self._yang_map[module_name] = text

    def build(self) -> YangTree:
        # Convert yang to yin
        yin_map = {}
        for module_name in self._yang_map:
            logger.info(f"Parsing YANG file '{module_name}'...")
            yin_string = pyang_wrapper.convert(
                module_name=module_name,
                yang_map=self._yang_map,
            )
            yin = xml_utils.from_string(yin_string)
            yin_map[module_name] = yin

        logger.info("Building YANG tree...")

        # Delete yang namespace
        for root_yang_module in yin_map.values():
            xml_utils.delete_namespace(root_yang_module)

        # Create schema-tree
        root_schema_tree = xml_utils.create(tag="root")
        for module_name, root_yang_module in yin_map.items():
            if root_yang_module.tag == "submodule":
                continue

            namespace = self._get_module_namespace(
                yin_map=yin_map, root_yang_module=root_yang_module
            )
            module_schema_tree = xml_utils.create_sub(
                parent=root_schema_tree, tag="module", namespace=namespace
            )
            xml_utils.set_attribute(
                xml=module_schema_tree, name="name", value=module_name
            )
            self._build_schema_tree_rec(
                namespace=namespace,
                module_name=module_name,
                yin_map=yin_map,
                parent_yang_module=root_yang_module,
                parent_schema_tree=module_schema_tree,
            )

        # Build augment
        self._build_augment(root_schema_tree=root_schema_tree)

        # Return
        yang_tree = YangTree(xml=root_schema_tree)
        return yang_tree

    @classmethod
    def _build_schema_tree_rec(
        cls,
        namespace: str,
        module_name: str,
        yin_map: typing.Any,
        parent_yang_module: typing.Any,
        parent_schema_tree: typing.Any,
    ) -> None:
        root_yang_module = parent_yang_module.xpath("/*")[0]
        yang_module_name = root_yang_module.attrib["name"]
        yang_module_prefix = cls._get_module_prefix(root_yang_module)

        yang_statements = parent_yang_module.xpath("./*")

        for yang_statement in yang_statements:
            yang_statement_name = xml_utils.get_localname(yang_statement)

            if yang_statement_name == "include":
                yang_module_name_to_include = yang_statement.attrib["module"]
                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yin_map[yang_module_name_to_include],
                    parent_schema_tree=parent_schema_tree,
                )

            elif yang_statement_name == "leaf":
                new_parent_schema_tree = cls._wrap_with_case_if_needed(
                    parent_schema_tree=parent_schema_tree,
                    yang_statement=yang_statement,
                    namespace=namespace,
                )

                node = cls._create_node(
                    parent=new_parent_schema_tree,
                    tag="leaf",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

            elif yang_statement_name == "leaf-list":
                new_parent_schema_tree = cls._wrap_with_case_if_needed(
                    parent_schema_tree=parent_schema_tree,
                    yang_statement=yang_statement,
                    namespace=namespace,
                )

                node = cls._create_node(
                    parent=new_parent_schema_tree,
                    tag="leaf-list",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

            elif yang_statement_name == "container":
                new_parent_schema_tree = cls._wrap_with_case_if_needed(
                    parent_schema_tree=parent_schema_tree,
                    yang_statement=yang_statement,
                    namespace=namespace,
                )

                node = cls._create_node(
                    parent=new_parent_schema_tree,
                    tag="container",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=node,
                )

            elif yang_statement_name == "list":
                new_parent_schema_tree = cls._wrap_with_case_if_needed(
                    parent_schema_tree=parent_schema_tree,
                    yang_statement=yang_statement,
                    namespace=namespace,
                )

                node = cls._create_node(
                    parent=new_parent_schema_tree,
                    tag="list",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

                _results = yang_statement.xpath("./key")
                if len(_results) > 0:
                    key_stmt = _results[0]

                    key_schema_node = xml_utils.create_sub(
                        parent=node, tag="key", namespace=namespace
                    )
                    key_schema_node.attrib["value"] = key_stmt.attrib["value"]

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=node,
                )

            elif yang_statement_name == "choice":
                new_parent_schema_tree = cls._wrap_with_case_if_needed(
                    parent_schema_tree=parent_schema_tree,
                    yang_statement=yang_statement,
                    namespace=namespace,
                )

                node = cls._create_node(
                    parent=new_parent_schema_tree,
                    tag="choice",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=node,
                )

            elif yang_statement_name == "case":
                node = cls._create_node(
                    parent=parent_schema_tree,
                    tag="case",
                    name=yang_statement.attrib["name"],
                    namespace=namespace,
                )

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=node,
                )

            elif yang_statement_name == "augment":
                schema_node = xml_utils.create_sub(
                    parent=parent_schema_tree, tag="augment", namespace=namespace
                )

                target_node = yang_statement.attrib["target-node"]

                # convert prefix to namespace
                schema_node.attrib["target-node"] = cls.resolve_target_node(
                    target_node=target_node,
                    default_namespace=namespace,
                    root_yang_module=root_yang_module,
                    yin_map=yin_map,
                )

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=schema_node,
                )

            elif yang_statement_name == "uses":
                _segments = yang_statement.attrib["name"].split(":")
                if len(_segments) == 1:
                    target_prefix = yang_module_prefix
                    target_grouping_name = _segments[0]
                elif len(_segments) == 2:
                    target_prefix = _segments[0]
                    target_grouping_name = _segments[1]
                else:
                    raise ValueError(
                        "Invalid uses statement: 'uses {}'".format(
                            yang_statement.attrib["name"]
                        )
                    )

                grouping_yang_module = None
                if target_prefix == yang_module_prefix:
                    # search in current modules
                    _target_xml = yang_statement
                    while _target_xml is not None:
                        results = _target_xml.xpath(
                            "./grouping[@name='{}']".format(target_grouping_name)
                        )
                        if len(results) != 0:
                            grouping_yang_module = results[0]
                            break

                        _target_xml = _target_xml.getparent()

                    if grouping_yang_module is None:
                        # search in included modules
                        if root_yang_module.tag == "module":
                            # module
                            _yang_submodules = cls._get_submodules(
                                root_yang_module=root_yang_module, yin_map=yin_map
                            )

                            target_yang_modules = _yang_submodules
                        else:
                            # submodule
                            _parent_yang_module = cls._get_parent_module(
                                root_yang_module=root_yang_module, yang_modules=yin_map
                            )

                            target_yang_modules = cls._get_submodules(
                                root_yang_module=_parent_yang_module, yin_map=yin_map
                            )

                        for _yang_module in target_yang_modules:
                            _results = _yang_module.xpath(
                                "./grouping[@name='{}']".format(target_grouping_name)
                            )

                            if len(_results) == 1:
                                grouping_yang_module = _results[0]
                                break

                if grouping_yang_module is None:
                    # search in imported modules
                    target_yang_module_name = cls._get_module_name_by_import_prefix(
                        root_yang_module=root_yang_module, prefix=target_prefix
                    )

                    target_yang_module = yin_map[target_yang_module_name]

                    target_yang_submodules = cls._get_submodules(
                        root_yang_module=target_yang_module, yin_map=yin_map
                    )

                    for _yang_module in [target_yang_module] + target_yang_submodules:
                        _results = _yang_module.xpath(
                            "./grouping[@name='{}']".format(target_grouping_name)
                        )

                        if len(_results) == 1:
                            grouping_yang_module = _results[0]
                            break

                if grouping_yang_module is None:
                    raise ValueError(
                        "grouping '{}' not found for uses statement".format(
                            target_grouping_name
                        )
                    )

                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=grouping_yang_module,
                    parent_schema_tree=parent_schema_tree,
                )

                # augment, etc
                cls._build_schema_tree_rec(
                    namespace=namespace,
                    module_name=module_name,
                    yin_map=yin_map,
                    parent_yang_module=yang_statement,
                    parent_schema_tree=parent_schema_tree,
                )

            else:
                # node = xml_utils.copy_xml(yang_statement)
                # xml_utils.delete_namespace(node)
                # xml_utils.append(parent=parent_schema_tree, child=node)
                pass

    @classmethod
    def _create_node(
        cls,
        parent: typing.Any,
        tag: str,
        name: str,
        namespace: str,
    ) -> typing.Any:
        element = xml_utils.create_sub(parent=parent, tag=tag, namespace=namespace)
        xml_utils.set_attribute(xml=element, name="name", value=name)
        return element

    @classmethod
    def _build_augment(cls, root_schema_tree: typing.Any) -> None:
        def _sort(augment_stmt: typing.Any) -> int:
            parents = xml_utils.get_parents(augment_stmt)
            nodes = [
                parent
                for parent in parents
                if xml_utils.get_localname(parent)
                in ["augment", "container", "list", "leaf", "leaf-list"]
            ]
            nodes.insert(0, augment_stmt)

            num_of_nodes = 0
            for node in nodes:
                if xml_utils.get_localname(node) in ["augment"]:
                    num_of_nodes += len(
                        node.attrib["target-node"].lstrip("/").split("/")
                    )
                else:
                    num_of_nodes += 1

            return num_of_nodes

        augment_stmts = root_schema_tree.xpath(".//*[local-name()='augment']")

        sorted_augment_stmts = sorted(augment_stmts, key=_sort)

        for augment_stmt in sorted_augment_stmts:
            target_node = augment_stmt.attrib["target-node"]
            segments = re.findall(r"{.+?}[^/]+", target_node)

            node_xpaths = []
            for segment in segments:
                m = re.match(r"\A{(.+)}(.+)\Z", segment)
                if m is None:
                    raise ValueError("Invalid segment")
                namespace = m.group(1)
                node_name = m.group(2)

                _xpath = (
                    r"*[@name='{node_name}' and namespace-uri()='{namespace}']".format(
                        node_name=node_name, namespace=namespace
                    )
                )
                node_xpaths.append(_xpath)

            if target_node.startswith("/"):
                # absolute
                xpath = "./*[local-name()='module']/" + "/".join(node_xpaths)
                _results = root_schema_tree.xpath(xpath)
            else:
                # descendant
                xpath = "../" + "/".join(node_xpaths)
                _results = augment_stmt.xpath(xpath)

            if len(_results) == 0:
                logger.warning(
                    "Failed to augment from '{}'. '{}' not exists on yang tree".format(
                        xml_utils.get_path(xml=augment_stmt), target_node
                    )
                )
                continue

            parent_schema_tree = _results[0]

            for child in augment_stmt.xpath("./*"):
                if xml_utils.get_localname(parent_schema_tree) == "choice":
                    if xml_utils.get_localname(child) != "case":
                        # if augment to choice without case
                        _parent_schema_tree = xml_utils.create_sub(
                            parent=parent_schema_tree,
                            tag="case",
                            namespace=xml_utils.get_namespace(parent_schema_tree),
                        )

                        xml_utils.set_attribute(
                            xml=_parent_schema_tree,
                            name="name",
                            value=child.attrib["name"],
                        )
                        parent_schema_tree = _parent_schema_tree

                xml_utils.append(parent=parent_schema_tree, child=child)

        # Delete augment stmt from tree
        for augment_stmt in sorted_augment_stmts:
            xml_utils.delete(xml=augment_stmt)

    @classmethod
    def _wrap_with_case_if_needed(
        cls,
        parent_schema_tree: typing.Any,
        yang_statement: typing.Any,
        namespace: str,
    ) -> typing.Any:
        if xml_utils.get_localname(parent_schema_tree) == "choice":
            new_parent_schema_tree = xml_utils.create_sub(
                parent=parent_schema_tree, tag="case", namespace=namespace
            )
            xml_utils.set_attribute(
                xml=new_parent_schema_tree,
                name="name",
                value=yang_statement.attrib["name"],
            )
            return new_parent_schema_tree
        else:
            return parent_schema_tree

    @classmethod
    def _get_module_namespace(
        cls,
        root_yang_module: typing.Any,
        yin_map: typing.Any,
    ) -> str:
        module_type = xml_utils.get_localname(root_yang_module)
        if module_type == "module":
            # module
            target_module = root_yang_module
        else:
            # submodule
            _parent_module_name = cls._get_parent_module_name(root_yang_module)
            target_module = yin_map[_parent_module_name]

        module_namespace: str = target_module.xpath("/module/namespace")[0].attrib[
            "uri"
        ]

        return module_namespace

    @classmethod
    def _get_parent_module_name(cls, root_yang_module: typing.Any) -> str:
        module_type = xml_utils.get_localname(root_yang_module)
        if module_type != "submodule":
            raise ValueError(
                "'{}' is not submodule".format(root_yang_module.attrib["name"])
            )

        parent_module_name: str = root_yang_module.xpath("./belongs-to")[0].attrib[
            "module"
        ]

        return parent_module_name

    @classmethod
    def _get_parent_module(
        cls,
        root_yang_module: typing.Any,
        yang_modules: typing.Any,
    ) -> typing.Any:
        parent_module_name = cls._get_parent_module_name(root_yang_module)
        return yang_modules[parent_module_name]

    @classmethod
    def _get_module_prefix(cls, root_yang_module: typing.Any) -> str:
        module_type = xml_utils.get_localname(root_yang_module)
        prefix: str
        if module_type == "module":
            prefix = root_yang_module.xpath("./prefix")[0].attrib["value"]
        else:
            prefix = root_yang_module.xpath("./belongs-to/prefix")[0].attrib["value"]

        return prefix

    @classmethod
    def _get_module_name_by_import_prefix(
        cls,
        root_yang_module: typing.Any,
        prefix: str,
    ) -> str:
        module_prefix = cls._get_module_prefix(root_yang_module)
        module_name: str
        if module_prefix == prefix:
            module_name = root_yang_module.attrib["name"]
            return module_name
        else:
            import_statement = root_yang_module.xpath(
                "./import[prefix[@value='{}']]".format(prefix)
            )[0]
            module_name = import_statement.attrib["module"]
            return module_name

    @classmethod
    def _get_namespace_by_import_prefix(
        cls,
        root_yang_module: typing.Any,
        prefix: str,
        yin_map: typing.Any,
    ) -> str:
        module_prefix = cls._get_module_prefix(root_yang_module)
        if module_prefix == prefix:
            yang_module = root_yang_module
        else:
            import_statement = root_yang_module.xpath(
                "./import[prefix[@value='{}']]".format(prefix)
            )[0]
            module_name = import_statement.attrib["module"]
            yang_module = yin_map[module_name]

        namespace = cls._get_module_namespace(
            root_yang_module=yang_module, yin_map=yin_map
        )
        return namespace

    @classmethod
    def _get_submodules(
        cls,
        root_yang_module: typing.Any,
        yin_map: typing.Any,
    ) -> typing.Any:
        include_stmts = root_yang_module.xpath("./include")
        submodule_names = [
            include_stmt.attrib["module"] for include_stmt in include_stmts
        ]

        submodules = []
        for submodule_name in submodule_names:
            submodule = yin_map[submodule_name]
            submodules.append(submodule)

        for submodule in submodules:
            subsubmodules = cls._get_submodules(
                root_yang_module=submodule, yin_map=yin_map
            )
            for subsubmodule in subsubmodules:
                if subsubmodule not in submodules:
                    submodules.append(subsubmodule)

        return submodules

    @classmethod
    def resolve_target_node(
        cls,
        target_node: str,
        default_namespace: str,
        root_yang_module: typing.Any,
        yin_map: typing.Any,
    ) -> str:
        """

        target_node (str):
            ex) /aaa/aaa, /ac:aaa/ac:aaa, ac:aaa/ac:aaa, aaa/aaa, ...
        """

        # format: {"{prefix}": "{namespace}", ...}
        prefix_namespace_map = {}

        default_prefix = cls._get_module_prefix(root_yang_module=root_yang_module)

        prefix_namespace_map[default_prefix] = default_namespace

        for import_stmt in root_yang_module.xpath("./import"):
            prefix = import_stmt.xpath("./prefix")[0].attrib["value"]

            module_name = import_stmt.attrib["module"]
            root_module = yin_map[module_name]
            namespace = cls._get_module_namespace(
                root_yang_module=root_module, yin_map=yin_map
            )

            prefix_namespace_map[prefix] = namespace

        segments = target_node.split("/")
        resolved_segments = []
        for segment in segments:
            if segment == "":
                resolved_segments.append("")
                continue

            results = segment.split(":")

            if len(results) == 1:
                namespace = default_namespace
                node_name = results[0]
            else:
                namespace = prefix_namespace_map[results[0]]
                node_name = results[1]

            resolved_segments.append("{{{}}}{}".format(namespace, node_name))

        resolved_target_node = "/".join(resolved_segments)

        return resolved_target_node


class YangTree(object):
    def __init__(self, xml: typing.Any) -> None:
        self._xml = xml

    def get_xml(self) -> typing.Any:
        return copy.deepcopy(self._xml)

    def get_root_node(self) -> YangNode:
        node = YangNode(xml=self._xml)
        return node

    def get_namespace(self, module_name: str) -> str:
        _results = self._xml.xpath("./module[@name='{}']".format(module_name))
        if len(_results) != 1:
            raise ValueError("Invalid module name: '{}'".format(module_name))
        module = _results[0]
        namespace: str = module.attrib["namespace"]
        return namespace

    def validate(self, config: typing.Any) -> None:
        def _validate(parent_config: typing.Any, parent_yang_node: typing.Any) -> None:
            for child_config in parent_config.xpath("./*"):
                name = xml_utils.get_localname(child_config)
                child_yang_node = parent_yang_node.get_child(name=name)
                _validate(parent_config=child_config, parent_yang_node=child_yang_node)

        _validate(parent_config=config, parent_yang_node=self.get_root_node())

    def set_node_type(self, root_config: typing.Any) -> typing.Any:
        def _set_node_type(
            parent_config: typing.Any, parent_yang_node: typing.Any
        ) -> None:
            for child_config in parent_config.xpath("./*"):
                name = xml_utils.get_localname(child_config)
                child_yang_node = parent_yang_node.get_child(name=name)
                child_config.attrib["node_type"] = child_yang_node.type
                _set_node_type(
                    parent_config=child_config, parent_yang_node=child_yang_node
                )

        _root_config = xml_utils.copy_xml(root_config)
        _set_node_type(parent_config=_root_config, parent_yang_node=self._xml)

        return _root_config


class YangNode(object):
    def __init__(self, xml: typing.Any, schema: typing.Any = None) -> None:
        self._xml = xml
        self._schema = schema

        name: typing.Optional[str]
        if schema is None:
            name = None
            module = None
            type = None
            namespace = None
        else:
            name = schema.attrib["name"]
            module = self._get_module(schema)
            type = xml_utils.get_localname(schema)
            namespace = xml_utils.get_namespace(self._schema)

        self._name = name
        self._module = module
        self._type = type
        self._namespace = namespace

    @property
    def name(self) -> typing.Optional[str]:
        return self._name

    @property
    def type(self) -> typing.Optional[str]:
        return self._type

    @property
    def namespace(self) -> typing.Optional[str]:
        return self._namespace

    def _get_module(self, schema: typing.Any) -> typing.Any:
        parent = schema.getparent()
        if parent is None:
            raise Error("root node")

        parent_2 = parent.getparent()
        if parent_2 is None:
            return schema

        return self._get_module(schema=parent)

    def get_path(self) -> str:
        if self._schema is None:
            return "/"

        nodes = [self]
        node = self
        while True:
            parent_node = node.get_parent()
            if parent_node is None:
                break
            node = parent_node
            nodes.insert(0, parent_node)

        path = "/" + "/".join([str(node.name) for node in nodes[1:]])
        return path

    def get(self, path: str) -> YangNode:
        if not path.startswith("/"):
            raise ValueError(f"Invalid path '{path}'")

        node = YangNode(xml=self._xml)

        if path != "/":
            names = path.lstrip("/").split("/")
            for name in names:
                node = node.get_child(name=name)

        return node

    def get_root(self) -> YangNode:
        node = self.get(path="/")
        return node

    def get_child(self, name: str, namespace: str = "*") -> YangNode:
        """Get child node (Container, List, leaf-list, leaf)

        node_name (str):
            node name

        namespace (str):
            not implemented
        """

        module, statement = self._get_child(
            module=self._module, schema=self._schema, name=name
        )
        if module is not None:
            node = YangNode(xml=self._xml, schema=statement)
            return node
        else:
            raise ValueError(
                f"YANG node '{name}' is not defined in '{self.get_path()}'"
            )

    def _get_child(
        self, module: typing.Any, schema: typing.Any, name: str
    ) -> typing.Any:
        # module
        if module is None:
            for candidate_tree in self._xml.xpath("./*"):
                found_module, found_xml = self._get_child(
                    module=candidate_tree,
                    schema=candidate_tree,
                    name=name,
                )
                if found_module is None:
                    continue

                return found_module, found_xml

            raise ValueError(f"No module supports '{name}'")

        # container, list, leaf-list, leaf
        for statement_type in ("container", "list", "leaf-list", "leaf"):
            _results = schema.xpath(
                f"./*[local-name()='{statement_type}' and @name='{name}']"
            )

            if len(_results) == 1:
                return module, _results[0]

        # choice
        for statement_type in ("container", "list", "leaf-list", "leaf"):
            _results = schema.xpath("./*[local-name()='choice']/*[local-name()='case']")
            for _result in _results:
                _module, _schema = self._get_child(
                    module=module,
                    schema=_result,
                    name=name,
                )
                if _module is None:
                    continue

                return _module, _schema

        return None, None

    def get_parent(self) -> typing.Optional[YangNode]:
        if self._schema is None:
            return None

        schema = self._schema
        while True:
            schema = schema.getparent()

            if xml_utils.get_localname(schema) == "module":
                parent_node = YangNode(xml=self._xml)
                return parent_node

            if xml_utils.get_localname(schema) not in ("choice", "case"):
                parent_node = YangNode(xml=self._xml, schema=schema)
                return parent_node

    def get_choice_ids(self) -> list[dict[str, str]]:
        if self._schema is None:
            return []

        choice_ids: list[dict[str, typing.Any]] = []
        schema = self._schema
        while True:
            schema = schema.getparent()
            if xml_utils.get_localname(schema) != "case":
                break

            case_namespace = xml_utils.get_namespace(schema)
            case_name = schema.attrib["name"]

            schema = schema.getparent()
            if xml_utils.get_localname(schema) != "choice":
                raise Error(f"FatalError: schema must be 'choice'")

            choice_namespace = xml_utils.get_namespace(schema)
            choice_name = schema.attrib["name"]

            choice_ids.append(
                {
                    "choice_namespace": choice_namespace,
                    "choice_name": choice_name,
                    "case_namespace": case_namespace,
                    "case_name": case_name,
                }
            )

        return choice_ids

    def get_keys(self) -> list[str]:
        if self._schema is None:
            raise Error(f"schema is empty.")

        if self._type != "list":
            raise Error(f"'{self._type}' does not have keys. Only list node has keys.")

        keys: list[str] = (
            self._schema.xpath("./*[local-name()='key']")[0].attrib["value"].split()
        )
        return keys


class Error(Exception):
    pass
