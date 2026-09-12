"""夭夭影社 · Phase 2 刮削引擎验证脚本。

覆盖：

1. 番号提取准确率（常规大厂 / FC2 / 无码三巨头 / 欧美 / 复杂前后缀）；
2. 本地 NFO 解析与 NFO 生成回环；
3. 网络源 HTML 解析（JavBus / JavDB / Airav）；
4. 图片智能裁切（2:3 海报 / 16:9 backdrop）；
5. 流水线端到端串通（临时 SQLite + 假数据源 + 临时媒体目录）。

运行::

    /tmp/yyvenv/bin/python tests/test_scraper.py        # 推荐（含 aiosqlite）
    python3 tests/test_scraper.py                        # 无 aiosqlite 时自动跳过 DB 用例
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import config  # noqa: E402
from server.scraper import image_processor  # noqa: E402
from server.scraper.bangou_parser import normalize_bangou, parse_bangou  # noqa: E402
from server.scraper.sources.airav import AiravScraper  # noqa: E402
from server.scraper.sources.base import normalize_result  # noqa: E402
from server.scraper.sources.javbus import JavBusScraper  # noqa: E402
from server.scraper.sources.javdb import JavDBScraper  # noqa: E402
from server.scraper.sources.nfo_source import (  # noqa: E402
    build_nfo_xml,
    parse_nfo_file,
    parse_nfo_string,
)

try:  # aiosqlite 仅在完整环境（/tmp/yyvenv）提供
    import aiosqlite  # noqa: F401

    HAS_AIOSQLITE = True
except ImportError:  # pragma: no cover
    HAS_AIOSQLITE = False


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def make_landscape(path: Path, width: int = 900, height: int = 600) -> Path:
    """生成左侧暗、右侧亮的横版测试图（模拟人物在右的日式封面）。"""
    img = Image.new("RGB", (width, height), (10, 10, 10))
    draw = ImageDraw.Draw(img)
    draw.rectangle([width // 2, 0, width, height], fill=(230, 200, 160))
    # 加入纹理，避免纯色导致显著性算法退化
    for x in range(width // 2 + 10, width, 24):
        draw.line([(x, 0), (x, height)], fill=(190, 160, 120), width=3)
    img.save(path, "JPEG", quality=95)
    return path


def make_portrait(path: Path, width: int = 600, height: int = 600) -> Path:
    img = Image.new("RGB", (width, height), (30, 60, 90))
    ImageDraw.Draw(img).ellipse(
        [width // 2 - 80, height // 2 - 120, width // 2 + 80, height // 2 + 120],
        fill=(240, 220, 190),
    )
    img.save(path, "JPEG", quality=95)
    return path


def make_solid(path: Path, size: tuple[int, int], color=(120, 140, 160)) -> Path:
    Image.new("RGB", size, color).save(path, "JPEG", quality=95)
    return path


# ---------------------------------------------------------------------------
# 1. 番号解析
# ---------------------------------------------------------------------------


class BangouParserTest(unittest.TestCase):
    CASES: list[tuple[str, str | None, str | None]] = [
        ("SSIS-001.mp4", "SSIS-001", "censored"),
        ("ABP-123.mkv", "ABP-123", "censored"),
        ("SSIS001.mp4", "SSIS-001", "censored"),
        ("SSIS_001.avi", "SSIS-001", "censored"),
        ("CAWD-001-C.mp4", "CAWD-001", "censored"),
        ("SSIS-001-CD1.mp4", "SSIS-001", "censored"),
        ("[ThZu.Cc]SSIS-001-C.mp4", "SSIS-001", "censored"),
        ("HD-SSNI-123.part1.mkv", "SSNI-123", "censored"),
        ("1080P_x264_MIDE-123.mp4", "MIDE-123", "censored"),
        ("FC2-PPV-1234567.mp4", "FC2-PPV-1234567", "fc2"),
        ("FC2PPV_123456.mp4", "FC2-PPV-123456", "fc2"),
        ("FC2-1234567.mp4", "FC2-PPV-1234567", "fc2"),
        ("010120_001.mp4", "010120_001", "uncensored"),
        ("010120-001.mp4", "010120_001", "uncensored"),
        ("n1234.mp4", "N1234", "uncensored"),
        ("K1234.mp4", "K1234", "uncensored"),
        ("HEYZO-1234.mp4", "HEYZO-1234", "uncensored"),
        ("NHDTA-123.mp4", "NHDTA-123", "censored"),
        ("Brazzers.23.01.15.mp4", "BRAZZERS-23-01-15", "censored"),
        ("unknown_file.mp4", None, None),
        ("FHD_HD-1080.mp4", None, None),
    ]

    def test_parse_bangou_table(self) -> None:
        failures: list[str] = []
        for filename, expected_bangou, expected_type in self.CASES:
            parsed = parse_bangou(filename)
            if expected_bangou is None:
                if parsed is not None:
                    failures.append(f"{filename}: 期望 None，实际 {parsed}")
                continue
            if parsed is None:
                failures.append(f"{filename}: 期望 {expected_bangou}，实际 None")
                continue
            if parsed["bangou"] != expected_bangou:
                failures.append(
                    f"{filename}: 期望 {expected_bangou}，实际 {parsed['bangou']}"
                )
            if parsed["type"] != expected_type:
                failures.append(
                    f"{filename}: 期望类型 {expected_type}，实际 {parsed['type']}"
                )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_normalize(self) -> None:
        self.assertEqual(normalize_bangou("ssis-001"), "SSIS001")
        self.assertEqual(normalize_bangou("FC2-PPV_1234567"), "FC2PPV1234567")

    def test_accuracy_ratio(self) -> None:
        correct = sum(
            1
            for filename, expected, _ in self.CASES
            if (parse_bangou(filename) or {}).get("bangou") == expected
        )
        ratio = correct / len(self.CASES)
        self.assertGreaterEqual(ratio, 0.95, f"番号提取准确率仅 {ratio:.0%}")


# ---------------------------------------------------------------------------
# 2. NFO 解析 / 生成
# ---------------------------------------------------------------------------

NFO_SAMPLE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>SSIS-001 夕美しおん</title>
  <originaltitle>新人NO.1STYLE 夕美しおんAVデビュー</originaltitle>
  <sorttitle>SSIS-001</sorttitle>
  <num>SSIS-001</num>
  <studio>S1 NO.1 STYLE</studio>
  <director>キョウセイ</director>
  <year>2021</year>
  <premiered>2021-01-19</premiered>
  <plot>新人NO.1STYLE...</plot>
  <runtime>120</runtime>
  <rating>8.5</rating>
  <tag>巨乳</tag>
  <tag>新人</tag>
  <genre>巨乳</genre>
  <actor>
    <name>夕美しおん</name>
    <thumb>actors/yumi_shion.jpg</thumb>
  </actor>
  <set>
    <name>新人NO.1STYLE</name>
  </set>
  <art>
    <poster>poster.jpg</poster>
    <fanart>backdrop.jpg</fanart>
  </art>
</movie>
"""


