import asyncio

import pytest
import aiohttp

from . import http_client as _http_client


# @pytest.fixture(scope='function', autouse=True)
# def event_loop():
#     loop = asyncio.get_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture(scope="session")
def project_path(tmp_path_factory: pytest.TempPathFactory):
    return tmp_path_factory.mktemp("project_path")


@pytest.fixture(scope="function")
async def http_client():
    client = _http_client.HttpClient()
    yield client
    await client.close()
