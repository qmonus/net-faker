import typing
import pathlib
import asyncio
import functools
import dataclasses
import telnetlib
import asyncssh.connection

import pytest
import pytest_asyncio
from ncclient import manager
import pysnmp.hlapi
from qmonus_net_faker import action, server

from . import http_client


@dataclasses.dataclass
class ManagerInfo(object):
    host: str = "127.0.0.1"
    port: int = 10080

    @property
    def endpoint(self):
        return f"http://{self.host}:{self.port}"


@dataclasses.dataclass
class StubInfo(object):
    stub_id: str
    host: str
    ssh_port: int = 20022
    http_port: int = 20080
    https_port: int = 20443
    telnet_port: int = 20023
    snmp_port: int = 20161


MANAGER = ManagerInfo()
STUBS = [
    StubInfo(stub_id="netfaker-stub-0", host="127.0.0.1"),
    StubInfo(stub_id="netfaker-stub-1", host="127.0.0.2"),
    StubInfo(stub_id="netfaker-stub-2", host="127.0.0.3"),
]


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_function(project_path: pathlib.Path):
    await action.init(project_path=str(project_path))
    await action.build(project_path=str(project_path), yang_name="junos")
    manager = await server.create_manager(
        host=MANAGER.host, port=MANAGER.port, project_path=str(project_path)
    )

    stubs = []
    for STUB in STUBS:
        ssh_stub = await server.create_ssh_stub(
            host=STUB.host,
            port=STUB.ssh_port,
            stub_id=STUB.stub_id,
            manager_endpoint=MANAGER.endpoint,
        )
        stubs.append(ssh_stub)

        http_stub = await server.create_http_stub(
            host=STUB.host,
            port=STUB.http_port,
            stub_id=STUB.stub_id,
            manager_endpoint=MANAGER.endpoint,
        )
        stubs.append(http_stub)

        https_stub = await server.create_https_stub(
            host=STUB.host,
            port=STUB.https_port,
            stub_id=STUB.stub_id,
            manager_endpoint=MANAGER.endpoint,
        )
        stubs.append(https_stub)

        telnet_stub = await server.create_telnet_stub(
            host=STUB.host,
            port=STUB.telnet_port,
            stub_id=STUB.stub_id,
            manager_endpoint=MANAGER.endpoint,
        )
        stubs.append(telnet_stub)

        snmp_stub = await server.create_snmp_stub(
            host=STUB.host,
            port=STUB.snmp_port,
            stub_id=STUB.stub_id,
            manager_endpoint=MANAGER.endpoint,
        )
        stubs.append(snmp_stub)

    await manager.start()
    await asyncio.gather(*[stub.start() for stub in stubs])
    yield
    await manager.stop()
    await asyncio.gather(*[stub.stop() for stub in stubs])
    await asyncio.sleep(3)


