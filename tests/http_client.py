import typing
import json
import dataclasses

import aiohttp


@dataclasses.dataclass
class Response(object):
    status: int
    headers: typing.Any
    data: typing.Any

    @property
    def json(self):
        return json.loads(self.data)


class HttpClient(object):
    def __init__(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        await self._session.close()

    async def request(
        self,
        method: typing.Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
        data: typing.Union[str, dict, None] = None,
        ssl: bool = False,
        timeout: int = 60,
    ) -> Response:
        if isinstance(data, dict):
            _data = json.dumps(data)
        else:
            _data = data

        async with self._session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=_data,
            ssl=ssl,
            timeout=timeout,
        ) as resp:
            _resp = Response(
                status=resp.status,
                headers=resp.headers,
                data=await resp.text(),
            )
        return _resp
