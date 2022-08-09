from __future__ import annotations
import typing
import re
import json

import multidict

from . import exceptions
from ..libs import str_utils, xml_utils, netconf
from ..domain import (
    file_domain,
    stub_domain,
    netconf_service_domain,
    snmp_service_domain,
)


class Handler(object):
    async def netconf_hello_message(self, ctx: Context) -> Response:
        raise NotImplementedError("'get_netconf_hello_message' is not implemented.")

    async def handle_netconf(self, ctx: Context) -> Response:
        raise NotImplementedError("'handle_netconf' is not implemented.")

    async def handle_http(self, ctx: Context) -> Response:
        raise NotImplementedError("'handle_http' is not implemented.")

    async def ssh_login_message(self, ctx: Context) -> Response:
        raise NotImplementedError("'get_ssh_login_message' is not implemented.")

    async def handle_ssh(self, ctx: Context) -> Response:
        raise NotImplementedError("'handle_ssh' is not implemented.")

    async def telnet_login_message(self, ctx: Context) -> Response:
        raise NotImplementedError("'get_telnet_login_message' is not implemented.")

    async def handle_telnet(self, ctx: Context) -> Response:
        raise NotImplementedError("'handle_telnet' is not implemented.")

    async def handle_snmp(self, ctx: Context) -> Response:
        raise NotImplementedError("'handle_snmp' is not implemented.")


class Request(object):
    def __init__(
        self,
        scheme: str,
        method: str,
        url: str,
        path: str,
        query: dict[str, list[str]],
        headers: multidict.CIMultiDictProxy[str],
        body: str,
        stub_id: str,
    ) -> None:
        self.scheme = scheme
        self.method = method
        self.url = url
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body
        self.stub_id = stub_id
        self.http: HttpRequest
        self.netconf: NetconfRequest
        self.ssh: SSHRequest
        self.telnet: TelnetRequest
        self.snmp: SNMPRequest

        json_body = json.loads(body)
        protocol = json_body["protocol"]
        if protocol in ["http", "https"]:
            self.http = HttpRequest(
                scheme=json_body["protocol"],
                method=json_body["method"],
                path=json_body["path"],
                query=json_body["query"],
                headers=multidict.CIMultiDict(json_body["headers"]),
                body=json_body["body"],
            )
        elif protocol == "netconf":
            if json_body["connectionStatus"] == "login":
                rpc_xml = xml_utils.from_string("<rpc/>", ignore_namespace=False)
                protocol_operation = ""
                message_id = ""
            else:
                rpc_xml = xml_utils.from_string(
                    json_body["rpc"], ignore_namespace=False
                )
                protocol_operation = netconf.Netconf.get_protocol_operation(rpc_xml)
                message_id = netconf.Netconf.get_message_id(rpc=rpc_xml)

            self.netconf = NetconfRequest(
                connection_status=json_body["connectionStatus"],
                username=json_body["username"],
                session_id=json_body["sessionId"],
                rpc=rpc_xml,
                protocol_operation=protocol_operation,
                message_id=message_id,
            )
        elif protocol == "ssh":
            self.ssh = SSHRequest(
                connection_status=json_body["connectionStatus"],
                username=json_body["username"],
                session_id=json_body["sessionId"],
                input=json_body["input"],
                prompt=json_body["prompt"],
                state=json_body["state"],
            )
        elif protocol == "telnet":
            self.telnet = TelnetRequest(
                connection_status=json_body["connectionStatus"],
                session_id=json_body["sessionId"],
                input=json_body["input"],
                prompt=json_body["prompt"],
                state=json_body["state"],
            )
        elif protocol == "snmp":
            self.snmp = SNMPRequest(
                pdu_type=json_body["pduType"],
                version=json_body["version"],
                request_id=json_body["requestId"],
                community=json_body["community"],
                objects=json_body["objects"],
                non_repeaters=json_body["non_repeaters"],
                max_repetitions=json_body["max_repetitions"],
            )
        else:
            raise exceptions.FatalError(f"Invalid request")

    def to_dict(self) -> dict[str, typing.Any]:
        return {
            "scheme": self.scheme,
            "method": self.method,
            "url": self.url,
            "path": self.path,
            "query": self.query,
            "headers": dict(self.headers),
            "body": self.body,
        }

    def match_path(self, path: str) -> typing.Optional[re.Match[str]]:
        regex = r"\A" + re.sub(r"{([a-zA-Z0-9_]+?)}", r"(?P<\1>[^/]+)", path) + r"\Z"
        m = re.match(regex, self.path)
        return m


