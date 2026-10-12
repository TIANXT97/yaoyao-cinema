"""Alist 服务直链换取与缓存单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.alist_service import (
    clear_alist_cache,
    fetch_alist_raw_url,
)


class AlistServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        clear_alist_cache()

    async def test_fetch_raw_url_and_cache_hit(self) -> None:
        fake_response = AsyncMock()
        fake_response.raise_for_status = lambda: None
        fake_response.json = lambda: {
            "code": 200,
            "data": {"raw_url": "https://cdn.example.com/video.mp4?sign=123"},
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=fake_response)

        with patch("server.services.alist_service.get_client", return_value=mock_client):
            # 1. 首次请求：命中网络
            url1 = await fetch_alist_raw_url("/aliyun/movie.mp4")
            self.assertEqual(url1, "https://cdn.example.com/video.mp4?sign=123")
            self.assertEqual(mock_client.post.call_count, 1)

            # 2. 第二次请求：命中内存缓存，不发起网络请求
            url2 = await fetch_alist_raw_url("/aliyun/movie.mp4")
            self.assertEqual(url2, "https://cdn.example.com/video.mp4?sign=123")
            self.assertEqual(mock_client.post.call_count, 1)

    async def test_fetch_raw_url_timeout_raises(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))

        with patch("server.services.alist_service.get_client", return_value=mock_client):
            with self.assertRaises(httpx.TimeoutException):
                await fetch_alist_raw_url("/timeout/video.mp4")
