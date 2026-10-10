# 任务书：夭夭影社接入 Alist 媒体双轨与 302 直链微创改造

## 背景与定位
- 宿主机 Alist 容器已启动（地址 `http://192.168.31.235:5244`），已开启游客读取并挂载 `/百度网盘`。
- 夭夭影社后端需支持本地视频（206 分块切片）与云端视频（302 Redirect 至 Alist 提取的真实原画直链）。
- 严格遵循微创手术原则：不破坏既有单测，不重构无关模块。

## 改造明细

### 1. 配置管理 `server/config.py`
在文件末尾追加：
```python
# —— Alist 云端直链聚合集成 ——
ALIST_ENABLE: bool = os.getenv("ALIST_ENABLE", "true").lower() in ("true", "1", "yes")
ALIST_BASE_URL: str = os.getenv("ALIST_BASE_URL", "http://192.168.31.235:5244").rstrip("/")
ALIST_TOKEN: str = os.getenv("ALIST_TOKEN", "")
```

### 2. 数据库结构 `server/database.py`
1. `VIDEO_COLUMNS` 中追加允许写入字段：`"storage_type"`, `"cloud_fs_path"`。
2. 在 `Database.init_schema()` 中，建表后增加平滑迁移逻辑（检查 videos 表是否有 storage_type 列，没有则执行 ALTER TABLE）：
```python
        cols = {row["name"] for row in await self.fetchall("PRAGMA table_info(videos)")}
        if "storage_type" not in cols:
            await self.conn.execute("ALTER TABLE videos ADD COLUMN storage_type TEXT DEFAULT 'local'")
        if "cloud_fs_path" not in cols:
            await self.conn.execute("ALTER TABLE videos ADD COLUMN cloud_fs_path TEXT DEFAULT NULL")
        await self.conn.commit()
```

### 3. 流媒体核心 `server/api/stream.py`
重构 `stream_video` 接口：
1. 若 `video.get("storage_type") == "cloud"` 或 `video.get("cloud_fs_path")`:
   - 提取 `cloud_fs_path = video.get("cloud_fs_path")`
   - 向 `f"{config.ALIST_BASE_URL}/api/fs/get"` 发送 POST 请求：`{"path": cloud_fs_path, "password": ""}`
   - 从响应解析 `data.raw_url`。若获取失败抛出 HTTP 502。
   - 返回 `RedirectResponse(url=raw_url, status_code=302, headers={"Access-Control-Allow-Origin": "*"})`。
2. 否则（本地文件）：维持原有的 `file_iterator` + HTTP 206 Partial Content 切片逻辑 100% 不变。

### 4. 扫描器 `server/scraper/scanner.py`
在 `_scan_locked` 中增加对 Alist 的轻量遍历：
- 当 `config.ALIST_ENABLE` 为 True 时，调用 Alist API 遍历 `/百度网盘/电影` 与 `/百度网盘/电视剧`：
- 对发现的视频文件（后缀符合 `config.VIDEO_EXTS`）：
  - 构造 record：`id=str(uuid4())`, `title=stem`, `file_path=f"cloud://{virtual_path}"`, `file_name=fname`, `file_size=size`, `storage_type="cloud"`, `cloud_fs_path=virtual_path`。
  - 严禁调用 `ffprobe` 探测云端文件。
  - 同目录若有 `poster.jpg` / `cover.jpg`，写入 `poster_path`。
  - 若 `file_path` 已存在于数据库则跳过（更新海报），不存在则 `insert_video`。

## 验收铁律
1. 执行 `python3 -m py_compile server/config.py server/database.py server/api/stream.py server/scraper/scanner.py` 无任何语法报错。
2. 执行测试确保不影响原有功能。