class NfoParserTest(unittest.TestCase):
    def test_parse_string(self) -> None:
        data = parse_nfo_string(NFO_SAMPLE)
        self.assertEqual(data["title"], "SSIS-001 夕美しおん")
        self.assertEqual(data["original_title"], "新人NO.1STYLE 夕美しおんAVデビュー")
        self.assertEqual(data["bangou"], "SSIS-001")
        self.assertEqual(data["studio"], "S1 NO.1 STYLE")
        self.assertEqual(data["director"], "キョウセイ")
        self.assertEqual(data["release_date"], "2021-01-19")
        self.assertEqual(data["duration"], 120 * 60)
        self.assertEqual(data["rating"], "8.5")
        self.assertEqual(data["series"], "新人NO.1STYLE")
        self.assertIn("巨乳", data["tags"])
        self.assertIn("新人", data["tags"])
        self.assertEqual(data["actors"][0]["name"], "夕美しおん")
        self.assertEqual(data["poster_url"], "poster.jpg")
        self.assertEqual(data["backdrop_url"], "backdrop.jpg")

    def test_parse_file_and_local_art(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "poster.jpg").write_bytes(b"fake-poster")
            (base / "backdrop.jpg").write_bytes(b"fake-backdrop")
            nfo_path = base / "movie.nfo"
            nfo_path.write_text(NFO_SAMPLE, encoding="utf-8")

            data = parse_nfo_file(nfo_path)
            self.assertEqual(data["poster_local"], str((base / "poster.jpg").resolve()))
            self.assertEqual(
                data["backdrop_local"], str((base / "backdrop.jpg").resolve())
            )

    def test_build_roundtrip(self) -> None:
        video = {
            "id": "v1",
            "title": "SSIS-001 夕美しおん",
            "original_title": "新人NO.1STYLE",
            "bangou": "SSIS-001",
            "studio": "S1",
            "director": "キョウセイ",
            "release_date": "2021-01-19",
            "duration": 7200,
            "rating": 8.5,
            "plot": "剧情",
            "poster_path": "posters/v1.jpg",
            "backdrop_path": "backdrops/v1.jpg",
        }
        actors = [{"name": "夕美しおん", "photo_path": "actors/a.jpg"}]
        tags = [{"name": "巨乳"}, {"name": "新人"}]
        series = {"name": "新人NO.1STYLE"}

        xml_text = build_nfo_xml(video, actors=actors, tags=tags, series=series)
        parsed = parse_nfo_string(xml_text)
        self.assertEqual(parsed["title"], "SSIS-001 夕美しおん")
        self.assertEqual(parsed["bangou"], "SSIS-001")
        self.assertEqual(parsed["release_date"], "2021-01-19")
        self.assertEqual(parsed["rating"], "8.5")
        self.assertEqual(parsed["series"], "新人NO.1STYLE")
        self.assertEqual(parsed["actors"][0]["name"], "夕美しおん")
        self.assertIn("巨乳", parsed["tags"])
        self.assertEqual(parsed["poster_url"], "posters/v1.jpg")


