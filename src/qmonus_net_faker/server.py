import logging
import pathlib
import sys

from .interface import (
    manager_interface,
    http_stub_interface,
    ssh_stub_interface,
    telnet_stub_interface,
    snmp_stub_interface,
)
from .application import manager_application
from .infrastructure import (
    file_infrastructure,
    stub_infrastructure,
    yang_tree_infrastructure,
)

logger = logging.getLogger(__name__)


async def create_manager(
    host: str,
    port: int,
    project_path: str,
) -> manager_interface.Server:
    # Setup project directory
    _project_path = pathlib.Path(project_path).resolve()
    if not _project_path.is_dir():
        logger.warning(f"Specified directory '{project_path}' does not exist.")

    sys.path.append(str(_project_path))

    # Setup repositories
    file_repo = file_infrastructure.Repository(dir_path=_project_path)
    stub_repo = stub_infrastructure.Repository()
    yang_tree_repo = yang_tree_infrastructure.Repository()

    # Setup applications
    manager_app = manager_application.App(
        file_repo=file_repo,
        stub_repo=stub_repo,
        yang_tree_repo=yang_tree_repo,
        project_path=_project_path,
    )
    await manager_app.reload_stubs()
    await manager_app.reload_yangs()

    # Setup interface
    _server = manager_interface.Server(
        host=host,
        port=port,
        manager_app=manager_app,
    )

    return _server


async def create_http_stub(
    host: str, port: int, stub_id: str, manager_endpoint: str
) -> http_stub_interface.Server:
    _server = http_stub_interface.Server(
        host=host,
        port=port,
        stub_id=stub_id,
        manager_endpoint=manager_endpoint,
        ssl=False,
    )
    return _server


async def create_https_stub(
    host: str, port: int, stub_id: str, manager_endpoint: str
) -> http_stub_interface.Server:
    _server = http_stub_interface.Server(
        host=host,
        port=port,
        stub_id=stub_id,
        manager_endpoint=manager_endpoint,
        ssl=True,
    )
    return _server


async def create_ssh_stub(
    host: str, port: int, stub_id: str, manager_endpoint: str
) -> ssh_stub_interface.Server:
    _server = ssh_stub_interface.Server(
        host=host,
        port=port,
        stub_id=stub_id,
        manager_endpoint=manager_endpoint,
    )
    return _server


async def create_telnet_stub(
    host: str, port: int, stub_id: str, manager_endpoint: str
) -> telnet_stub_interface.Server:
    _server = telnet_stub_interface.Server(
        host=host,
        port=port,
        stub_id=stub_id,
        manager_endpoint=manager_endpoint,
    )
    return _server


async def create_snmp_stub(
    host: str, port: int, stub_id: str, manager_endpoint: str
) -> snmp_stub_interface.Server:
    _server = snmp_stub_interface.Server(
        host=host,
        port=port,
        stub_id=stub_id,
        manager_endpoint=manager_endpoint,
    )
    return _server
