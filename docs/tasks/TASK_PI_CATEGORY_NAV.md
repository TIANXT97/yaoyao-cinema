# 任务书：夭夭影社全链路实现「二级分类导航」与「网盘变更静默自愈」

## 核心目标
1. 二级分类导航：在首页与片库顶部实现纯白极简通透风格的分类胶囊栏（全部、电影、国产剧、韩剧、欧美剧、私房），点击一键平滑过滤，且严格兼容 `group_series=True` 聚合展示。
2. 网盘变动自愈机制：新增或改动网盘资源时，前端与服务端能平滑感知与更新。

## 详细改造清单

### 1. 数据库定义 `server/database.py` 与模型 `server/models.py`
- `videos` 表追加字段：`category TEXT DEFAULT 'other'`，并增加索引 `idx_videos_category`。
- `VIDEO_COLUMNS` 中加入 `category`。
- `VideoBase` 模型中追加 `category: Optional[str] = 'other'`。
- 数据迁移推断规则：
  - 路径含 `/电影/` -> `movie` (电影)
  - 路径含 `/国产剧/` -> `c_drama` (国产剧)
  - 路径含 `/韩剧/` -> `k_drama` (韩剧)
  - 路径含 `/欧美剧/` -> `w_drama` (欧美剧)
  - 其余 -> `local` (私房)

### 2. 服务端 API 与业务层 `server/services/video_service.py` & `server/api/videos.py`
- `list_videos` 增加参数 `category: Optional[str] = None`。
  - 在 `where_sql` 中增加过滤 `v.category = ?`（若 `category` 不为空且不为 `'all'`）。
- 新增分类统计接口 `GET /api/videos/categories/summary`：
  - 返回各分类聚合后的部数：`{"all": 94, "movie": 29, "c_drama": 33, "k_drama": 27, "w_drama": 3, "local": 2}`。

### 3. 扫描器自愈与轻量同步 `server/scraper/scanner.py`
- 扫描新入库或更新时，自动调用 `detect_category(file_path)` 设置 `category`。
- 处理网盘变动：如果旧记录已不存在于网盘中（例如文件重命名或移动），`scan_media_library` 自动清理失效的旧记录（`missing`），保持数据库与网盘 100% 同步。

### 4. 前端组件与页面整合
- 创建组件 `frontend/src/components/browse/CategoryNav.vue`：
  - 纯白极简圆润胶囊条，含部数角标，支持横向平滑滚动，带 TV 遥控器与触控高亮。
- 在 `frontend/src/types/video.ts` 的 `VideoFilters` 中增加 `category?: string`。
- 在 `frontend/src/api/videos.ts` 中透传 `category` 参数，并新增 `getCategorySummary` API。
- 在 `frontend/src/views/HomeView.vue` 与 `frontend/src/views/LibraryView.vue` 顶部引入 `CategoryNav`，切换分类时刷新片库。

## 验收铁律
1. 后端 `python3 -m py_compile` 逐文件通过。
2. 前端 `npm run build` 构建成功。
