"""云端媒体反向代理流单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.api.stream import (
    build_cloud_stream_response,
    open_cloud_upstream,
    proxy_upstream_iterator,
)

RAW_URL = "http://192.168.31.235:5244/d/movie.mp4?sign=abc"


def make_upstream(status: int, headers: dict[str, str], chunks: list[bytes]) -> httpx.Response:
    async def body():
        for chunk in chunks:
            yield chunk

    response = httpx.Response(status, headers=headers, stream=httpx.AsyncByteStream())
    response.aiter_bytes = lambda chunk_size=None: body()  # type: ignore[method-assign]
    response.aclose = AsyncMock()  # type: ignore[method-assign]
    return response


class OpenCloudUpstreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_range_header_and_streams(self) -> None:
        upstream = make_upstream(206, {"content-type": "video/mp4"}, [b"abc"])
        client = MagicMock()
        client.send = AsyncMock(return_value=upstream)

        with patch("server.api.stream.get_client", AsyncMock(return_value=client)):
            result = await open_cloud_upstream(RAW_URL, "bytes=0-")

        self.assertIs(result, upstream)
        sent_request = client.send.call_args.args[0]
        self.assertEqual(sent_request.headers["Range"], "bytes=0-")
        self.assertEqual(client.send.call_args.kwargs, {"stream": True})

    async def test_upstream_error_status_maps_to_502(self) -> None:
        upstream = make_upstream(403, {}, [])
        client = MagicMock()
        client.send = AsyncMock(return_value=upstream)

        with patch("server.api.stream.get_client", AsyncMock(return_value=client)):
            with self.assertRaises(HTTPException) as ctx:
                await open_cloud_upstream(RAW_URL, None)

        self.assertEqual(ctx.exception.status_code, 502)
        upstream.aclose.assert_awaited()

    async def test_timeout_maps_to_504(self) -> None:
        client = MagicMock()
        client.send = AsyncMock(side_effect=httpx.TimeoutException("slow"))

        with patch("server.api.stream.get_client", AsyncMock(return_value=client)):
            with self.assertRaises(HTTPException) as ctx:
                await open_cloud_upstream(RAW_URL, "bytes=0-")

        self.assertEqual(ctx.exception.status_code, 504)


class BuildCloudStreamResponseTest(unittest.TestCase):
    def test_strips_attachment_and_keeps_media_headers(self) -> None:
        upstream = make_upstream(
            206,
            {
                "content-type": "video/mp4",
                "content-length": "1024",
                "content-range": "bytes 0-1023/4096",
                "content-disposition": 'attachment; filename="01~4K.mp4"',
                "server": "alist",
                "set-cookie": "x=1",
            },
            [],
        )

        response = build_cloud_stream_response(upstream, 206)

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 0-1023/4096")
        self.assertEqual(response.headers["content-length"], "1024")
        self.assertEqual(response.headers["content-disposition"], "inline")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertNotIn("set-cookie", response.headers)
        self.assertNotIn("server", response.headers)
        self.assertEqual(response.media_type, "video/mp4")


class ProxyIteratorTest(unittest.IsolatedAsyncioTestCase):
    async def test_yields_all_chunks_and_closes_upstream(self) -> None:
        upstream = make_upstream(200, {}, [b"ab", b"cd"])

        collected = [chunk async for chunk in proxy_upstream_iterator(upstream)]

        self.assertEqual(collected, [b"ab", b"cd"])
        upstream.aclose.assert_awaited()

    async def test_upstream_error_mid_stream_closes_quietly(self) -> None:
        async def broken():
            yield b"ab"
            raise httpx.ReadError("reset")

        upstream = make_upstream(200, {}, [])
        upstream.aiter_bytes = lambda chunk_size=None: broken()  # type: ignore[method-assign]

        collected = [chunk async for chunk in proxy_upstream_iterator(upstream)]

        self.assertEqual(collected, [b"ab"])
        upstream.aclose.assert_awaited()
