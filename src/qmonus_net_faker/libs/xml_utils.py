import typing
import copy

from lxml import etree, objectify


def from_file(filename: str, ignore_namespace: bool = False) -> typing.Any:
    parser = etree.XMLParser(
        remove_blank_text=True, ns_clean=False, recover=False, encoding="utf-8"
    )
    xml = etree.parse(filename, parser=parser)
    if ignore_namespace is True:
        delete_namespace(xml)
    return xml


def from_string(string: str, ignore_namespace: bool = False) -> typing.Any:
    byte_string = string.lstrip().encode("utf-8")
    parser = etree.XMLParser(
        remove_blank_text=True,
        ns_clean=False,
        recover=False,
        encoding="utf-8",
    )
    xml = etree.fromstring(byte_string, parser=parser)
    if ignore_namespace is True:
        delete_namespace(xml)
    return xml


def to_string(xml: typing.Any, pretty_print: bool = True) -> str:
    return etree.tostring(xml, encoding="unicode", pretty_print=pretty_print)  # type: ignore


def is_element(xml: typing.Any) -> bool:
    result: bool = etree.iselement(xml)
    return result


def delete_namespace(xml: typing.Any, backup_attr: typing.Optional[str] = None) -> None:
    for el in xml.iter():
        if isinstance(el.tag, str):
            namespace = get_namespace(el)
            localname = get_localname(el)
            el.tag = localname
            if backup_attr is not None and namespace is not None:
                el.attrib[backup_attr] = namespace

    # Delete unused namespace
    deannotate(xml)


def revert_namespace(xml: typing.Any, backup_attr: str) -> None:
    for el in xml.iter():
        if isinstance(el.tag, str):
            if backup_attr not in el.attrib:
                continue
            namespace = el.attrib[backup_attr]
            localname = get_localname(el)
            el.tag = "{" + namespace + "}" + localname
            del el.attrib[backup_attr]

    # Delete unused namespace
    deannotate(xml)


def update_namespace(xml: typing.Any, namespace: str, recursive: bool = False) -> None:
    localname = get_localname(xml)
    xml.tag = "{" + namespace + "}" + localname

    if recursive is True:
        for el in xml.xpath(".//*"):
            if isinstance(el.tag, str):
                localname = get_localname(el)
                el.tag = "{" + namespace + "}" + localname

    # Delete unused namespace
    deannotate(xml)


def replace_namespace(
    xml: typing.Any,
    src: typing.Optional[str],
    dst: str,
    recursive: bool = False,
) -> None:
    def _replace(_xml: typing.Any) -> None:
        namespace = get_namespace(_xml)
        if namespace == src:
            localname = get_localname(_xml)
            _xml.tag = "{" + dst + "}" + localname

    _replace(xml)

    if recursive is True:
        for el in xml.xpath(".//*"):
            if isinstance(el.tag, str):
                _replace(el)

    # Delete unused namespace
    deannotate(xml)


def deannotate(xml: typing.Any) -> None:
    # Delete unused namespace
    objectify.deannotate(xml, cleanup_namespaces=True)  # type: ignore


def set_attribute(
    xml: typing.Any, name: str, value: str, recursive: bool = False
) -> None:
    xml.attrib[name] = value
    if recursive is True:
        for child in xml.xpath(".//*"):
            child.attrib[name] = value


def delete_attribute(xml: typing.Any, name: str, recursive: bool = False) -> None:
    if name in xml.attrib:
        del xml.attrib[name]

    if recursive is True:
        etree.strip_attributes(xml, name)
        # for child in xml.xpath(".//*[@{}]".format(name)):
        #     del child.attrib[name]


def create(tag: str, namespace: typing.Optional[str] = None) -> typing.Any:
    if namespace:
        namespace_str = "{" + namespace + "}"
    else:
        namespace_str = ""
    element = etree.Element(namespace_str + tag)  # type: ignore
    return element


def create_sub(
    parent: typing.Any, tag: str, namespace: typing.Optional[str] = None
) -> typing.Any:
    if namespace:
        namespace_str = "{" + namespace + "}"
    else:
        namespace_str = ""
    sub_element = etree.SubElement(parent, namespace_str + tag)  # type: ignore
    return sub_element


def append(parent: typing.Any, child: typing.Any) -> None:
    parent.append(child)


def delete(xml: typing.Any) -> None:
    xml.getparent().remove(xml)


def get_localname(xml: typing.Any) -> str:
    localname: str = etree.QName(xml).localname
    return localname


def get_namespace(xml: typing.Any) -> typing.Optional[str]:
    namespace: typing.Optional[str] = etree.QName(xml).namespace
    return namespace


def copy_xml(xml: typing.Any) -> typing.Any:
    new = copy.deepcopy(xml)
    return new


def get_path(xml: typing.Any) -> str:
    root_tree = xml.getroottree()
    root = root_tree.getroot()
    root_local_name = get_localname(root)
    root_namespace = get_namespace(root)
    if root_namespace is None:
        root_path = root_local_name
    else:
        root_path = "{" + root_namespace + "}" + root_local_name

    partial_path = path = root_tree.getelementpath(xml)
    full_path = "/{}/{}".format(root_path, partial_path)
    return full_path


def get_parents(xml: typing.Any) -> typing.Any:
    parents = []
    _xml = xml
    while True:
        _xml = _xml.getparent()
        if _xml is None:
            break

        parents.append(_xml)

    return parents


def equals(xml_a: typing.Any, xml_b: typing.Any) -> bool:
    xml_a_str = to_string(xml_a, pretty_print=False)
    xml_b_str = to_string(xml_b, pretty_print=False)
    return xml_a_str == xml_b_str
