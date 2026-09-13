# 任务书：夭夭影社云端海报代理与直通伺服

## 背景
- 网盘目录中已成功为各电影和电视剧下载了官方高清 `poster.jpg`。
- 云端视频的 `poster_path` 为 `cloud:///百度网盘/.../poster.jpg`。
- 当前 `/api/images/{path:path}` 与 `/api/poster/{video_id}` 只解析本地 `MEDIA_ROOT` 物理文件，遇到 `cloud://` 开头或云端海报时直接抛出 403/404。

## 改造清单

### 1. 完善图片接口 `server/api/images.py`
在 `get_image` 与 `get_video_poster` 中增加对 `cloud://` 协议海报的适配：
1. 若 `poster_path` 以 `cloud://` 开头：
   - 提取 Alist 内部路径：`fs_path = poster_path[len("cloud://"):]`
   - 向 Alist 请求该图片的下载直链：`POST f"{config.ALIST_BASE_URL}/api/fs/get"`，payload 为 `{"path": fs_path}`。
   - 若解析出 `raw_url`，直接返回 `RedirectResponse(url=raw_url, status_code=302, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"})`。
   - 若失败返回 404。
2. 本地物理海报：维持原有的 `FileResponse` 逻辑 100% 不变。

### 2. 完善扫描器 `server/scraper/scanner.py` 中的海报探测与更新
- 在 `_scan_alist_dir` 中，当递归扫描电视剧各集或电影时，确保：
  - 如果同级或上级目录包含 `poster.jpg`，则将视频的 `poster_path` 设置为 `cloud://{dir_with_poster}/poster.jpg`。
  - 对于同一电视剧下的所有分集，均自动继承该剧集目录下的 `poster.jpg`。

## 验收铁律
1. `python3 -m py_compile server/api/images.py server/scraper/scanner.py` 无任何语法报错。
2. 重启容器后，请求带有云端海报的 `GET http://127.0.0.1:9900/api/poster/{video_id}` 能正确返回 302 重定向至海报直链。
