import pytest
import pytest_asyncio

from . import http_client as _http_client


@pytest.fixture(scope="session")
def project_path(tmp_path_factory: pytest.TempPathFactory):
    return tmp_path_factory.mktemp("project_path")


@pytest_asyncio.fixture(scope="function")
async def http_client():
    client = _http_client.HttpClient()
    yield client
    await client.close()
