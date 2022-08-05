import logging
import logging.handlers
import warnings
import typing
import sys
import asyncio
import argparse
import pathlib

from . import (
    __version__,
    action,
    constants,
)
from .libs import file_lib

logger = logging.getLogger(__name__)


def parse_args(args: list[str]) -> argparse.Namespace:
    # Parse args
    parser = argparse.ArgumentParser(
        prog="qmonus_net_faker",
        description="Qmonus-NetFaker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub_parser_action = parser.add_subparsers(dest="sub_parser")
    init_parser = sub_parser_action.add_parser(
        "init",
        help="initialize",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    build_parser = sub_parser_action.add_parser("build", help="build yang-tree")
    run_parser = sub_parser_action.add_parser(
        "run",
        help="run manager or stub",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    run_sub_parser_action = run_parser.add_subparsers(
        dest="run_sub_parser", required=True
    )
    manager_parser = run_sub_parser_action.add_parser(
        "manager",
        help="run manager",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    stub_parser = run_sub_parser_action.add_parser(
        "stub",
        help="run stub",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # version
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # deprecated
    parser.add_argument(
        "--role",
        type=str,
        dest="roles",
        nargs="*",
        default=[
            "manager",
            "ssh-stub",
            "http-stub",
            "https-stub",
            "telnet-stub",
            "snmp-stub",
        ],
        choices=[
            "manager",
            "ssh-stub",
            "http-stub",
            "https-stub",
            "telnet-stub",
            "snmp-stub",
        ],
        help="deprecated: role",
    )
    parser.add_argument(
        "--host",
        type=str,
        dest="host",
        default="0.0.0.0",
        help="deprecated: host to listen on",
    )
    parser.add_argument(
        "--manager-port",
        type=int,
        dest="manager_port",
        default=10080,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--http-stub-port",
        type=int,
        dest="http_stub_port",
        default=20080,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--https-stub-port",
        type=int,
        dest="https_stub_port",
        default=20443,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--ssh-stub-port",
        type=int,
        dest="ssh_stub_port",
        default=20022,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--telnet-stub-port",
        type=int,
        dest="telnet_stub_port",
        default=20023,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--snmp-stub-port",
        type=int,
        dest="snmp_stub_port",
        default=20161,
        help="deprecated: port to listen on",
    )
    parser.add_argument(
        "--plugin-path",
        type=str,
        dest="project_path",
        help="deprecated: project directory path",
    )
    parser.add_argument(
        "--stub-id",
        type=str,
        dest="stub_id",
        default="netfaker-stub-0",
        help="deprecated: stub id",
    )
    parser.add_argument(
        "--manager-endpoint",
        type=str,
        dest="manager_endpoint",
        default="http://127.0.0.1:10080",
        help="deprecated: manager endpoint",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        dest="log_level",
        choices=["debug", "info"],
        default=constants.DEFAULT_LOG_LEVEL,
        help="deprecated: log level",
    )
    parser.add_argument(
        "--log-file-path",
        type=str,
        dest="log_file_path",
        default="",
        help="deprecated: log file path",
    )
    parser.add_argument(
        "--log-file-size",
        type=int,
        dest="log_file_size",
        default=constants.DEFAULT_MAX_LOG_FILE_SIZE,
        help="deprecated: max log file size",
    )
    parser.add_argument(
        "--log-file-backup-count",
        type=int,
        dest="log_file_backup_count",
        default=constants.DEFAULT_MAX_LOG_FILE_BACKUP_COUNT,
        help="deprecated: log file backup count",
    )

    # init command
    init_parser.add_argument(
        "project_path",
        type=str,
        help="project directory path",
    )

    # build command
    build_parser.add_argument(
        "project_path",
        type=str,
        help="project directory path",
    )
    build_parser.add_argument(
        "yang_name",
        type=str,
        help="YANG module name",
    )
    build_parser.add_argument(
        "--log-level",
        type=str,
        dest="log_level",
        choices=["debug", "info"],
        default=constants.DEFAULT_LOG_LEVEL,
        help="log level",
    )

    # run manager command
    manager_parser.add_argument(
        "project_path",
        type=str,
        help="project directory path",
    )
    manager_parser.add_argument(
        "--host",
        type=str,
        dest="host",
        default="0.0.0.0",
        help="host to listen on",
    )
    manager_parser.add_argument(
        "--port",
        type=int,
        dest="port",
        default=10080,
        help="port to listen on",
    )
    manager_parser.add_argument(
        "--log-level",
        type=str,
        dest="log_level",
        choices=["debug", "info"],
        default=constants.DEFAULT_LOG_LEVEL,
        help="log level",
    )
    manager_parser.add_argument(
        "--log-file-path",
        type=str,
        dest="log_file_path",
        default="",
        help="log file path",
    )
    manager_parser.add_argument(
        "--log-file-size",
        type=int,
        dest="log_file_size",
        default=constants.DEFAULT_MAX_LOG_FILE_SIZE,
        help="max log file size",
    )
    manager_parser.add_argument(
        "--log-file-backup-count",
        type=int,
        dest="log_file_backup_count",
        default=constants.DEFAULT_MAX_LOG_FILE_BACKUP_COUNT,
        help="log file backup count",
    )

    # run stub command
    stub_parser.add_argument(
        "stub_id",
        type=str,
        help="stub-id",
    )
    stub_parser.add_argument(
        "manager_endpoint",
        type=str,
        help="manager endpoint: http://{manager_host}:{manager_port}",
    )
    stub_parser.add_argument(
        "--host",
        type=str,
        dest="host",
        default="0.0.0.0",
        help="host to listen on",
    )
    stub_parser.add_argument(
        "--http-port",
        type=int,
        dest="http_port",
        default=20080,
        help="port to listen on",
    )
    stub_parser.add_argument(
        "--https-port",
        type=int,
        dest="https_port",
        default=20443,
        help="port to listen on",
    )
    stub_parser.add_argument(
        "--ssh-port",
        type=int,
        dest="ssh_port",
        default=20022,
        help="port to listen on",
    )
    stub_parser.add_argument(
        "--telnet-port",
        type=int,
        dest="telnet_port",
        default=20023,
        help="port to listen on",
    )
    stub_parser.add_argument(
        "--snmp-port",
        type=int,
        dest="snmp_port",
        default=20161,
        help="port to listen on",
    )
    stub_parser.add_argument(
        "--protocol",
        type=str,
        dest="protocols",
        nargs="+",
        default=["ssh", "http", "https", "telnet", "snmp"],
        choices=["ssh", "http", "https", "telnet", "snmp"],
        help="protocol",
    )
    stub_parser.add_argument(
        "--log-level",
        type=str,
        dest="log_level",
        choices=["debug", "info"],
        default=constants.DEFAULT_LOG_LEVEL,
        help="log level",
    )
    stub_parser.add_argument(
        "--log-file-path",
        type=str,
        dest="log_file_path",
        default="",
        help="log file path",
    )
    stub_parser.add_argument(
        "--log-file-size",
        type=int,
        dest="log_file_size",
        default=constants.DEFAULT_MAX_LOG_FILE_SIZE,
        help="max log file size",
    )
    stub_parser.add_argument(
        "--log-file-backup-count",
        type=int,
        dest="log_file_backup_count",
        default=constants.DEFAULT_MAX_LOG_FILE_BACKUP_COUNT,
        help="log file backup count",
    )

    parsed_args = parser.parse_args(args)
    return parsed_args


def setup_logging(
    log_level: str,
    log_file_size: int,
    log_file_backup_count: int,
    log_file_path: str,
) -> None:
    # Setup logging
    if log_level == "debug":
        _log_level = logging.DEBUG
    elif log_level == "info":
        _log_level = logging.INFO
    else:
        raise ValueError(f"Invalid log-level: '{log_level}'")

    if log_file_size <= 0:
        raise ValueError(f"Invalid log-file-size: '{log_file_size}'")

    if log_file_backup_count <= 0:
        raise ValueError(f"Invalid log-file-backup-count: '{log_file_backup_count}'")

    # Setup aiohttp logger
    logging.getLogger("aiohttp.access").setLevel(logging.ERROR)

    # Setup logger
    root_logger = logging.getLogger()
    root_logger.setLevel(_log_level)
    formatter = logging.Formatter(constants.LOG_FORMAT)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_file_path:
        # Create log directory
        log_file = pathlib.Path(log_file_path).resolve()
        file_lib.create_dir(log_file.parent)

        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file),
            maxBytes=log_file_size,
            backupCount=log_file_backup_count,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def main() -> None:
    args = parse_args(sys.argv[1:])

    if args.sub_parser is None:
        # deprecated
        warnings.warn("Use 'qmonus_net_faker run' command instead.", DeprecationWarning)

        host = args.host
        roles = args.roles
        project_path = args.project_path
        manager_endpoint = args.manager_endpoint
        stub_id = args.stub_id
        manager_port = args.manager_port
        http_stub_port = args.http_stub_port
        https_stub_port = args.https_stub_port
        ssh_stub_port = args.ssh_stub_port
        telnet_stub_port = args.telnet_stub_port
        snmp_stub_port = args.snmp_stub_port
        log_level = args.log_level
        log_file_path = args.log_file_path
        log_file_size = args.log_file_size
        log_file_backup_count = args.log_file_backup_count

        setup_logging(
            log_level=log_level,
            log_file_path=log_file_path,
            log_file_size=log_file_size,
            log_file_backup_count=log_file_backup_count,
        )

        # execute
        async def _do() -> None:
            aws = []
            if "manager" in roles:
                if project_path is None:
                    raise ValueError("'--plugin-path' must be set")

                aw = action.run_manager(
                    host=host,
                    port=manager_port,
                    project_path=project_path,
                )
                aws.append(aw)

            protocols: list[
                typing.Literal["ssh", "http", "https", "telnet", "snmp"]
            ] = []
            for role in roles:
                if role == "http-stub":
                    protocols.append("http")
                elif role == "https-stub":
                    protocols.append("https")
                elif role == "ssh-stub":
                    protocols.append("ssh")
                elif role == "telnet-stub":
                    protocols.append("telnet")
                elif role == "snmp-stub":
                    protocols.append("snmp")

            if protocols:
                aw = action.run_stub(
                    stub_id=stub_id,
                    manager_endpoint=manager_endpoint,
                    host=host,
                    http_port=http_stub_port,
                    https_port=https_stub_port,
                    ssh_port=ssh_stub_port,
                    telnet_port=telnet_stub_port,
                    snmp_port=snmp_stub_port,
                    protocols=protocols,
                )
                aws.append(aw)

            await asyncio.gather(*aws)

        try:
            asyncio.run(_do())
        except (KeyboardInterrupt, SystemExit) as e:
            logger.info(f"Stopped: {e.__class__.__name__}")
    elif args.sub_parser == "init":
        project_path = args.project_path
        asyncio.run(action.init(project_path=project_path))
    elif args.sub_parser == "build":
        project_path = args.project_path
        yang_name = args.yang_name
        log_level = args.log_level

        # Setup logger
        if log_level == "debug":
            _log_level = logging.DEBUG
        elif log_level == "info":
            _log_level = logging.INFO
        else:
            raise ValueError(f"Invalid log-level value: '{log_level}'")
        logging.basicConfig(format=constants.LOG_FORMAT, level=_log_level)

        asyncio.run(action.build(project_path=project_path, yang_name=yang_name))
    elif args.sub_parser == "run":
        log_level = args.log_level
        log_file_path = args.log_file_path
        log_file_size = args.log_file_size
        log_file_backup_count = args.log_file_backup_count

        setup_logging(
            log_level=log_level,
            log_file_path=log_file_path,
            log_file_size=log_file_size,
            log_file_backup_count=log_file_backup_count,
        )

        if args.run_sub_parser == "manager":
            host = args.host
            port = args.port
            project_path = args.project_path

            try:
                asyncio.run(
                    action.run_manager(
                        host=host,
                        port=port,
                        project_path=project_path,
                    )
                )
            except (KeyboardInterrupt, SystemExit) as e:
                logger.info(f"Stopped: {e.__class__.__name__}")
        elif args.run_sub_parser == "stub":
            stub_id = args.stub_id
            manager_endpoint = args.manager_endpoint
            host = args.host
            http_port = args.http_port
            https_port = args.https_port
            ssh_port = args.ssh_port
            telnet_port = args.telnet_port
            snmp_port = args.snmp_port
            protocols = args.protocols

            try:
                asyncio.run(
                    action.run_stub(
                        stub_id=stub_id,
                        manager_endpoint=manager_endpoint,
                        host=host,
                        http_port=http_port,
                        https_port=https_port,
                        ssh_port=ssh_port,
                        telnet_port=telnet_port,
                        snmp_port=snmp_port,
                        protocols=protocols,
                    )
                )
            except (KeyboardInterrupt, SystemExit) as e:
                logger.info(f"Stopped: {e.__class__.__name__}")
        else:
            raise ValueError("FatalError: Invalid command")
    else:
        raise ValueError("FatalError: Invalid command")


if __name__ == "__main__":
    main()
