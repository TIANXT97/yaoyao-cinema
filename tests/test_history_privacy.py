"""私房隔离、观看历史全库封顶 5 条与续播进度字段的单元测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.database import Database
from server.services import history_service, video_service


class PrivacyAndHistoryCapTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self._tmp.name) / "test.db"))
        await self.db.connect()
        await self.db.init_schema()

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self._tmp.cleanup()

    async def _add_video(self, title: str, category: str) -> str:
        video_id = str(uuid4())
        await self.db.insert_video(
            {
                "id": video_id,
                "title": title,
                "file_path": f"/fake/{video_id}.mp4",
                "file_name": f"{video_id}.mp4",
                "category": category,
                "duration": 3600,
            }
        )
        return video_id

    async def test_default_listing_hides_local_category(self) -> None:
        await self._add_video("公共影片", "movie")
        private_id = await self._add_video("私房影片", "local")

        items, total = await video_service.list_videos(self.db)
        ids = {item["id"] for item in items}
        self.assertNotIn(private_id, ids)
        self.assertEqual(total, 1)

    async def test_all_and_empty_category_hide_local(self) -> None:
        await self._add_video("公共影片", "movie")
        await self._add_video("私房影片", "local")

        for category in ("all", "", None):
            _, total = await video_service.list_videos(self.db, category=category)
            self.assertEqual(total, 1, category)

    async def test_explicit_local_category_returns_private_only(self) -> None:
        await self._add_video("公共影片", "movie")
        private_id = await self._add_video("私房影片", "local")

        items, total = await video_service.list_videos(self.db, category="local")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["id"], private_id)

    async def test_category_summary_excludes_local_from_all(self) -> None:
        await self._add_video("公共影片", "movie")
        await self._add_video("私房影片", "local")

        summary = await video_service.get_category_summary(self.db)
        self.assertEqual(summary["all"], 1)
        self.assertEqual(summary["local"], 1)

    async def test_list_exposes_resume_progress(self) -> None:
        video_id = await self._add_video("公共影片", "movie")
        await history_service.report_progress(
            self.db, video_id=video_id, position=1800_000, duration=3600_000
        )

        items, _ = await video_service.list_videos(self.db)
        self.assertAlmostEqual(items[0]["resume_progress"], 0.5)

    async def test_history_is_capped_globally_at_five(self) -> None:
        video_ids = [await self._add_video(f"影片{i}", "movie") for i in range(7)]
        for video_id in video_ids:
            await history_service.report_progress(
                self.db, video_id=video_id, position=1000, duration=3600_000
            )

        row = await self.db.fetchone("SELECT COUNT(*) AS n FROM watch_history")
        self.assertEqual(int(row["n"]), 5)

    async def test_recent_excludes_local_and_caps_at_five(self) -> None:
        public_ids = [await self._add_video(f"公共{i}", "movie") for i in range(3)]
        private_id = await self._add_video("私房", "local")
        for video_id in public_ids + [private_id]:
            await history_service.report_progress(
                self.db, video_id=video_id, position=1000, duration=3600_000
            )

        records = await history_service.get_recent(self.db, limit=50)
        self.assertLessEqual(len(records), 5)
        self.assertNotIn(private_id, {r["video_id"] for r in records})


if __name__ == "__main__":
    unittest.main()
