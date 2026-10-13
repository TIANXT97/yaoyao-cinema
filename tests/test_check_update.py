"""系统更新检查接口的缓存与回退逻辑单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from server.api import system


RELEASE = {
    "tag_name": "v1.0.5",
    "name": "v1.0.5",
    "body": "notes",
    "published_at": "2026-10-13T00:00:00Z",
    "assets": [
        {
            "name": "app.apk",
            "size": 123,
            "browser_download_url": "https://github.com/x/app.apk",
        }
    ],
}


def _fake_client(payload=None, error: Exception | None = None):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    client = MagicMock()
    if error is not None:
        client.get = AsyncMock(side_effect=error)
    else:
        client.get = AsyncMock(return_value=response)
    return client


class CheckUpdateTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system._update_cache = None
        system._update_cached_at = 0.0

    async def test_normalizes_release_and_builds_accelerated_url(self) -> None:
        client = _fake_client(RELEASE)
        with patch.object(system, "get_client", AsyncMock(return_value=client)):
            data = await system.check_update()

        self.assertEqual(data["versionName"], "1.0.5")
        self.assertEqual(data["apkAsset"]["name"], "app.apk")
        self.assertEqual(
            data["apkAsset"]["acceleratedUrl"],
            "https://ghfast.top/https://github.com/x/app.apk",
        )

    async def test_second_call_hits_cache(self) -> None:
        client = _fake_client(RELEASE)
        with patch.object(system, "get_client", AsyncMock(return_value=client)):
            await system.check_update()
            await system.check_update()

        self.assertEqual(client.get.await_count, 1)

    async def test_upstream_failure_without_cache_raises_502(self) -> None:
        client = _fake_client(error=RuntimeError("rate limited"))
        with patch.object(system, "get_client", AsyncMock(return_value=client)):
            with self.assertRaises(HTTPException) as ctx:
                await system.check_update()

        self.assertEqual(ctx.exception.status_code, 502)

    async def test_upstream_failure_falls_back_to_stale_cache(self) -> None:
        ok_client = _fake_client(RELEASE)
        with patch.object(system, "get_client", AsyncMock(return_value=ok_client)):
            await system.check_update()

        system._update_cached_at = 0.0
        bad_client = _fake_client(error=RuntimeError("boom"))
        with patch.object(system, "get_client", AsyncMock(return_value=bad_client)):
            data = await system.check_update()

        self.assertEqual(data["versionName"], "1.0.5")


if __name__ == "__main__":
    unittest.main()
