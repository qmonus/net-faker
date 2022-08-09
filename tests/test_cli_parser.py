import pytest
from qmonus_net_faker import __main__


def test_returns_parsed_args_when_valid_args_are_passed_for_init_command():
    args = __main__.parse_args(args=["init", "."])
    assert args.project_path == "."


def test_exits_with_error_when_invalid_args_are_passed_for_init_command():
    with pytest.raises(SystemExit) as e:
        __main__.parse_args(args=["init"])
    assert e.value.code != 0


@pytest.mark.parametrize(
    "case",
    [
        {
            "args": ["build", ".", "yang_name_1"],
            "expected": {
                "project_path": ".",
                "yang_name": "yang_name_1",
                "log_level": "info",
            },
        },
        {
            "args": ["build", "project_path", "yang_name_2", "--log-level", "debug"],
            "expected": {
                "project_path": "project_path",
                "yang_name": "yang_name_2",
                "log_level": "debug",
            },
        },
    ],
)
def test_returns_parsed_args_when_valid_args_are_passed_for_build_command(case: dict):
    parsed_args = __main__.parse_args(args=case["args"])
    assert parsed_args.project_path == case["expected"]["project_path"]
    assert parsed_args.yang_name == case["expected"]["yang_name"]
    assert parsed_args.log_level == case["expected"]["log_level"]


@pytest.mark.parametrize(
    "case",
    [
        {"args": ["build"]},
        {"args": ["build", "."]},
        {"args": ["build", ".", "--log-level", "invalid_log_level"]},
    ],
)
def test_exits_with_error_when_invalid_args_are_passed_for_build_command(case: dict):
    with pytest.raises(SystemExit) as e:
        __main__.parse_args(args=case["args"])
    assert e.value.code != 0


def test_exits_with_error_when_invalid_args_are_passed_for_run_command():
    with pytest.raises(SystemExit) as e:
        __main__.parse_args(args=["run"])
    assert e.value.code != 0


@pytest.mark.parametrize(
    "case",
    [
        {
            "args": ["run", "manager", "."],
            "expected": {
                "log_level": "info",
                "log_file_path": "",
                "log_file_size": 3 * 1024 * 1024,
                "log_file_backup_count": 2,
                "project_path": ".",
                "host": "0.0.0.0",
                "port": 10080,
            },
        },
        {
            "args": [
                "run",
                "manager",
                "project_path",
                "--log-level",
                "debug",
                "--log-file-path",
                "log",
                "--log-file-size",
                "1024",
                "--log-file-backup-count",
                "3",
                "--host",
                "127.0.0.1",
                "--port",
                "80",
            ],
            "expected": {
                "log_level": "debug",
                "log_file_path": "log",
                "log_file_size": 1024,
                "log_file_backup_count": 3,
                "project_path": "project_path",
                "host": "127.0.0.1",
                "port": 80,
            },
        },
    ],
)
def test_returns_parsed_args_when_valid_args_are_passed_for_run_manager_command(
    case: dict,
):
    args = __main__.parse_args(args=case["args"])
    assert args.log_level == case["expected"]["log_level"]
    assert args.log_file_path == case["expected"]["log_file_path"]
    assert args.log_file_size == case["expected"]["log_file_size"]
    assert args.log_file_backup_count == case["expected"]["log_file_backup_count"]
    assert args.project_path == case["expected"]["project_path"]
    assert args.host == case["expected"]["host"]
    assert args.port == case["expected"]["port"]


def test_exits_with_error_when_invalid_args_are_passed_for_run_manager_command():
    with pytest.raises(SystemExit) as e:
        __main__.parse_args(args=["run", "manager"])
    assert e.value.code != 0


@pytest.mark.parametrize(
    "case",
    [
        {
            "args": ["run", "stub", "netfaker-stub-0", "http://127.0.0.1:10080"],
            "expected": {
                "log_level": "info",
                "log_file_path": "",
                "log_file_size": 3 * 1024 * 1024,
                "log_file_backup_count": 2,
                "stub_id": "netfaker-stub-0",
                "manager_endpoint": "http://127.0.0.1:10080",
                "host": "0.0.0.0",
                "http_port": 20080,
                "https_port": 20443,
                "ssh_port": 20022,
                "telnet_port": 20023,
                "snmp_port": 20161,
                "protocols": ["ssh", "http", "https", "telnet", "snmp"],
            },
        },
        {
            "args": [
                "run",
                "stub",
                "netfaker-stub-1",
                "http://127.0.0.2:10080",
                "--log-level",
                "debug",
                "--log-file-path",
                "log",
                "--log-file-size",
                "1024",
                "--log-file-backup-count",
                "3",
                "--host",
                "127.0.0.1",
                "--http-port",
                "80",
                "--https-port",
                "443",
                "--ssh-port",
                "22",
                "--telnet-port",
                "23",
                "--snmp-port",
                "161",
                "--protocol",
                "ssh",
                "http",
            ],
            "expected": {
                "log_level": "debug",
                "log_file_path": "log",
                "log_file_size": 1024,
                "log_file_backup_count": 3,
                "stub_id": "netfaker-stub-1",
                "manager_endpoint": "http://127.0.0.2:10080",
                "host": "127.0.0.1",
                "http_port": 80,
                "https_port": 443,
                "ssh_port": 22,
                "telnet_port": 23,
                "snmp_port": 161,
                "protocols": ["ssh", "http"],
            },
        },
    ],
)
def test_returns_parsed_args_when_valid_args_are_passed_for_run_stub_command(
    case: dict,
):
    args = __main__.parse_args(args=case["args"])
    assert args.log_level == case["expected"]["log_level"]
    assert args.log_file_path == case["expected"]["log_file_path"]
    assert args.log_file_size == case["expected"]["log_file_size"]
    assert args.log_file_backup_count == case["expected"]["log_file_backup_count"]
    assert args.stub_id == case["expected"]["stub_id"]
    assert args.manager_endpoint == case["expected"]["manager_endpoint"]
    assert args.host == case["expected"]["host"]
    assert args.http_port == case["expected"]["http_port"]
    assert args.https_port == case["expected"]["https_port"]
    assert args.ssh_port == case["expected"]["ssh_port"]
    assert args.telnet_port == case["expected"]["telnet_port"]
    assert args.snmp_port == case["expected"]["snmp_port"]
    assert args.protocols == case["expected"]["protocols"]


@pytest.mark.parametrize(
    "case",
    [
        {"args": ["run", "stub"]},
        {"args": ["run", "stub", "netfaker-stub-0"]},
    ],
)
def test_exits_with_error_when_invalid_args_are_passed_for_run_stub_command(case: dict):
    with pytest.raises(SystemExit) as e:
        __main__.parse_args(args=case["args"])
    assert e.value.code != 0