# ---------------------------------------------------------------------------
# 3. 网络源 HTML 解析
# ---------------------------------------------------------------------------

JAVBUS_HTML = """<html><head>
<meta property="og:title" content="SSIS-001 夕美しおん - JavBus">
<meta property="og:image" content="https://cdn.example/cover.jpg">
</head><body>
<h3>SSIS-001 夕美しおん</h3>
<div class="info">
  <p><span class="header">識別碼:</span> SSIS-001</p>
  <p><span class="header">發行日期:</span> 2021-01-19</p>
  <p><span class="header">長度:</span> 120分鐘</p>
  <p><span class="header">導演:</span> <a href="/director/1">キョウセイ</a></p>
  <p><span class="header">製作商:</span> <a href="/studio/1">S1 NO.1 STYLE</a></p>
  <p><span class="header">系列:</span> <a href="/series/1">新人NO.1STYLE</a></p>
  <p><span class="header">類別:</span>
     <a class="genre" href="/genre/1">巨乳</a>
     <a class="genre" href="/genre/2">新人</a></p>
</div>
<a class="bigImage" href="https://cdn.example/cover.jpg">
  <img src="https://cdn.example/cover.jpg">
</a>
<div class="star-name"><a href="/star/1">夕美しおん</a></div>
<div class="sample-box"><img src="https://cdn.example/sample1.jpg"></div>
</body></html>
"""