class HttpRequest(object):
    def __init__(
        self,
        scheme: str,
        method: str,
        path: str,
        query: dict[str, list[str]],
        headers: multidict.CIMultiDict[str],
        body: str,
    ) -> None:
        self.scheme = scheme
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def create_json_response(
        self,
        code: int,
        headers: typing.Union[
            typing.Dict[str, str], multidict.CIMultiDict[str], None
        ] = None,
        body: typing.Union[dict[typing.Any, typing.Any], list[typing.Any], None] = None,
    ) -> Response:
        _headers: multidict.CIMultiDict[str]
        if headers is None:
            _headers = multidict.CIMultiDict()
        else:
            _headers = multidict.CIMultiDict(headers)
        _headers["content-type"] = "application/json"

        res_body = json.dumps(
            {
                "code": code,
                "headers": dict(_headers),
                "body": None if body is None else json.dumps(body),
            }
        )

        response = Response(
            code=200,
            headers=multidict.CIMultiDict({"content-type": "application/json"}),
            body=res_body,
        )
        return response

    def create_xml_response(
        self,
        code: int,
        headers: typing.Union[dict[str, str], multidict.CIMultiDict[str], None] = None,
        body: typing.Any = None,
    ) -> Response:
        _headers: multidict.CIMultiDict[str]
        if headers is None:
            _headers = multidict.CIMultiDict()
        else:
            _headers = multidict.CIMultiDict(headers)
        _headers["content-type"] = "application/xml"

        res_body = json.dumps(
            {
                "code": code,
                "headers": dict(_headers),
                "body": body
                if (body is None or isinstance(body, str))
                else xml_utils.to_string(body),
            }
        )

        response = Response(
            code=200,
            headers=multidict.CIMultiDict({"content-type": "application/json"}),
            body=res_body,
        )
        return response

    def create_response(
        self,
        code: int,
        headers: typing.Union[dict[str, str], multidict.CIMultiDict[str], None] = None,
        body: typing.Optional[str] = None,
    ) -> Response:
        res_body = json.dumps(
            {
                "code": code,
                "headers": {} if headers is None else dict(headers),
                "body": body,
            }
        )

        response = Response(
            code=200,
            headers=multidict.CIMultiDict({"content-type": "application/json"}),
            body=res_body,
        )
        return response


class NetconfRequest(object):
    def __init__(
        self,
        connection_status: typing.Literal["login", "established"],
        username: str,
        session_id: int,
        rpc: typing.Any,  # lxml.etree._Element
        protocol_operation: str,
        message_id: str,
    ) -> None:
        self.connection_status: typing.Literal[
            "login", "established"
        ] = connection_status
        self.username = username
        self.session_id = session_id
        self.protocol_operation = protocol_operation
        self.rpc = rpc  # lxml.etree._Element
        self.message_id = message_id

    def create_response(self, xml: typing.Any) -> Response:
        headers: multidict.CIMultiDict[str] = multidict.CIMultiDict()
        headers["content-type"] = "application/xml"

        if isinstance(xml, str):
            body = xml
        else:
            body = xml_utils.to_string(xml)

        response = Response(code=200, headers=headers, body=body)
        return response

    def create_hello_message(
        self,
        capabilities: typing.Optional[typing.List[str]] = None,
    ) -> Response:
        if capabilities is None:
            capabilities = [
                "urn:ietf:params:netconf:base:1.0",
                "urn:ietf:params:netconf:capability:writable-running:1.0",
                "urn:ietf:params:netconf:capability:candidate:1.0",
                "urn:ietf:params:netconf:capability:xpath:1.0",
                "urn:ietf:params:netconf:capability:validate:1.0",
                "urn:ietf:params:netconf:capability:validate:1.1",
                "urn:ietf:params:netconf:capability:rollback-on-error:1.0",
                "urn:ietf:params:netconf:capability:notification:1.0",
                "urn:ietf:params:netconf:capability:interleave:1.0",
            ]

        variables = {
            "session_id": self.session_id,
            "capabilities": capabilities,
        }
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
        hello = str_utils.render(template=template, variables=variables)

        headers: multidict.CIMultiDict[str] = multidict.CIMultiDict()
        headers["content-type"] = "application/xml"
        response = Response(code=200, headers=headers, body=hello)
        return response