@pytest.mark.asyncio
async def test_handles_netconf():
    def _test(STUB: StubInfo):
        with manager.connect(
            username="root",
            password="",
            host=STUB.host,
            port=STUB.ssh_port,
            hostkey_verify=False,
            device_params={"name": "junos"},
            allow_agent=False,
        ) as m:  # type: ignore
            resp = m.lock(target="candidate")

            resp = m.get_config(source="candidate")
            assert len(resp.xpath("./*[local-name()='data']")) == 1
            assert len(resp.xpath("./*[local-name()='data']/*")) == 0

            resp = m.edit_config(
                target="candidate",
                config="""
                <config>
                    <configuration xmlns="http://yang.juniper.net/junos/conf/root">
                        <interfaces xmlns="http://yang.juniper.net/junos/conf/interfaces">
                            <interface>
                                <name>xe-0/0/1</name>
                                <description>xe-0/0/1</description>
                                <vlan-tagging/>
                                <unit>
                                    <name>10</name>
                                    <description>10</description>
                                    <vlan-id>10</vlan-id>
                                    <family>
                                        <inet>
                                            <address>
                                                <name>10.0.0.1/24</name>
                                            </address>
                                            <address>
                                                <name>10.0.0.2/24</name>
                                            </address>
                                        </inet>
                                    </family>
                                </unit>
                            </interface>
                        </interfaces>
                        <policy-options xmlns="http://yang.juniper.net/junos/conf/policy-options">
                            <prefix-list>
                                <name>prefix-1</name>
                                <prefix-list-item>
                                    <name>10.0.0.0/24</name>
                                </prefix-list-item>
                                <prefix-list-item>
                                    <name>10.0.1.0/24</name>
                                </prefix-list-item>
                            </prefix-list>
                            <policy-statement>
                                <name>bgp</name>
                                <term>
                                    <name>10</name>
                                    <from>
                                        <protocol>bgp</protocol>
                                        <prefix-list-filter>
                                            <list_name>prefix-1</list_name>
                                            <choice-ident>orlonger</choice-ident>
                                            <choice-value/>
                                        </prefix-list-filter>
                                    </from>
                                    <then>
                                        <community>
                                            <choice-ident>add</choice-ident>
                                            <choice-value/>
                                            <community-name>community-1</community-name>
                                        </community>
                                        <reject/>
                                    </then>
                                </term>
                            </policy-statement>
                            <community>
                                <name>community-1</name>
                                <members>65000:1</members>
                                <members>65000:2</members>
                            </community>
                        </policy-options>
                    </configuration>
                </config>
            """,
            )

            resp = m.validate(source="candidate")
            resp = m.get_config(source="candidate")
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 1
            )

            resp = m.get()
            assert len(resp.xpath("./*[local-name()='data']/*")) == 0

            resp = m.commit()

            resp = m.unlock(target="candidate")

            resp = m.get_config(source="candidate")
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 1
            )

            resp = m.get()
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 1
            )

        with manager.connect(
            username="root",
            password="",
            host=STUB.host,
            port=STUB.ssh_port,
            hostkey_verify=False,
            device_params={"name": "junos"},
            allow_agent=False,
        ) as m:  # type: ignore
            resp = m.edit_config(
                target="candidate",
                config="""
                <config>
                    <configuration xmlns="http://yang.juniper.net/junos/conf/root">
                        <interfaces xmlns="http://yang.juniper.net/junos/conf/interfaces">
                            <interface>
                                <name>xe-0/0/1</name>
                                <flexible-vlan-tagging/>
                                <unit>
                                    <name>10</name>
                                    <description>10</description>
                                    <vlan-id>10</vlan-id>
                                    <family>
                                        <inet>
                                            <address operation='delete'>
                                                <name>10.0.0.1/24</name>
                                            </address>
                                        </inet>
                                    </family>
                                </unit>
                            </interface>
                        </interfaces>
                    </configuration>
                </config>
            """,
            )

            resp = m.get_config(source="candidate")
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='flexible-vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 0
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 0
            )

            resp = m.get()
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='flexible-vlan-tagging']"
                    )
                )
                == 0
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 1
            )

            resp = m.commit()

            resp = m.get_config(source="candidate")
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='flexible-vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 0
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 0
            )

            resp = m.get()
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='flexible-vlan-tagging']"
                    )
                )
                == 1
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='vlan-tagging']"
                    )
                )
                == 0
            )
            assert (
                len(
                    resp.xpath(
                        "."
                        "/*[local-name()='data']"
                        "/*[local-name()='configuration']"
                        "/*[local-name()='interfaces']"
                        "/*[local-name()='interface']"
                        "/*[local-name()='unit']"
                        "/*[local-name()='family']"
                        "/*[local-name()='inet']"
                        "/*[local-name()='address']"
                        "/*[local-name()='name' and text()='10.0.0.1/24']"
                    )
                )
                == 0
            )

    for STUB in STUBS:
        await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(_test, STUB=STUB)
        )


@pytest.mark.asyncio
async def test_handles_http(http_client: http_client.HttpClient):
    for STUB in STUBS:
        resp = await http_client.request(
            method="GET", url=f"http://{STUB.host}:{STUB.http_port}"
        )
        assert resp.status == 200


@pytest.mark.asyncio
async def test_handles_https(http_client: http_client.HttpClient):
    for STUB in STUBS:
        resp = await http_client.request(
            method="GET", url=f"https://{STUB.host}:{STUB.https_port}"
        )
        assert resp.status == 200