JAVDB_HTML = """<html><head>
<meta property="og:image" content="https://cdn.example/cover.jpg">
</head><body>
<h2 class="title"><strong>SSIS-001 夕美しおん</strong></h2>
<div class="movie-panel-info">
  <div class="column"><span class="label">日期:</span> 2021-01-19</div>
  <div class="column"><span class="label">導演:</span><a href="/director/1">キョウセイ</a></div>
  <div class="column"><span class="label">片商:</span><a href="/studio/1">S1 NO.1 STYLE</a></div>
  <div class="column"><span class="label">系列:</span><a href="/series/1">新人NO.1STYLE</a></div>
  <div class="column"><span class="label">類別:</span><a class="genre" href="/tags?t=1">巨乳</a></div>
</div>
<span class="value">8.5</span>
<a href="/actors/abc">夕美しおん</a>
<div class="preview-images"><a href="https://cdn.example/preview1.jpg">预览</a></div>
</body></html>
"""

AIRAV_HTML = """<html><head>
<meta property="og:image" content="https://cdn.example/cover.jpg">
</head><body>
<script type="application/ld+json">
{
  "@type": "Movie",
  "name": "SSIS-001 夕美しおん",
  "alternateName": "新人NO.1STYLE",
  "description": "剧情简介",
  "datePublished": "2021-01-19",
  "director": {"name": "キョウセイ"},
  "productionCompany": {"name": "S1 NO.1 STYLE"},
  "genre": ["巨乳", "新人"],
  "actor": [{"name": "夕美しおん", "image": "https://cdn.example/actor.jpg"}],
  "aggregateRating": {"ratingValue": "8.5"},
  "image": "https://cdn.example/cover.jpg",
  "thumbnailUrl": "https://cdn.example/backdrop.jpg"
}
</script>
</body></html>
"""


class SourceParserTest(unittest.TestCase):
    def test_javbus_detail(self) -> None:
        data = JavBusScraper().parse_detail(JAVBUS_HTML)
        self.assertEqual(data["title"], "SSIS-001 夕美しおん")
        self.assertEqual(data["release_date"], "2021-01-19")
        self.assertEqual(data["director"], "キョウセイ")
        self.assertEqual(data["studio"], "S1 NO.1 STYLE")
        self.assertEqual(data["series"], "新人NO.1STYLE")
        self.assertEqual(data["poster_url"], "https://cdn.example/cover.jpg")
        self.assertEqual(data["backdrop_url"], "https://cdn.example/sample1.jpg")
        self.assertIn("巨乳", data["tags"])
        self.assertEqual(data["actors"][0]["name"], "夕美しおん")

    def test_javbus_uncensored_name(self) -> None:
        self.assertEqual(JavBusScraper(uncensored=True).name, "javbus_uncensored")

    def test_javdb_detail(self) -> None:
        data = JavDBScraper().parse_detail(JAVDB_HTML)
        self.assertIn("SSIS-001", data["title"])
        self.assertEqual(data["release_date"], "2021-01-19")
        self.assertEqual(data["rating"], 8.5)
        self.assertEqual(data["poster_url"], "https://cdn.example/cover.jpg")
        self.assertEqual(data["backdrop_url"], "https://cdn.example/preview1.jpg")
        self.assertIn("巨乳", data["tags"])
        self.assertEqual(data["actors"][0]["name"], "夕美しおん")

    def test_airav_jsonld(self) -> None:
        data = AiravScraper().parse_detail(AIRAV_HTML)
        self.assertEqual(data["title"], "SSIS-001 夕美しおん")
        self.assertEqual(data["release_date"], "2021-01-19")
        self.assertEqual(data["director"], "キョウセイ")
        self.assertEqual(data["studio"], "S1 NO.1 STYLE")
        self.assertEqual(data["rating"], 8.5)
        self.assertIn("巨乳", data["tags"])
        self.assertEqual(data["actors"][0]["name"], "夕美しおん")
        self.assertEqual(data["poster_url"], "https://cdn.example/cover.jpg")
        self.assertEqual(data["backdrop_url"], "https://cdn.example/backdrop.jpg")

    def test_normalize_result(self) -> None:
        data = normalize_result({"title": "  X  ", "tags": "a,b", "rating": 85})
        self.assertEqual(data["title"], "X")
        self.assertEqual(data["tags"], ["a", "b"])
        self.assertEqual(data["rating"], 8.5)
        self.assertEqual(len(data), len(normalize_result({})))