class SSHRequest(object):
    def __init__(
        self,
        connection_status: typing.Literal["login", "established"],
        username: str,
        session_id: str,
        input: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
    ) -> None:
        self.connection_status: typing.Literal[
            "login", "established"
        ] = connection_status
        self.username = username
        self.session_id = session_id
        self.input = input
        self.prompt = prompt
        self.state = state

    def create_response(
        self,
        output: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
    ) -> Response:
        body = {
            "output": output,
            "prompt": prompt,
            "state": state,
        }
        headers: multidict.CIMultiDict[str] = multidict.CIMultiDict()
        headers["content-type"] = "application/json"
        response = Response(code=200, headers=headers, body=json.dumps(body))
        return response


class TelnetRequest(object):
    def __init__(
        self,
        connection_status: typing.Literal["login", "established"],
        session_id: str,
        input: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
    ) -> None:
        self.connection_status: typing.Literal[
            "login", "established"
        ] = connection_status
        self.session_id = session_id
        self.input = input
        self.prompt = prompt
        self.state = state

    def create_response(
        self,
        output: str,
        prompt: str,
        state: dict[typing.Any, typing.Any],
    ) -> Response:
        body = {
            "output": output,
            "prompt": prompt,
            "state": state,
        }
        headers: multidict.CIMultiDict[str] = multidict.CIMultiDict()
        headers["content-type"] = "application/json"
        response = Response(code=200, headers=headers, body=json.dumps(body))
        return response


class SNMPRequest(object):
    def __init__(
        self,
        pdu_type: typing.Literal["GET", "GET_NEXT", "GET_BULK"],
        version: typing.Literal["v1", "v2c"],
        request_id: int,
        community: str,
        objects: list[dict[str, typing.Any]],
        non_repeaters: int,
        max_repetitions: int,
    ) -> None:
        self.pdu_type: typing.Literal["GET", "GET_NEXT", "GET_BULK"] = pdu_type
        self.version: typing.Literal["v1", "v2c"] = version
        self.request_id = request_id
        self.community = community
        self.objects = objects
        self.non_repeaters = non_repeaters
        self.max_repetitions = max_repetitions

    def create_response(self, objects: list[dict[str, typing.Any]]) -> Response:
        body = {"objects": objects}
        headers: multidict.CIMultiDict[str] = multidict.CIMultiDict()
        headers["content-type"] = "application/json"
        response = Response(code=200, headers=headers, body=json.dumps(body))
        return response


class Response(object):
    def __init__(
        self,
        code: int,
        headers: multidict.CIMultiDict[str],
        body: typing.Optional[str],
    ) -> None:
        self.code = code
        self.headers = headers
        self.body = body

    def to_dict(self) -> dict[str, typing.Any]:
        return {
            "code": self.code,
            "headers": dict(self.headers),
            "body": self.body,
        }


class Context(object):
    def __init__(
        self,
        request: Request,
        stub: stub_domain.Entity,
        file_repo: file_domain.Repository,
        stub_repo: stub_domain.Repository,
        netconf_service: netconf_service_domain.NetconfService,
        snmp_service: snmp_service_domain.SNMPService,
    ) -> None:
        self.request = request
        self.stub = stub
        self.file_repo = file_repo
        self.stub_repo = stub_repo
        self.netconf_service = netconf_service
        self.snmp_service = snmp_service