@pytest.mark.asyncio
async def test_handles_ssh():
    for STUB in STUBS:
        async with asyncssh.connection.connect(
            host=STUB.host,
            port=STUB.ssh_port,
            username="root",
            password="",
            client_keys=[],
            passphrase=None,
            known_hosts=None,
        ) as conn:
            process = await conn.create_process()
            output = await asyncio.wait_for(process.stdout.readuntil(">"), timeout=10)
            assert "JUNOS" in output

            process.stdin.write("\n")
            output = await asyncio.wait_for(process.stdout.readuntil(">"), timeout=10)
            assert "root" in output

            process.stdin.write("set cli screen-length 0\n")
            output = await asyncio.wait_for(process.stdout.readuntil(">"), timeout=10)
            assert "Screen length set to 0" in output


@pytest.mark.asyncio
async def test_handles_telnet():
    def _test(STUB: StubInfo):
        with telnetlib.Telnet(host=STUB.host, port=STUB.telnet_port) as tn:
            output = tn.read_until(b"login: ", timeout=5)
            assert b"login: " in output
            tn.write(b"root\n")

            output = tn.read_until(b"Password: ", timeout=5)
            assert b"Password: " in output
            tn.write(b"\n")

            output = tn.read_until(b"> ", timeout=5)
            assert b"root" in output
            tn.write(b"\n")

            output = tn.read_until(b"> ", timeout=5)
            assert b"root" in output

    for STUB in STUBS:
        await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(_test, STUB=STUB)
        )


@pytest.mark.asyncio
async def test_handles_snmp():
    def _test(STUB: StubInfo):
        # Get
        results = pysnmp.hlapi.getCmd(
            pysnmp.hlapi.SnmpEngine(),
            pysnmp.hlapi.CommunityData("public"),
            pysnmp.hlapi.UdpTransportTarget((STUB.host, STUB.snmp_port), retries=0),
            pysnmp.hlapi.ContextData(),
            pysnmp.hlapi.ObjectType(
                pysnmp.hlapi.ObjectIdentity("1.3.6.1.2.1.2.2.1.1.1")
            ),
        )
        error_indication, error_status, error_index, variable_binddings = next(results)
        assert error_indication is None
        assert error_status == 0
        assert error_index == 0
        assert len(variable_binddings) == 1
        assert variable_binddings[0][1] == 1

        # GetNext
        results = pysnmp.hlapi.nextCmd(
            pysnmp.hlapi.SnmpEngine(),
            pysnmp.hlapi.CommunityData("public"),
            pysnmp.hlapi.UdpTransportTarget((STUB.host, STUB.snmp_port), retries=0),
            pysnmp.hlapi.ContextData(),
            pysnmp.hlapi.ObjectType(
                pysnmp.hlapi.ObjectIdentity("1.3.6.1.2.1.2.2.1.1.1")
            ),
        )
        error_indication, error_status, error_index, variable_binddings = next(results)
        assert error_indication is None
        assert error_status == 0
        assert error_index == 0
        assert len(variable_binddings) == 1  # type: ignore
        assert variable_binddings[0][1] == 2

        # GetBulk
        results = pysnmp.hlapi.bulkCmd(
            pysnmp.hlapi.SnmpEngine(),
            pysnmp.hlapi.CommunityData("public"),
            pysnmp.hlapi.UdpTransportTarget((STUB.host, STUB.snmp_port), retries=0),
            pysnmp.hlapi.ContextData(),
            1,
            2,
            pysnmp.hlapi.ObjectType(
                pysnmp.hlapi.ObjectIdentity("1.3.6.1.2.1.2.2.1.1.1")
            ),
            pysnmp.hlapi.ObjectType(
                pysnmp.hlapi.ObjectIdentity("1.3.6.1.2.1.2.2.1.2.1")
            ),
        )
        error_indication, error_status, error_index, variable_binddings = next(results)
        assert error_indication is None
        assert error_status == 0
        assert error_index == 0
        assert len(variable_binddings) == 2
        assert variable_binddings[0][1] == 2
        assert str(variable_binddings[1][1]) == "xe-0/0/0"

        error_indication, error_status, error_index, variable_binddings = next(results)
        assert error_indication is None
        assert error_status == 0
        assert error_index == 0
        assert len(variable_binddings) == 2
        assert variable_binddings[0][1] == 2
        assert str(variable_binddings[1][1]) == "xe-0/0/1"

    for STUB in STUBS:
        await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(_test, STUB=STUB)
        )
