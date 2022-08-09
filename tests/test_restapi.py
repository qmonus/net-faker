import pathlib

import pytest
from qmonus_net_faker import action, server

from . import http_client


@pytest.fixture(scope="function", autouse=True)
async def setup_function(project_path: pathlib.Path):
    await action.init(project_path=str(project_path))
    manager = await server.create_manager(
        host="127.0.0.1", port=10080, project_path=str(project_path)
    )
    await manager.start()
    yield
    await manager.stop()


@pytest.fixture(scope="function")
async def initial_stubs():
    return [
        {
            "id": "netfaker-stub-0",
            "description": "junos-0",
            "handler": "junos",
            "yang": "junos",
            "enabled": True,
            "metadata": {},
            "candidateConfig": "<root/>\n",
            "runningConfig": "<root/>\n",
            "startupConfig": "<root/>\n",
        },
        {
            "id": "netfaker-stub-1",
            "description": "junos-1",
            "handler": "junos",
            "yang": "junos",
            "enabled": True,
            "metadata": {},
            "candidateConfig": "<root/>\n",
            "runningConfig": "<root/>\n",
            "startupConfig": "<root/>\n",
        },
        {
            "id": "netfaker-stub-2",
            "description": "junos-2",
            "handler": "junos",
            "yang": "junos",
            "enabled": True,
            "metadata": {},
            "candidateConfig": "<root/>\n",
            "runningConfig": "<root/>\n",
            "startupConfig": "<root/>\n",
        },
    ]


@pytest.fixture(scope="function")
async def initial_yangs():
    return [
        {
            "id": "junos",
        }
    ]


@pytest.mark.asyncio
async def test_shows_stubs(http_client: http_client.HttpClient, initial_stubs: list):
    # with no params
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs",
    )
    assert resp.status == 200
    stubs = resp.json["stubs"]
    assert sorted(stubs, key=lambda x: x["id"]) == initial_stubs

    # with params
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs",
        params={"id": "netfaker-stub-0"},
    )
    assert resp.status == 200
    stubs = resp.json["stubs"]
    assert stubs[0] == initial_stubs[0]


@pytest.mark.asyncio
async def test_shows_a_stub(http_client: http_client.HttpClient, initial_stubs: list):
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/netfaker-stub-0",
    )
    assert resp.status == 200
    stub = resp.json["stub"]
    assert stub == initial_stubs[0]


@pytest.mark.asyncio
async def test_shows_not_found_error_when_getting_a_non_existing_stub(
    http_client: http_client.HttpClient,
):
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/dummy",
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_creates_a_stub(http_client: http_client.HttpClient):
    # With required properties only
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_0",
                "handler": "handler_0",
            }
        },
    )
    assert resp.status == 200
    created_stub = resp.json["stub"]
    assert created_stub == {
        "id": "id_0",
        "description": "",
        "handler": "handler_0",
        "yang": "",
        "enabled": True,
        "metadata": {},
        "candidateConfig": "<root/>\n",
        "runningConfig": "<root/>\n",
        "startupConfig": "<root/>\n",
    }

    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/id_0",
    )
    assert resp.status == 200
    stub = resp.json["stub"]
    assert stub == created_stub

    # With all properties
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_1",
                "description": "description_1",
                "handler": "handler_1",
                "yang": "yang_1",
                "enabled": False,
                "metadata": {"data": {}},
            }
        },
    )
    assert resp.status == 200
    created_stub = resp.json["stub"]
    assert created_stub == {
        "id": "id_1",
        "description": "description_1",
        "handler": "handler_1",
        "yang": "yang_1",
        "enabled": False,
        "metadata": {"data": {}},
        "candidateConfig": "<root/>\n",
        "runningConfig": "<root/>\n",
        "startupConfig": "<root/>\n",
    }

    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/id_1",
    )
    assert resp.status == 200
    stub = resp.json["stub"]
    assert stub == created_stub


@pytest.mark.asyncio
async def test_shows_conflict_error_when_creating_a_duplicate_stub(
    http_client: http_client.HttpClient,
):
    # Prepare
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_0",
                "handler": "handler_0",
            }
        },
    )
    assert resp.status == 200

    # Create a duplicate stub
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_0",
                "handler": "handler_0",
            }
        },
    )
    assert resp.status == 409


