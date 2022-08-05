import logging
import typing
import pathlib
import signal
import asyncio

from . import exceptions
from . import server
from .interface import (
    cli_interface,
    manager_interface,
    http_stub_interface,
    ssh_stub_interface,
    telnet_stub_interface,
    snmp_stub_interface,
)
from .application import manager_application, cli_application
from .infrastructure import (
    file_infrastructure,
)

logger = logging.getLogger(__name__)


async def init(project_path: str) -> None:
    _project_path = pathlib.Path(project_path).resolve()
    if not _project_path.is_dir():
        raise exceptions.Error(f"Specified directory '{project_path}' does not exist.")

    # Setup repositories
    file_repo = file_infrastructure.Repository(dir_path=_project_path)

    # Setup application
    cli_app = cli_application.App(file_repo=file_repo)

    # Setup interface
    interface = cli_interface.Interface(cli_app=cli_app)

    # Start
    await interface.init()


async def build(project_path: str, yang_name: str) -> None:
    _project_path = pathlib.Path(project_path).resolve()
    if not _project_path.is_dir():
        raise exceptions.Error(f"Specified directory '{project_path}' does not exist.")

    # Setup repositories
    file_repo = file_infrastructure.Repository(dir_path=_project_path)

    # Setup application
    cli_app = cli_application.App(file_repo=file_repo)

    # Setup interface
    interface = cli_interface.Interface(cli_app=cli_app)

    # Start
    await interface.build(yang_name=yang_name)


def handle_signal() -> None:
    raise SystemExit(0)


async def run_manager(
    host: str,
    port: int,
    project_path: str,
) -> None:
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(sig=signal.SIGTERM, callback=handle_signal)
        loop.add_signal_handler(sig=signal.SIGINT, callback=handle_signal)
    except NotImplementedError:
        logger.info(f"Signal not implemented.")

    manager = await server.create_manager(
        host=host, port=port, project_path=project_path
    )
    try:
        await manager.start()
        while True:
            await asyncio.sleep(3600)
    finally:
        await manager.stop()


async def run_stub(
    stub_id: str,
    manager_endpoint: str,
    host: str,
    http_port: int,
    https_port: int,
    ssh_port: int,
    telnet_port: int,
    snmp_port: int,
    protocols: list[typing.Literal["ssh", "http", "https", "telnet", "snmp"]],
) -> None:
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(sig=signal.SIGTERM, callback=handle_signal)
        loop.add_signal_handler(sig=signal.SIGINT, callback=handle_signal)
    except NotImplementedError:
        logger.info(f"Signal not implemented.")

    stubs: typing.List[
        typing.Union[
            ssh_stub_interface.Server,
            http_stub_interface.Server,
            telnet_stub_interface.Server,
            snmp_stub_interface.Server,
        ]
    ] = []
    if "ssh" in protocols:
        ssh_stub = await server.create_ssh_stub(
            host=host,
            port=ssh_port,
            stub_id=stub_id,
            manager_endpoint=manager_endpoint,
        )
        stubs.append(ssh_stub)
    if "http" in protocols:
        http_stub = await server.create_http_stub(
            host=host,
            port=http_port,
            stub_id=stub_id,
            manager_endpoint=manager_endpoint,
        )
        stubs.append(http_stub)
    if "https" in protocols:
        https_stub = await server.create_https_stub(
            host=host,
            port=https_port,
            stub_id=stub_id,
            manager_endpoint=manager_endpoint,
        )
        stubs.append(https_stub)
    if "telnet" in protocols:
        telnet_stub = await server.create_telnet_stub(
            host=host,
            port=telnet_port,
            stub_id=stub_id,
            manager_endpoint=manager_endpoint,
        )
        stubs.append(telnet_stub)
    if "snmp" in protocols:
        snmp_stub = await server.create_snmp_stub(
            host=host,
            port=snmp_port,
            stub_id=stub_id,
            manager_endpoint=manager_endpoint,
        )
        stubs.append(snmp_stub)

    try:
        await asyncio.gather(*[stub.start() for stub in stubs])
        while True:
            await asyncio.sleep(3600)
    finally:
        await asyncio.gather(*[stub.stop() for stub in stubs])