# ---------------------------------------------------------------------------
# 4. 图片处理
# ---------------------------------------------------------------------------


class ImageProcessorTest(unittest.TestCase):
    def test_landscape_smart_crop_prefers_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_landscape(Path(tmp) / "cover.jpg")
            img = image_processor.open_image(path)
            cropped = image_processor.crop_to_ratio(img, 2 / 3)
            self.assertEqual(cropped.size, (400, 600))

            stat = ImageStat.Stat(cropped.convert("L"))
            mean = stat.mean[0]
            # 右侧亮区被保留：平均亮度显著高于整图
            whole_mean = ImageStat.Stat(img.convert("L")).mean[0]
            self.assertGreater(mean, whole_mean)

    def test_portrait_center_crop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_portrait(Path(tmp) / "p.jpg", 600, 600)
            img = image_processor.open_image(path)
            cropped = image_processor.crop_poster(img)
            self.assertEqual(cropped.size, (400, 600))

    def test_crop_backdrop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_solid(Path(tmp) / "b.jpg", (1000, 1000))
            img = image_processor.open_image(path)
            cropped = image_processor.crop_backdrop(img)
            self.assertAlmostEqual(cropped.size[0] / cropped.size[1], 16 / 9, places=2)

    def test_save_poster_and_backdrop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_media(Path(tmp))
            try:
                path = make_landscape(Path(tmp) / "cover.jpg")
                img = image_processor.open_image(path)
                poster_rel = image_processor.save_poster(img, "vid1")
                backdrop_rel, thumb_rel = image_processor.save_backdrop(img, "vid1")

                poster_abs = config.MEDIA_ROOT / poster_rel
                backdrop_abs = config.MEDIA_ROOT / backdrop_rel
                thumb_abs = config.MEDIA_ROOT / thumb_rel

                self.assertTrue(poster_abs.is_file())
                self.assertTrue(backdrop_abs.is_file())
                self.assertTrue(thumb_abs.is_file())
                with Image.open(poster_abs) as p:
                    self.assertEqual(p.size, (400, 600))
                with Image.open(backdrop_abs) as b:
                    self.assertEqual(b.size, (1280, 720))
                with Image.open(thumb_abs) as t:
                    self.assertEqual(t.size, (320, 180))
            finally:
                self._restore_media()

    # -- media patch helpers -------------------------------------------------
    _saved: dict[str, Path] = {}

    def _patch_media(self, root: Path) -> None:
        self._saved = {
            "MEDIA_ROOT": config.MEDIA_ROOT,
            "POSTERS_DIR": config.POSTERS_DIR,
            "BACKDROPS_DIR": config.BACKDROPS_DIR,
            "THUMBS_DIR": config.THUMBS_DIR,
            "ACTORS_DIR": config.ACTORS_DIR,
            "NFO_DIR": config.NFO_DIR,
        }
        config.MEDIA_ROOT = root
        config.POSTERS_DIR = root / "posters"
        config.BACKDROPS_DIR = root / "backdrops"
        config.THUMBS_DIR = root / "thumbs"
        config.ACTORS_DIR = root / "actors"
        config.NFO_DIR = root / "nfo"

    def _restore_media(self) -> None:
        for key, value in self._saved.items():
            setattr(config, key, value)


class ImageAsyncTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = {
            "MEDIA_ROOT": config.MEDIA_ROOT,
            "POSTERS_DIR": config.POSTERS_DIR,
            "BACKDROPS_DIR": config.BACKDROPS_DIR,
            "THUMBS_DIR": config.THUMBS_DIR,
            "ACTORS_DIR": config.ACTORS_DIR,
            "NFO_DIR": config.NFO_DIR,
        }
        root = Path(self._tmp.name)
        config.MEDIA_ROOT = root
        config.POSTERS_DIR = root / "posters"
        config.BACKDROPS_DIR = root / "backdrops"
        config.THUMBS_DIR = root / "thumbs"
        config.ACTORS_DIR = root / "actors"
        config.NFO_DIR = root / "nfo"

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            setattr(config, key, value)
        self._tmp.cleanup()

    async def test_download_and_crop_poster_local(self) -> None:
        root = Path(self._tmp.name)
        source = make_landscape(root / "raw.jpg")
        rel = await image_processor.download_and_crop_poster(source, "vid-9")
        self.assertIsNotNone(rel)
        target = config.MEDIA_ROOT / rel
        self.assertTrue(target.is_file())
        with Image.open(target) as img:
            self.assertEqual(img.size, (400, 600))


# ---------------------------------------------------------------------------
# 5. 流水线端到端
# ---------------------------------------------------------------------------

FAKE_RESULT = {
    "title": "SSIS-001 测试标题",
    "original_title": "テスト",
    "release_date": "2021-01-19",
    "studio": "S1",
    "director": "監督",
    "actors": [{"name": "演员甲"}, {"name": "演员乙", "name_ja": "俳優乙"}],
    "tags": ["巨乳", "新人"],
    "plot": "剧情简介",
    "rating": 8.5,
    "series": "测试系列",
    "source": "fake",
}


