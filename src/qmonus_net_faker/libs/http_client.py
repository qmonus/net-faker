from __future__ import annotations
import typing
import time
import json
import base64
import urllib.parse
import logging

import aiohttp

logger = logging.getLogger(__name__)


class RequestData(object):
    def __init__(
        self,
        scheme: str,
        method: str,
        url: str,
        path: str,
        query: dict[str, list[str]],
        headers: dict[str, str],
        body: typing.Optional[str],
    ) -> None:
        self.scheme = scheme
        self.method = method
        self.url = url
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def to_dict(self) -> dict[str, typing.Any]:
        return {
            "scheme": self.scheme,
            "method": self.method,
            "url": self.url,
            "path": self.path,
            "query": self.query,
            "headers": self.headers,
            "body": self.body,
        }


class ResponseData(object):
    def __init__(
        self,
        code: int,
        reason: typing.Optional[str],
        rtt: float,
        headers: dict[str, str],
        body: str,
        request: RequestData,
    ) -> None:
        self.code = code
        self.reason = reason
        self.rtt = rtt
        self.headers = headers
        self.body = body
        self.request = request

    def to_dict(self) -> dict[str, typing.Any]:
        return {
            "code": self.code,
            "reason": self.reason,
            "rtt": self.rtt,
            "headers": self.headers,
            "body": self.body,
            "request": self.request.to_dict(),
        }


class Session(object):
    def __init__(self, default_timeout: int = 300) -> None:
        self._default_timeout = default_timeout
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(
        self, exc_type: typing.Any, exc_val: typing.Any, exc_tb: typing.Any
    ) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        url: str,
        query: typing.Optional[dict[str, list[str]]] = None,
        headers: typing.Optional[dict[str, str]] = None,
        basic_auth: typing.Optional[dict[str, str]] = None,
        body: typing.Optional[str] = None,
        json_body: typing.Optional[typing.Any] = None,
        timeout: typing.Optional[int] = None,
        ssl: bool = False,
    ) -> ResponseData:
        # if query is None:
        #     query = {}

        if headers is None:
            headers = {}

        if basic_auth is not None:
            _encoded = "{username}:{password}".format(**basic_auth).encode("utf-8")
            headers["Authorization"] = "Basic {}".format(
                base64.b64encode(_encoded).decode()
            )

        if body is not None and json_body is not None:
            raise ValueError(
                "body and json_body parameters can not be used at the same time."
            )

        if json_body is not None:
            body = json.dumps(json_body)

        if timeout is None:
            timeout = self._default_timeout

        if ssl is True:
            _ssl = None
        else:
            _ssl = False

        # url = add_query(url, query)

        logger.debug(
            "Sending: {} {} headers: {} body: {}".format(method, url, headers, body)
        )
        sent_at = time.time()

        async with self._session.request(
            method=method,
            url=url,
            params=query,
            headers=headers,
            data=body,
            ssl=_ssl,
            timeout=timeout,
        ) as resp:
            received_at = time.time()

            req = RequestData(
                scheme=resp.request_info.url.scheme,
                method=resp.request_info.method,
                url=str(resp.request_info.url),
                path=resp.request_info.url.path,
                query=to_query_dict(resp.request_info.url.query_string),
                headers=dict(resp.request_info.headers),
                body=body,
            )

            res = ResponseData(
                code=resp.status,
                reason=resp.reason,
                rtt=received_at - sent_at,
                headers=dict(resp.headers),
                body=await resp.text(),
                request=req,
            )

        logger.debug(f"Received: {res.to_dict()}")
        return res

    async def get(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseData:
        return await self.request(*args, method="GET", **kwargs)  # type: ignore

    async def post(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseData:
        return await self.request(method="POST", *args, **kwargs)  # type: ignore

    async def put(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseData:
        return await self.request(method="PUT", *args, **kwargs)  # type: ignore

    async def patch(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseData:
        return await self.request(method="PATCH", *args, **kwargs)  # type: ignore

    async def delete(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseData:
        return await self.request(method="DELETE", *args, **kwargs)  # type: ignore


# def add_query(url, query: typing.Optional[dict[str, list[str]]] = None) -> str:
#     if not (url.startswith('http://') or url.startswith('https://')):
#         raise ValueError("url must start with 'http://' or 'https://'")
#     if query is None:
#         query = {}
#     parsed = urllib.parse.urlparse(url)
#     new_query = to_query_dict(parsed.query)

#     for name, values in query.items():
#         if name not in new_query:
#             new_query[name] = []
#         new_query[name] = new_query[name] + values

#     new_url = '{scheme}://{netloc}{path}'.format(scheme=parsed.scheme, netloc=parsed.netloc, path=parsed.path)
#     if new_query:
#         new_url = new_url + '?' + to_query_string(new_query)
#     if parsed.fragment:
#         new_url = new_url + '#' + parsed.fragment
#     return new_url


def to_query_string(query_dict: dict[str, list[str]]) -> str:
    return urllib.parse.urlencode(
        [(key, value) for key, values in query_dict.items() for value in values]
    )


def to_query_dict(query_string: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(query_string)
