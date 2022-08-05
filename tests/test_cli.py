import sys
import pathlib
import datetime
import asyncio
import functools
import telnetlib
import asyncssh.connection

import pytest
import aiohttp
import pysnmp.hlapi
from qmonus_net_faker import __main__

from . import http_client


MAX_WAIT_TIME = 15


@pytest.mark.asyncio
async def test_initializes(project_path: pathlib.Path):
    init_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "qmonus_net_faker",
        "init",
        str(project_path),
    )
    await init_process.wait()
    assert init_process.returncode == 0


@pytest.mark.asyncio
async def test_builds(project_path: pathlib.Path):
    init_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "qmonus_net_faker",
        "init",
        str(project_path),
    )
    await init_process.wait()
    assert init_process.returncode == 0

    build_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "qmonus_net_faker",
        "build",
        str(project_path),
        "junos",
    )
    await build_process.wait()
    assert build_process.returncode == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {},
        {
            "--log-level": "debug",
            "--log-file-path": "log/manager.log",
            "--log-file-size": "1024",
            "--log-file-backup-count": "3",
            "--host": "127.0.0.2",
            "--port": "10081",
        },
    ],
)
async def test_runs_manager(
    options: dict, project_path: pathlib.Path, http_client: http_client.HttpClient
):
    if "--log-file-path" in options:
        options["--log-file-path"] = str(
            project_path.joinpath(options["--log-file-path"]).resolve()
        )

    _options: list = []
    for k, v in options.items():
        _options = _options + [k] + [v]

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-m",
            "qmonus_net_faker",
            "run",
            "manager",
            str(project_path),
            *_options,
        )

        expected_manager_endpoint = f"http://{options.get('--host', '127.0.0.1')}:{options.get('--port', 10080)}"
        expected_log_file_path = options.get("--log-file-path")

        expired_at = datetime.datetime.now() + datetime.timedelta(seconds=MAX_WAIT_TIME)
        while True:
            try:
                resp = await http_client.request(
                    method="GET", url=f"{expected_manager_endpoint}/stubs", timeout=3
                )
                assert resp.status == 200

                if expected_log_file_path:
                    assert pathlib.Path(expected_log_file_path).is_file()
            except Exception:
                if expired_at <= datetime.datetime.now():
                    raise
                await asyncio.sleep(1)
                continue
            break
    finally:
        if process:
            process.terminate()
            await process.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {},
        {
            "--log-level": "debug",
            "--log-file-path": "log/stub.log",
            "--log-file-size": "1024",
            "--log-file-backup-count": "3",
            "--host": "127.0.0.2",
            "--http-port": "30080",
            "--https-port": "30443",
            "--ssh-port": "30022",
            "--telnet-port": "30023",
            "--snmp-port": "30161",
            "--protocol": ["ssh", "http", "https", "telnet", "snmp"],
        },
    ],
)
async def test_runs_stub(
    options: dict, project_path: pathlib.Path, http_client: http_client.HttpClient
):
    if "--log-file-path" in options:
        options["--log-file-path"] = str(
            project_path.joinpath(options["--log-file-path"]).resolve()
        )

    _options: list = []
    for k, v in options.items():
        _options = _options + [k] + (v if isinstance(v, list) else [v])

    init_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "qmonus_net_faker",
        "init",
        str(project_path),
    )
    await init_process.wait()
    assert init_process.returncode == 0

    manager_process = None
    stub_process = None
    try:
        manager_process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-m",
            "qmonus_net_faker",
            "run",
            "manager",
            str(project_path),
        )
        stub_process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-m",
            "qmonus_net_faker",
            "run",
            "stub",
            "netfaker-stub-0",
            "http://127.0.0.1:10080",
            *_options,
        )

        expected_stub_host = options.get("--host", "127.0.0.1")
        expected_stub_ssh_port = int(options.get("--ssh-port", 20022))
        expected_stub_http_port = int(options.get("--http-port", 20080))
        expected_stub_https_port = int(options.get("--https-port", 20443))
        expected_stub_telnet_port = int(options.get("--telnet-port", 20023))
        expected_stub_snmp_port = int(options.get("--snmp-port", 20161))
        expected_log_file_path = options.get("--log-file-path")
        expected_protocols = options.get(
            "--protocol", ["ssh", "http", "https", "telnet", "snmp"]
        )

        expired_at = datetime.datetime.now() + datetime.timedelta(seconds=MAX_WAIT_TIME)
        while True:
            try:
                if "ssh" in expected_protocols:
                    async with asyncssh.connection.connect(
                        host=expected_stub_host,
                        port=expected_stub_ssh_port,
                        username="root",
                        password="",
                        client_keys=[],
                        passphrase=None,
                        known_hosts=None,
                    ) as conn:
                        process = await conn.create_process()
                        output = await asyncio.wait_for(
                            process.stdout.readuntil(">"), timeout=10
                        )
                        assert "JUNOS" in output

                if "http" in expected_protocols:
                    resp = await http_client.request(
                        method="GET",
                        url=f"http://{expected_stub_host}:{expected_stub_http_port}/dummy",
                        timeout=3,
                    )
                    assert resp.status == 200

                if "https" in expected_protocols:
                    resp = await http_client.request(
                        method="GET",
                        url=f"https://{expected_stub_host}:{expected_stub_https_port}/dummy",
                        timeout=3,
                    )
                    assert resp.status == 200

                if "telnet" in expected_protocols:

                    def _telnet():
                        with telnetlib.Telnet(
                            host=expected_stub_host, port=expected_stub_telnet_port
                        ) as tn:
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

                    await asyncio.get_event_loop().run_in_executor(
                        None, functools.partial(_telnet)
                    )

                if "snmp" in expected_protocols:
                    results = pysnmp.hlapi.getCmd(
                        pysnmp.hlapi.SnmpEngine(),
                        pysnmp.hlapi.CommunityData("public"),
                        pysnmp.hlapi.UdpTransportTarget(
                            (expected_stub_host, expected_stub_snmp_port), retries=0
                        ),
                        pysnmp.hlapi.ContextData(),
                        pysnmp.hlapi.ObjectType(
                            pysnmp.hlapi.ObjectIdentity("1.3.6.1.2.1.2.2.1.1.1")
                        ),
                    )
                    (
                        error_indication,
                        error_status,
                        error_index,
                        variable_binddings,
                    ) = next(results)
                    assert error_indication is None
                    assert error_status == 0
                    assert error_index == 0
                    assert len(variable_binddings) == 1
                    assert variable_binddings[0][1] == 1

                if expected_log_file_path:
                    assert pathlib.Path(expected_log_file_path).is_file()
            except Exception:
                if expired_at <= datetime.datetime.now():
                    raise
                await asyncio.sleep(1)
                continue
            break
    finally:
        if manager_process:
            manager_process.terminate()
            await manager_process.wait()
        if stub_process:
            stub_process.terminate()
            await stub_process.wait()


@pytest.mark.asyncio
async def test_runs_all(
    project_path: pathlib.Path, http_client: http_client.HttpClient
):
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-m",
            "qmonus_net_faker",
            "--plugin-path",
            str(project_path),
        )

        expired_at = datetime.datetime.now() + datetime.timedelta(seconds=MAX_WAIT_TIME)
        while True:
            try:
                resp = await http_client.request(
                    method="GET", url="http://127.0.0.1:10080/stubs", timeout=3
                )
            except (asyncio.exceptions.TimeoutError, aiohttp.ClientConnectorError):
                if expired_at <= datetime.datetime.now():
                    raise
                await asyncio.sleep(1)
                continue
            assert resp.status == 200
            break
    finally:
        if process:
            process.terminate()
            await process.wait()