@pytest.mark.asyncio
async def test_updates_a_stub(http_client: http_client.HttpClient):
    # Prepare
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_0",
                "handler": "handler_0",
            }
        },
    )
    assert resp.status == 200

    # With required properties only
    resp = await http_client.request(
        method="PATCH", url="http://127.0.0.1:10080/stubs/id_0", data={"stub": {}}
    )
    assert resp.status == 200
    updated_stub = resp.json["stub"]
    assert updated_stub == {
        "id": "id_0",
        "description": "",
        "handler": "handler_0",
        "yang": "",
        "enabled": True,
        "metadata": {},
        "candidateConfig": "<root/>\n",
        "runningConfig": "<root/>\n",
        "startupConfig": "<root/>\n",
    }

    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/id_0",
    )
    assert resp.status == 200
    stub = resp.json["stub"]
    assert stub == updated_stub

    # With all properties
    resp = await http_client.request(
        method="PATCH",
        url="http://127.0.0.1:10080/stubs/id_0",
        data={
            "stub": {
                "description": "description_1",
                "handler": "handler_1",
                "yang": "yang_1",
                "enabled": False,
                "metadata": {"data": {}},
            }
        },
    )
    assert resp.status == 200
    updated_stub = resp.json["stub"]
    assert updated_stub == {
        "id": "id_0",
        "description": "description_1",
        "handler": "handler_1",
        "yang": "yang_1",
        "enabled": False,
        "metadata": {"data": {}},
        "candidateConfig": "<root/>\n",
        "runningConfig": "<root/>\n",
        "startupConfig": "<root/>\n",
    }

    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/stubs/id_0",
    )
    assert resp.status == 200
    stub = resp.json["stub"]
    assert stub == updated_stub


@pytest.mark.asyncio
async def test_shows_not_found_error_when_updating_a_non_existing_stub(
    http_client: http_client.HttpClient,
):
    # Update
    resp = await http_client.request(
        method="PATCH", url="http://127.0.0.1:10080/stubs/dummy", data={"stub": {}}
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_deletes_a_stub(http_client: http_client.HttpClient):
    # Prepare
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs",
        data={
            "stub": {
                "id": "id_0",
                "handler": "handler_0",
            }
        },
    )
    assert resp.status == 200

    # Delete
    resp = await http_client.request(
        method="DELETE",
        url="http://127.0.0.1:10080/stubs/id_0",
    )
    assert resp.status == 204


@pytest.mark.asyncio
async def test_shows_not_found_error_when_deleting_a_non_existing_stub(
    http_client: http_client.HttpClient,
):
    # Delete
    resp = await http_client.request(
        method="DELETE",
        url="http://127.0.0.1:10080/stubs/dummy",
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_reloads_stubs(http_client: http_client.HttpClient, initial_stubs: list):
    resp = await http_client.request(
        method="POST",
        url="http://127.0.0.1:10080/stubs:reload",
    )
    assert resp.status == 200
    stubs = resp.json["stubs"]
    assert sorted(stubs, key=lambda x: x["id"]) == initial_stubs


@pytest.mark.asyncio
async def test_shows_yangs(http_client: http_client.HttpClient, initial_yangs: list):
    # with no params
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/yangs",
    )
    assert resp.status == 200
    yangs = resp.json["yangs"]
    assert sorted(yangs, key=lambda x: x["id"]) == initial_yangs

    # with params
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/yangs",
        params={"id": "junos"},
    )
    assert resp.status == 200
    yangs = resp.json["yangs"]
    assert yangs[0] == initial_yangs[0]


@pytest.mark.asyncio
async def test_shows_a_yang(http_client: http_client.HttpClient, initial_yangs: list):
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/yangs/junos",
    )
    assert resp.status == 200
    yang = resp.json["yang"]
    assert yang == initial_yangs[0]


@pytest.mark.asyncio
async def test_shows_not_found_error_when_getting_a_non_existing_yang(
    http_client: http_client.HttpClient,
):
    resp = await http_client.request(
        method="GET",
        url="http://127.0.0.1:10080/yangs/dummy",
    )
    assert resp.status == 404
