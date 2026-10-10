# 任务书：夭夭影社影视库「剧集聚合 / 电影独立」与海报全覆盖

## 背景与痛点
1. 痛点 1：电视剧一集占一个海报，海报墙被《庆余年》、《完美世界》上百个单集刷屏，翻看起来极其混乱；一部剧集应作为一个聚合海报卡片展示。
2. 痛点 2：部分视频/剧集因路径多层（如包含 Season 1、中英文目录）导致海报丢失或为空。
3. 目标：
   - 电影（单独单部作品）：保持独立海报卡片展示。
   - 电视剧（多集剧集）：在片库/首页聚合为「一部剧对应一张专属海报封面」，点击进入剧集详情页后展示该剧下的所有分集列表供播放！

## 改造清单

### 1. 服务端接口支持「聚合展示模式」（server/services/video_service.py 与 server/api/videos.py）
- 在 `list_videos` 增加参数 `group_series: bool = False`：
  - 当 `group_series=True` 时：
    - 电影/无系列的独立视频（`series_id IS NULL`）：正常作为单项返回。
    - 属于某剧集的视频（`series_id IS NOT NULL`）：每个 `series_id` 只聚合出一条代表性记录（以该 series 的名称为 title，以 series.poster_path 为海报，携带 `is_series=True`, `episode_count=COUNT(*)`, `series_id`）。
  - 在 `server/api/videos.py` 中向 `GET /api/videos` 暴露 `group_series: bool = Query(False)`。

### 2. 补全扫描器中所有剧集分集的海报继承与 Series 绑定（server/scraper/scanner.py）
- 在 `_scan_alist_dir` 中，若扫描到 `/百度网盘/电视剧/{分类}/{剧名}/...`：
  - 提取 `{剧名}` 自动调用 `db.get_or_create_series(name=剧名)` 绑定 `series_id`。
  - 同级或上级目录的 `poster.jpg` 自动同步为 `series.poster_path` 以及分集的 `poster_path`。
- 确保无论是电视剧根目录还是 `Season 1/` 等子目录，所有分集 100% 绑定海报与系列 ID。

### 3. 剧集详情分集展示（server/api/series.py）
- 在 `server/api/series.py` 增加接口：
  - `GET /api/series/{series_id}/episodes`：返回该剧集下按集数自然排序的所有分集视频列表。

## 验收铁律
1. `python3 -m py_compile server/api/videos.py server/services/video_service.py server/api/series.py server/scraper/scanner.py` 通过。
2. 调用 `GET http://127.0.0.1:9900/api/videos?group_series=true` 实测返回的剧集不再是单集刷屏，而是按「整部剧」聚合，且带有海报。
