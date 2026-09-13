# 任务书：前端影视库「按部聚合展示」与分集选择体验

## 背景与目标
- 目前电视剧一集一张海报，导致海报墙被《庆余年》、《完美世界》上百集刷屏，翻看起来极其混乱。
- 后端已支持 `group_series=true` 参数：电影保持单张海报，电视剧按「整部剧」聚合成一张专属海报（带 `is_series=True`, `episode_count=N`），总数从 1973 骤降至极度清爽的 99 部！
- 现需将前端适配打通：默认按部聚合，点击剧集时优雅查看与选集播放！

## 改造清单

### 1. 前端 Store 与 API 适配（frontend/src/api/videos.ts 与 frontend/src/stores/video.ts）
- `VideoFilters` 增加 `groupSeries?: boolean`（默认 `true`）。
- `fetchVideos` 调用 `listVideos` 时携带 `group_series: filters.value.groupSeries ?? true`。

### 2. 详情页（frontend/src/views/VideoDetailView.vue）
- 当查看的视频是剧集分集（`series_id` 不为空）时：
  - 调用 `GET /api/series/{series_id}/episodes` 拉取该剧的所有分集列表。
  - 在详情页下方渲染极简白风格的「选集列表」（第 1 集、第 2 集、第 3 集……按方块或列表排列），点击任意分集直接切换或播放！

### 3. 构建前端产物
- 在宿主机或本地执行 `npm run build` 生成 `frontend/dist`。

## 验收
- 访问首页和片库，整面墙干净整洁，电影是单部，电视剧是一部一个海报卡片（角标标明共XX集）。
