"""夭夭影社 · Pydantic 数据模型（请求 / 响应）。

严格对齐 docs/ARCHITECTURE.md 第 2.2 节数据库表字段与第 2.5 节 API 路由总表。
不新增业务字段；仅提供类型化包装。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ScrapeStatus(str, Enum):
    """videos.scrape_status 取值（ARCHITECTURE.md 2.2.1）。"""

    PENDING = "pending"
    MATCHED = "matched"
    FAILED = "failed"
    MANUAL = "manual"


class BangouType(str, Enum):
    """番号类型（ARCHITECTURE.md 2.4.3）。"""

    CENSORED = "censored"
    UNCENSORED = "uncensored"
    FC2 = "fc2"


class TagCategory(str, Enum):
    """tags.category 取值（ARCHITECTURE.md 2.2.5）。"""

    GENRE = "genre"
    THEME = "theme"
    FEATURE = "feature"

class VideoCategory(str, Enum):
    """videos.category 取值（二级分类导航）。"""

    MOVIE = "movie"
    C_DRAMA = "c_drama"
    K_DRAMA = "k_drama"
    W_DRAMA = "w_drama"
    LOCAL = "local"
    OTHER = "other"


class ORMModel(BaseModel):
    """统一配置：允许从 sqlite3.Row 转换、忽略未知字段。"""

    model_config = ConfigDict(from_attributes=True, extra="ignore")


# ---------------------------------------------------------------------------
# videos
# ---------------------------------------------------------------------------
class VideoBase(ORMModel):
    title: Optional[str] = None
    original_title: Optional[str] = None
    sort_title: Optional[str] = None
    bangou: Optional[str] = None
    bangou_norm: Optional[str] = None
    series_id: Optional[str] = None
    studio: Optional[str] = None
    director: Optional[str] = None
    release_date: Optional[str] = None
    duration: Optional[int] = 0
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None
    bitrate: Optional[int] = None
    poster_path: Optional[str] = None
    thumb_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    plot: Optional[str] = None
    rating: Optional[float] = None
    scrape_status: ScrapeStatus = ScrapeStatus.PENDING
    scrape_source: Optional[str] = None
    nfo_path: Optional[str] = None
    play_count: int = 0
    last_played: Optional[str] = None
    is_favorite: int = 0
    is_hidden: int = 0
    # 二级分类：movie / c_drama / k_drama / w_drama / local（'other' 为未归类占位）
    category: Optional[str] = "other"
    # 聚合展示模式（group_series=true）附加字段：剧集聚合卡片标记与分集总数
    is_series: bool = False
    episode_count: int = 1


class VideoCreate(ORMModel):
    """新建影片（扫描器 / 手工导入）。"""

    title: str
    file_path: str
    file_name: str
    file_size: int = 0
    duration: Optional[int] = 0
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None
    bitrate: Optional[int] = None
    bangou: Optional[str] = None
    bangou_norm: Optional[str] = None
    scrape_status: ScrapeStatus = ScrapeStatus.PENDING
    nfo_path: Optional[str] = None


class VideoUpdate(ORMModel):
    """更新影片元数据（ARCHITECTURE.md 2.5.1 PUT /videos/{id}）。"""

    title: Optional[str] = None
    original_title: Optional[str] = None
    sort_title: Optional[str] = None
    bangou: Optional[str] = None
    bangou_norm: Optional[str] = None
    series_id: Optional[str] = None
    studio: Optional[str] = None
    director: Optional[str] = None
    release_date: Optional[str] = None
    poster_path: Optional[str] = None
    thumb_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    plot: Optional[str] = None
    rating: Optional[float] = None
    scrape_status: Optional[ScrapeStatus] = None
    scrape_source: Optional[str] = None
    is_favorite: Optional[int] = None
    is_hidden: Optional[int] = None


class VideoOut(VideoBase):
    id: str
    file_path: str
    file_name: str
    file_size: int = 0
    date_added: Optional[str] = None
    scrape_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VideoDetail(VideoOut):
    """影片详情（含演员、标签、续播点，ARCHITECTURE.md 2.5.1）。"""

    actors: list["ActorOut"] = Field(default_factory=list)
    tags: list["TagOut"] = Field(default_factory=list)
    series: Optional["SeriesOut"] = None
    resume_position: int = 0
    resume_progress: float = 0.0


# ---------------------------------------------------------------------------
# series / actors / tags
# ---------------------------------------------------------------------------
class SeriesOut(ORMModel):
    id: str
    name: str
    name_ja: Optional[str] = None
    description: Optional[str] = None
    poster_path: Optional[str] = None
    video_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ActorOut(ORMModel):
    id: str
    name: str
    name_ja: Optional[str] = None
    aliases: Optional[Any] = None
    photo_path: Optional[str] = None
    birth_date: Optional[str] = None
    measurements: Optional[str] = None
    cup_size: Optional[str] = None
    height: Optional[int] = None
    nationality: Optional[str] = None
    video_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ActorDetail(ActorOut):
    videos: list[VideoOut] = Field(default_factory=list)


class TagOut(ORMModel):
    id: str
    name: str
    name_ja: Optional[str] = None
    category: TagCategory = TagCategory.GENRE
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# watch_history
# ---------------------------------------------------------------------------
class WatchHistoryCreate(ORMModel):
    """上报播放进度（ARCHITECTURE.md 2.5.3 POST /history）。"""

    video_id: str
    position: int = 0
    duration: int = 0
    device: Optional[str] = None


class WatchHistoryOut(ORMModel):
    id: str
    video_id: str
    position: int = 0
    duration: int = 0
    progress: float = 0.0
    completed: int = 0
    watched_at: Optional[str] = None
    device: Optional[str] = None


class ResumeRecord(ORMModel):
    """续播点记录（含影片摘要）。"""

    video: VideoOut
    position: int = 0
    duration: int = 0
    progress: float = 0.0
    watched_at: Optional[str] = None


# ---------------------------------------------------------------------------
# scraper_cache
# ---------------------------------------------------------------------------
class ScraperCacheOut(ORMModel):
    id: str
    bangou_norm: str
    source: str
    raw_json: str
    fetched_at: Optional[str] = None
    expires_at: Optional[str] = None


# ---------------------------------------------------------------------------
# 通用响应
# ---------------------------------------------------------------------------
class Pagination(ORMModel):
    page: int = 1
    per_page: int = 30
    total: int = 0
    total_pages: int = 0


class VideoListResponse(ORMModel):
    items: list[VideoOut] = Field(default_factory=list)
    pagination: Pagination


class Paginated(ORMModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    pagination: Pagination


class VideoStats(ORMModel):
    total: int = 0
    total_size: int = 0
    favorites: int = 0
    watched: int = 0
    pending: int = 0
    matched: int = 0
    failed: int = 0
    manual: int = 0


class SystemStats(ORMModel):
    videos: VideoStats
    series: int = 0
    actors: int = 0
    tags: int = 0
    history_records: int = 0
    media_root: str
    database_path: str
    media_root_exists: bool = False


class HealthResponse(ORMModel):
    status: str = "ok"
    database: str = "unknown"
    version: str = "1.0.0"


class MessageResponse(ORMModel):
    success: bool = True
    message: str = ""


class ScanResult(ORMModel):
    """扫描结果。所有字段均带默认值，保证并发 / 空结果时也能安全序列化。"""

    discovered: int = 0
    added: int = 0
    skipped: int = 0
    missing: int = 0
    media_root: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


VideoDetail.model_rebuild()