@unittest.skipUnless(HAS_AIOSQLITE, "缺少 aiosqlite，跳过流水线端到端测试")
class PipelineTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from server.database import Database
        from server.scraper.pipeline import ScraperPipeline
        from server.scraper.sources.base import ScraperSource

        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._saved_config = {
            key: getattr(config, key)
            for key in (
                "MEDIA_ROOT",
                "POSTERS_DIR",
                "BACKDROPS_DIR",
                "THUMBS_DIR",
                "ACTORS_DIR",
                "NFO_DIR",
            )
        }
        config.MEDIA_ROOT = root / "media"
        config.POSTERS_DIR = config.MEDIA_ROOT / "posters"
        config.BACKDROPS_DIR = config.MEDIA_ROOT / "backdrops"
        config.THUMBS_DIR = config.MEDIA_ROOT / "thumbs"
        config.ACTORS_DIR = config.MEDIA_ROOT / "actors"
        config.NFO_DIR = config.MEDIA_ROOT / "nfo"
        for directory in (
            config.MEDIA_ROOT,
            config.POSTERS_DIR,
            config.BACKDROPS_DIR,
            config.THUMBS_DIR,
            config.ACTORS_DIR,
            config.NFO_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.poster_source = make_landscape(config.MEDIA_ROOT / "raw_cover.jpg")
        self.backdrop_source = make_solid(
            config.MEDIA_ROOT / "raw_backdrop.jpg", (1280, 720)
        )

        class FakeSource(ScraperSource):
            name = "fake"
            display_name = "Fake"
            base_url = "https://fake.local"
            priority = 1

            def __init__(self, poster: Path, backdrop: Path) -> None:
                super().__init__()
                self._poster = poster
                self._backdrop = backdrop
                self.calls = 0

            async def search(self, query: str):
                return []

            async def get_detail(self, identifier: str):
                self.calls += 1
                return {
                    **FAKE_RESULT,
                    "poster_url": str(self._poster),
                    "backdrop_url": str(self._backdrop),
                }

        self.fake = FakeSource(self.poster_source, self.backdrop_source)
        self.db = Database(str(config.MEDIA_ROOT / "test.db"))
        await self.db.connect()
        await self.db.init_schema()
        self.pipeline = ScraperPipeline(
            database=self.db,
            sources={
                "censored": [self.fake],
                "uncensored": [self.fake],
                "fc2": [self.fake],
            },
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        for key, value in self._saved_config.items():
            setattr(config, key, value)
        self._tmp.cleanup()

    async def _insert_video(self, file_name: str = "SSIS-001.mp4") -> str:
        video_path = config.MEDIA_ROOT / file_name
        video_path.write_bytes(b"fake-video")
        video_id = str(uuid4())
        await self.db.insert_video(
            {
                "id": video_id,
                "title": file_name,
                "file_path": str(video_path),
                "file_name": file_name,
                "file_size": 10,
                "scrape_status": "pending",
            }
        )
        return video_id

    async def test_scrape_video_end_to_end(self) -> None:
        video_id = await self._insert_video()

        result = await self.pipeline.scrape_video(video_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["bangou"], "SSIS-001")
        self.assertEqual(result["source"], "fake")

        video = await self.db.get_video(video_id)
        self.assertEqual(video["scrape_status"], "matched")
        self.assertEqual(video["title"], FAKE_RESULT["title"])
        self.assertEqual(video["studio"], "S1")
        self.assertEqual(video["bangou_norm"], "SSIS001")
        self.assertTrue(video["poster_path"])
        self.assertTrue(video["backdrop_path"])
        self.assertTrue((config.MEDIA_ROOT / video["poster_path"]).is_file())
        self.assertTrue((config.MEDIA_ROOT / video["backdrop_path"]).is_file())
        self.assertIsNotNone(video["series_id"])
        self.assertTrue(video["nfo_path"])

        actor_count = await self.db.fetchvalue("SELECT COUNT(*) FROM actors")
        tag_count = await self.db.fetchvalue("SELECT COUNT(*) FROM tags")
        link_count = await self.db.fetchvalue("SELECT COUNT(*) FROM video_actors")
        self.assertEqual(actor_count, 2)
        self.assertEqual(tag_count, 2)
        self.assertEqual(link_count, 2)

        cache = await self.db.get_scraper_cache("SSIS001")
        self.assertIsNotNone(cache)
        self.assertEqual(cache["source"], "fake")

        # NFO 文件确实生成
        self.assertTrue(Path(video["nfo_path"]).is_file())

    async def test_cache_hit_avoids_second_fetch(self) -> None:
        video_id = await self._insert_video()
        await self.pipeline.scrape_video(video_id)
        calls_after_first = self.fake.calls

        # 第二次直接走缓存
        cached = await self.pipeline.scrape("SSIS-001", "SSIS001", "censored")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["title"], FAKE_RESULT["title"])
        self.assertEqual(self.fake.calls, calls_after_first)

    async def test_scrape_all(self) -> None:
        await self._insert_video("SSIS-001.mp4")
        await self._insert_video("ABP-123.mp4")
        summary = await self.pipeline.scrape_all()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["matched"], 2)
        self.assertEqual(summary["failed"], 0)

    async def test_nfo_priority_over_network(self) -> None:
        video_id = await self._insert_video("NFO-001.mp4")
        nfo_path = config.MEDIA_ROOT / "NFO-001.nfo"
        nfo_path.write_text(
            "<?xml version='1.0'?><movie><title>本地优先</title>"
            "<num>NFO-001</num><actor><name>本地演员</name></actor></movie>",
            encoding="utf-8",
        )
        await self.db.update_video(video_id, {"nfo_path": str(nfo_path)})

        result = await self.pipeline.scrape_video(video_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["source"], "nfo")
        video = await self.db.get_video(video_id)
        self.assertEqual(video["title"], "本地优先")
        # 未触发网络源
        self.assertEqual(self.fake.calls, 0)


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for test_class in (
        BangouParserTest,
        NfoParserTest,
        SourceParserTest,
        ImageProcessorTest,
        ImageAsyncTest,
        PipelineTest,
    ):
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
