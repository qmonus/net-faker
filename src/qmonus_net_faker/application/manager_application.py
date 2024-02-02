from __future__ import annotations
import logging
import typing
import json
import re
import pathlib

import yaml

from . import plugin, exceptions
from ..libs import (
    module_utils,
    file_lib,
    xml_utils,
    yang,
)
from ..domain import (
    file_domain,
    stub_domain,
    yang_tree_domain,
    netconf_service_domain,
    snmp_service_domain,
)

logger = logging.getLogger(__name__)


class App(object):
    def __init__(
        self,
        file_repo: file_domain.Repository,
        stub_repo: stub_domain.Repository,
        yang_tree_repo: yang_tree_domain.Repository,
        project_path: pathlib.Path,
    ) -> None:
        self._file_repo = file_repo
        self._stub_repo = stub_repo
        self._yang_tree_repo = yang_tree_repo
        self._project_path = project_path

        _module_path = self._project_path.joinpath("module")
        self._module_dir_checker = file_lib.DirChecker(path=_module_path)

        _yang_path = self._project_path.joinpath("yangs")
        self._yangs_dir_checker = file_lib.DirChecker(
            path=_yang_path,
            glob_pattern="*/yang_tree/yang_tree_0.part",
        )

    async def create_stub(
        self,
        id: str,
        description: str,
        handler: str,
        yang: str,
        enabled: bool,
        metadata: dict[typing.Any, typing.Any],
    ) -> stub_domain.Entity:
        result = await self._stub_repo.get(id=stub_domain.Id(value=id))
        if result:
            raise exceptions.ConflictError(f"stub '{id}' already exists.")

        # Create
        stub = stub_domain.Entity(
            id=stub_domain.Id(value=id),
            description=stub_domain.Description(value=description),
            handler=stub_domain.Handler(value=handler),
            yang=yang_tree_domain.Id(value=yang),
            enabled=stub_domain.Enabled(value=enabled),
        )
        stub.set_metadata(value=metadata)

        await self._stub_repo.add(stub)
        return stub

    async def list_stubs(
        self,
        id: typing.Union[str, typing.List[str], None] = None,
    ) -> list[stub_domain.Entity]:
        if id is None:
            ids = None
        else:
            ids = [
                stub_domain.Id(value=i) for i in (id if isinstance(id, list) else [id])
            ]

        # List
        stubs = await self._stub_repo.list(id=ids)
        return stubs

    async def get_stub(self, id: str) -> stub_domain.Entity:
        # Get
        stub = await self._stub_repo.get(id=stub_domain.Id(value=id))
        if not stub:
            raise exceptions.NotFoundError(f"stub '{id}' does not exist.")
        return stub

    async def update_stub(
        self,
        id: str,
        description: typing.Optional[str] = None,
        handler: typing.Optional[str] = None,
        yang: typing.Optional[str] = None,
        enabled: typing.Optional[bool] = None,
        metadata: typing.Optional[dict[typing.Any, typing.Any]] = None,
    ) -> stub_domain.Entity:
        stub = await self._stub_repo.get(id=stub_domain.Id(value=id))
        if not stub:
            raise exceptions.NotFoundError(f"stub '{id}' does not exist.")

        # Update
        if description is not None:
            stub.description = stub_domain.Description(value=description)
        if handler is not None:
            stub.handler = stub_domain.Handler(value=handler)
        if yang is not None:
            stub.yang = yang_tree_domain.Id(value=yang)
        if enabled is not None:
            stub.enabled = stub_domain.Enabled(value=enabled)
        if metadata is not None:
            stub.set_metadata(value=metadata)

        await self._stub_repo.update(entity=stub)
        return stub

    async def delete_stub(self, id: str) -> None:
        stub = await self._stub_repo.get(id=stub_domain.Id(value=id))
        if not stub:
            raise exceptions.NotFoundError(f"stub '{id}' does not exist.")

        # Delete
        await self._stub_repo.remove(entity=stub)

    async def reload_stubs(self) -> list[stub_domain.Entity]:
        await self._stub_repo.remove_all()

        yaml_file = await self._file_repo.get(
            id=file_domain.Id(value="/stubs/stubs.yaml")
        )
        if yaml_file:
            entities = []
            _yaml = dict(yaml.safe_load(yaml_file.data.value))

            # Create Entities
            for stub_yaml in _yaml["stubs"]:
                # Setup variables
                entity = stub_domain.Entity(
                    id=stub_domain.Id(value=stub_yaml["id"]),
                    description=stub_domain.Description(
                        value=stub_yaml.get("description", "")
                    ),
                    handler=stub_domain.Handler(value=stub_yaml["handler"]),
                    yang=yang_tree_domain.Id(value=stub_yaml.get("yang", "")),
                    enabled=stub_domain.Enabled(value=stub_yaml.get("enabled", True)),
                )
                entity.set_metadata(value=stub_yaml.get("metadata", {}))
                entities.append(entity)

            await self._stub_repo.save(entity=entities)

        stubs = await self._stub_repo.list()
        return stubs

    async def list_yangs(
        self,
        id: typing.Union[str, typing.List[str], None] = None,
    ) -> list[yang_tree_domain.Entity]:
        if id is None:
            ids = None
        else:
            ids = [
                yang_tree_domain.Id(value=i)
                for i in (id if isinstance(id, list) else [id])
            ]

        # List
        yangs = await self._yang_tree_repo.list(id=ids)
        return yangs

    async def get_yang(self, id: str) -> yang_tree_domain.Entity:
        # Get
        yang = await self._yang_tree_repo.get(id=yang_tree_domain.Id(value=id))
        if not yang:
            raise exceptions.NotFoundError(f"yang module '{id}' does not exist.")
        return yang

    async def reload_yangs(self) -> None:
        await self._yang_tree_repo.remove_all()
        directories = await self._file_repo.list(
            type=file_domain.Type(value="directory"),
            parent_id=file_domain.Id(value="/yangs"),
            include_data=False,
            recursive=False,
        )
        for directory in directories:
            _files = await self._file_repo.list(
                parent_id=file_domain.Id(
                    value=f"/yangs/{directory.get_name()}/yang_tree"
                ),
                recursive=False,
            )
            yang_tree_files = [
                file
                for file in _files
                if re.match(r"\Ayang_tree_[0-9]+\.part\Z", file.get_name())
            ]
            if yang_tree_files:
                sorted_files = sorted(
                    yang_tree_files,
                    key=lambda x: int(x.get_name().split(".")[0].split("_")[2]),
                )
                text = "".join([file.data.value for file in sorted_files])

                yang_tree = yang_tree_domain.Entity(
                    id=yang_tree_domain.Id(value=directory.get_name()),
                    yang_tree=yang_tree_domain.YangTree(
                        value=yang.YangTree(xml=xml_utils.from_string(text))
                    ),
                )
                await self._yang_tree_repo.add(entity=yang_tree)

    async def handle_network_operation(
        self, request: plugin.Request
    ) -> plugin.Response:
        stub_id = request.stub_id
        req_body = json.loads(request.body)
        protocol = req_body["protocol"]

        stub = await self._stub_repo.get(id=stub_domain.Id(stub_id))
        if stub is None:
            raise exceptions.NotFoundError(f"stub '{stub_id}' does not exist.")
        if stub.enabled == stub_domain.Enabled(value=False):
            raise exceptions.NotFoundError(f"stub '{stub_id}' is not enabled.")

        netconf_service = netconf_service_domain.NetconfService(
            session_id=(
                request.netconf.session_id if hasattr(request, "netconf") else None
            ),
            yang_tree_repo=self._yang_tree_repo,
        )
        snmp_service = snmp_service_domain.SNMPService()

        # Import module
        if self._module_dir_checker.is_changed():
            logger.info(f"Reloading module.")
            module_utils.delete_module(name="module", recursive=True)
            self._module_dir_checker.refresh()
        module_path = f"module.handlers.{stub.handler.value}"
        handler_module = module_utils.import_module(
            module_path=module_path, reload=False
        )

        # Reset YANG tree
        if self._yangs_dir_checker.is_changed():
            logger.info(f"Reloading YANG tree.")
            await self.reload_yangs()
            self._yangs_dir_checker.refresh()

        # Create context
        ctx = plugin.Context(
            request=request,
            stub=stub,
            file_repo=self._file_repo,
            stub_repo=self._stub_repo,
            netconf_service=netconf_service,
            snmp_service=snmp_service,
        )

        # Setup
        handler: plugin.Handler = await handler_module.setup(ctx)

        # Handle
        if protocol in ["http", "https"]:
            response = await handler.handle_http(ctx)
        elif protocol == "netconf":
            if request.netconf.connection_status == "login":
                response = await handler.netconf_hello_message(ctx)
            elif request.netconf.connection_status == "established":
                response = await handler.handle_netconf(ctx)
            else:
                raise exceptions.FatalError(
                    f"Invalid connection status: '{request.netconf.connection_status}'"
                )
        elif protocol == "ssh":
            if request.ssh.connection_status == "login":
                response = await handler.ssh_login_message(ctx)
            elif request.ssh.connection_status == "established":
                response = await handler.handle_ssh(ctx)
            else:
                raise exceptions.FatalError(
                    f"Invalid connection status: '{request.ssh.connection_status}'"
                )
        elif protocol == "telnet":
            if request.telnet.connection_status == "login":
                response = await handler.telnet_login_message(ctx)
            elif request.telnet.connection_status == "established":
                response = await handler.handle_telnet(ctx)
            else:
                raise exceptions.FatalError(
                    f"Invalid connection status: '{request.telnet.connection_status}'"
                )
        elif protocol == "snmp":
            response = await handler.handle_snmp(ctx)
        else:
            raise exceptions.FatalError(f"Invalid configuration_protocol: '{protocol}'")

        return response
