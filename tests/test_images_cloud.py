"""云端海报反向代理与本地磁盘缓存单元测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.api import images


class _FakeUpstream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamContext:
    def __init__(self, upstream: _FakeUpstream) -> None:
        self._upstream = upstream

    async def __aenter__(self) -> _FakeUpstream:
        return self._upstream

    async def __aexit__(self, *exc_info) -> bool:
        return False


class CloudPosterProxyTest(unittest.IsolatedAsyncioTestCase):
    FS_PATH = "/aliyun/电影/海报.jpg"
    CLOUD_URL = "cloud:///aliyun/电影/海报.jpg"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self._tmp.name) / "posters"
        cache_patch = patch.object(images, "CACHE_DIR", self.cache_dir)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def _mock_client(self, stream_mock: MagicMock) -> MagicMock:
        client = MagicMock()
        client.stream = stream_mock
        return client

    async def test_cache_miss_proxies_upstream_and_returns_200_binary(self) -> None:
        upstream = _FakeUpstream([b"jpeg-", b"bytes"])
        client = self._mock_client(MagicMock(return_value=_FakeStreamContext(upstream)))
        fetch = AsyncMock(return_value="https://cdn.example.com/poster.jpg?sign=1")

        with patch.object(images, "fetch_alist_raw_url", fetch), \
                patch.object(images, "get_client", AsyncMock(return_value=client)):
            response = await images._serve_cloud_poster(self.CLOUD_URL)

        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.headers["cache-control"], "public, max-age=604800, immutable")
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertTrue(response.headers["etag"])
        self.assertTrue(response.headers["last-modified"].endswith("GMT"))

        target = Path(response.path)
        self.assertEqual(target, self.cache_dir / images._cache_key(self.FS_PATH))
        self.assertEqual(target.read_bytes(), b"jpeg-bytes")
        fetch.assert_awaited_once_with(self.FS_PATH)
        client.stream.assert_called_once_with("GET", "https://cdn.example.com/poster.jpg?sign=1")

    async def test_cache_hit_skips_upstream(self) -> None:
        self.cache_dir.mkdir(parents=True)
        (self.cache_dir / images._cache_key(self.FS_PATH)).write_bytes(b"cached")
        fetch = AsyncMock()
        get_client = AsyncMock()

        with patch.object(images, "fetch_alist_raw_url", fetch), \
                patch.object(images, "get_client", get_client):
            response = await images._serve_cloud_poster(self.CLOUD_URL)

        self.assertEqual(response.status_code, 200)
        fetch.assert_not_awaited()
        get_client.assert_not_awaited()

    async def test_upstream_network_error_returns_404_and_leaves_no_partial_file(self) -> None:
        client = self._mock_client(MagicMock(side_effect=httpx.ConnectError("boom")))
        fetch = AsyncMock(return_value="https://cdn.example.com/poster.jpg")

        with patch.object(images, "fetch_alist_raw_url", fetch), \
                patch.object(images, "get_client", AsyncMock(return_value=client)):
            with self.assertRaises(HTTPException) as ctx:
                await images._serve_cloud_poster(self.CLOUD_URL)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(list(self.cache_dir.glob("*")), [])

    async def test_alist_timeout_returns_404(self) -> None:
        fetch = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch.object(images, "fetch_alist_raw_url", fetch):
            with self.assertRaises(HTTPException) as ctx:
                await images._serve_cloud_poster(self.CLOUD_URL)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse((self.cache_dir / images._cache_key(self.FS_PATH)).exists())

    async def test_empty_raw_url_returns_404(self) -> None:
        fetch = AsyncMock(return_value=None)

        with patch.object(images, "fetch_alist_raw_url", fetch):
            with self.assertRaises(HTTPException) as ctx:
                await images._serve_cloud_poster(self.CLOUD_URL)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_cloud_fs_path_and_cache_key(self) -> None:
        self.assertEqual(images._cloud_fs_path("cloud:///a/b.jpg"), "/a/b.jpg")
        self.assertEqual(images._cloud_fs_path("cloud://a/b.jpg"), "/a/b.jpg")
        self.assertEqual(images._cache_key("/a/b.jpg"), images._cache_key("/a/b.jpg"))
        self.assertNotEqual(images._cache_key("/a/b.jpg"), images._cache_key("/a/c.jpg"))
        self.assertEqual(len(images._cache_key("/a/b.jpg")), 64)


if __name__ == "__main__":
    unittest.main()
