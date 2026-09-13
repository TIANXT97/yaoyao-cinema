# 《夭夭影社 × Alist 云端直链全链路融合架构方案书》

**文档标识**：YY-ARCH-2025-004  
**密级**：内部落地核心工程标准  
**架构责任人**：首席系统架构师  
**协同对象**：TIAN（系统所有者）、夭夭（贴身大管家）  
**执行工兵**：Pi（后端/基础设施工程实现）

---

## 1. 总体架构与数据流转拓扑

本方案旨在实现**本地私家影库**与**云端网盘影视库**的平滑双轨并存。针对云端媒体，彻底摒弃宿主机代理中转（Proxy Stream）、本地转码（Transcode）及本地磁盘缓存，达成**宿主零 CPU 占用、零硬盘 I/O 磨损、零宿主上行带宽消耗**的原画直出。

### 1.1 全链路拓扑图

```text
                               +--------------------------------------------+
                               |                 客户端集群                  |
                               |   (Vue3 PWA / 大屏 ExoPlayer / DLNA电视)    |
                               +---------------------+----------------------+
                                                     |
               [1] 元数据检索 / 目录浏览               | [4] 发起播放请求 GET /api/stream/{id}
                                                     v
+----------------------------------------------------+---------------------------------------+
| 宿主机 Docker (Host: 1000:1000)                                                            |
|                                                                                           |
|  +-------------------------------------+         +-------------------------------------+  |
|  |       夭夭影社 (yaoyao-cinema)       |         |             Alist 服务              |  |
|  |           (Port: 9900)              |         |            (Port: 5244)             |  |
|  |                                     |         |                                     |  |
|  |  +---------------+---------------+  | [2] 扫描 |  +-------------------------------+  |  |
|  |  | 本地扫描引擎  | 云端轻量嗅探器  +--+-------->+  Alist Core Engine            |  |  |
|  |  +-------+-------+-------+-------+  | 轻量索引 |  | (驱动: 百度网盘 / 夸克 / 分享) |  |  |
|  |          |               |          |         |  +---------------+---------------+  |  |
|  |          v               v          |         +------------------+------------------+  |
|  |  +-------------------------------+  |                            |                     |
|  |  | SQLite / 元数据库 (Video/File) |  |                            |                     |
|  |  | (标记 storage_type: local/cloud)| |                            |                     |
|  |  +---------------+---------------+  |                            |                     |
|  |                  |                  |                            |                     |
|  |                  | [5] 判断 storage_type == 'cloud'              |                     |
|  |                  +-----------------------------------------------+                     |
|  |                  | 请求 Alist 签名直链: POST /api/fs/get          |                     |
|  |                  |<----------------------------------------------+                     |
|  |                  | 返回带鉴权 raw_url                                                   |
|  |                  |                                                                     |
|  |  +---------------+---------------+                                                     |
|  |  | 流媒体分发核心 (stream.py)    |                                                     |
|  |  +---------------+---------------+                                                     |
|  |                  |                                                                     |
|  |                  | [6] 响应 HTTP 302 Found (Location: https://cdn.cloud.com/sign=xxx)  |
+--+------------------+---------------------------------------------------------------------+
                      |
                      | [7] 客户端自动跟随后续重定向 (Follow 302 Redirect)
                      v
+-------------------------------------------------------------------------------------------+
|                                公共云 / 大厂云端 CDN 机房                                   |
|                        (百度网盘机房 / 夸克 CDN / 对象存储底层直链)                          |
|                                                                                           |
|                 +-------------------------------------------------------+                 |
|                 | 客户端直接拉取 4K/原画视频流 (HTTP 206 Partial Content)   |                 |
|                 +-------------------------------------------------------+                 |
+-------------------------------------------------------------------------------------------+
```

### 1.2 三类流模型定义

1. **元数据流（Metadata Flow）**：影社定时/手动轻量化读取 Alist 文件树，将网盘路径建立虚拟索引入库，不下载任何视频体，不触发大厂风控。
2. **控制信令流（Control/Signaling Flow）**：客户端点击播放，向影社 `/api/stream/{id}` 请求视频。影社向 Alist 请求瞬时带签名的真实媒体直链，反手向客户端返回 `HTTP 302 Found`。
3. **媒体直链数据流（Direct Media Stream）**：客户端播放内核（ExoPlayer、AVPlayer、Web Video）接管 302 目标 URL，绕过 NAS 宿主机，直连云端网盘 CDN 机房拉取数 GB 甚至几十 GB 的原画视频。

---

## 2. 宿主机 Alist 部署规范

Alist 作为云端网盘底层驱动中间件，独立运行于宿主机 Docker 环境中，保障与夭夭影社容器互通，且权限严格受控。

### 2.1 Docker Compose 部署配置

在宿主机编排目录（例如 `/vol1/1000/docker/alist`）创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  alist:
    image: xhfe/alist:latest
    container_name: alist
    restart: unless-stopped
    user: "1000:1000"
    ports:
      - "5244:5244"
    volumes:
      - /vol1/1000/alist/data:/opt/alist/data
    environment:
      - PUID=1000
      - PGID=1000
      - UMASK=022
    networks:
      - cinema-net

networks:
  cinema-net:
    external: true
```

*注：若宿主机未创建外部网络 `cinema-net`，可执行 `docker network create cinema-net`，夭夭影社与 Alist 统一接入该网络，夭夭影社内部可直接通过 `http://alist:5244` 通信，亦可通过宿主机网关 `http://172.17.0.1:5244` 访问。*

### 2.2 基础初始化指引（工兵 Pi 执行）

1. **权限初始化**：
   ```bash
   mkdir -p /vol1/1000/alist/data
   chown -R 1000:1000 /vol1/1000/alist/data
   ```
2. **启动与管理员凭证设置**：
   ```bash
   docker compose up -d
   # 设置预设管理密码（以 CinemaAdmin2025 为例）
   docker exec -it alist ./alist admin set CinemaAdmin2025
   ```
3. **Alist 挂载配置规范**：
   - 登录 `http://<宿主机IP>:5244`。
   - 进入【管理】->【存储】->【添加】。
   - 挂载路径务必遵循标准化语义前缀：
     - 夸克网盘：`/quark`
     - 百度网盘：`/baidu`
     - 影视分享合集：`/shares`
   - **核心设置**：在对应存储的高级设置中，确保【WebDAV 策略】为 `302重定向` 或 `使用下载代理 URL 关闭`，提取真实直链。

---

## 3. 夭夭影社双轨挂载与路径映射设计

### 3.1 路径拓扑与存储解耦

统一容器内文件视角，保持极简白设计下单一媒体根目录的纯粹性，但目录逻辑分流：

| 介质类型 | 宿主机物理/逻辑源 | 夭夭影社容器内部映射路径 | 访问协议/机制 |
| :--- | :--- | :--- | :--- |
| **本地私家影库** | `/vol1/1000/私人影库` | `/media/local` | 物理 Volume 挂载 (ro) |
| **云端网盘影视** | Alist REST API / WebDAV | `/media/cloud` (虚拟标识) | API 交互，无实体挂载 |

夭夭影社 `docker-compose.yml` 调整如下：

```yaml
version: '3.8'

services:
  yaoyao-cinema:
    build: .
    container_name: yaoyao-cinema
    restart: unless-stopped
    user: "1000:1000"
    ports:
      - "9900:9900"
    environment:
      - MEDIA_LOCAL_ROOT=/media/local
      - ALIST_ENABLE=true
      - ALIST_BASE_URL=http://alist:5244
      - ALIST_TOKEN=your-alist-token-here  # Alist后门API Token或留空使用公开读取
    volumes:
      - /vol1/1000/私人影库:/media/local:ro
      - /vol1/1000/yaoyao/data:/app/data
    networks:
      - cinema-net
```

### 3.2 数据库 Schema 改造设计

在 SQLite 数据模型中新增存储属性，精准区分本地切片播放与云端直链嗅探：

```sql
-- 视频主表演进
ALTER TABLE videos ADD COLUMN storage_type VARCHAR(16) DEFAULT 'local'; -- 'local' | 'cloud'
ALTER TABLE videos ADD COLUMN cloud_fs_path VARCHAR(1024) DEFAULT NULL; -- Alist 内部路径，例如 '/quark/电影/奥本海默.mkv'
ALTER TABLE videos ADD COLUMN direct_url_cache TEXT DEFAULT NULL;        -- 瞬时缓存的直链 URL
ALTER TABLE videos ADD COLUMN direct_url_expire INTEGER DEFAULT 0;       -- 直链过期时间戳 (Unix Timestamp)
```

---

## 4. 核心改造点 1：扫描器与元数据绑定

网盘对高频探测和文件读取有严苛的 API 频控与风控限制（尤其是百度和夸克的防刷策略）。**严禁使用针对本地文件的 `os.walk` + `ffprobe` 直接去跑云端挂载点！**

### 4.1 轻量云端扫描器设计规范

1. **零探测原则**：
   - 扫描云端媒体时，不得调用 `ffprobe` 强行读取文件头部。
   - 基础元数据（分辨率、编码、时长）从文件名正则匹配，或在首次真实播放时由客户端回传修正。
2. **Alist 接口深度下钻控制**：
   - 使用 Alist `/api/fs/list` 接口获取目录。
   - 设定递归扫描并发度为单协程队列，目录切换间歇强制 `sleep(150ms)`，规避 API 429 Too Many Requests。
   - 开启 Alist 内部缓存（`refresh=false`），默认优先取 Alist 缓存索引。

### 4.2 扫描策略代码实现架构

```python
# server/services/cloud_scanner.py
import asyncio
import httpx
import logging
from typing import List, Dict, Any
from server.config import settings

logger = logging.getLogger("yaoyao.scanner.cloud")

class AlistScanner:
    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": token} if token else {}

    async def list_files(self, path: str = "/", refresh: bool = False) -> List[Dict[str, Any]]:
        """调用 Alist API 获取文件列表，带防风控延迟与容错"""
        url = f"{self.base_url}/api/fs/list"
        payload = {
            "path": path,
            "password": "",
            "page": 1,
            "per_page": 0,  # 0 为全部
            "refresh": refresh
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(url, json=payload, headers=self.headers)
                data = resp.json()
                if data.get("code") == 200:
                    return data.get("data", {}).get("content", []) or []
                logger.warning(f"Alist 读取目录失败 [{path}]: {data.get('message')}")
                return []
            except Exception as e:
                logger.error(f"连接 Alist 异常 [{path}]: {str(e)}")
                return []

    async def scan_recursive(self, current_path: str = "/"):
        """递归轻量索引网盘影视资产"""
        items = await self.list_files(current_path, refresh=False)
        for item in items:
            full_path = f"{current_path.rstrip('/')}/{item['name']}"
            if item.get("is_dir"):
                # 防风控缓冲
                await asyncio.sleep(0.2)
                await self.scan_recursive(full_path)
            else:
                # 校验扩展名并建立索引
                if item['name'].lower().endswith(('.mp4', '.mkv', '.mov', '.iso')):
                    await self._upsert_cloud_video(item, full_path)

    async def _upsert_cloud_video(self, item: Dict[str, Any], full_path: str):
        """入库逻辑：绑定 storage_type='cloud' 与真实 cloud_fs_path"""
        # 伪代码：在 DB 中插入或更新元数据
        # 此时只记录：标题、大小(item['size'])、修改时间、storage_type='cloud'、cloud_fs_path=full_path
        pass
```

---

## 5. 核心改造点 2：流媒体核心（server/api/stream.py）微创改造

实现本地与云端播放逻辑的彻底分流。改造遵循最小侵入式设计，原本地文件的 206 Partial Content 切片分块传输逻辑 100% 保留。

### 5.1 流媒体核心改造完整实现

```python
# server/api/stream.py
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, status, Header
from fastapi.responses import RedirectResponse, StreamingResponse
from server.config import settings
from server.models import Video  # 假设的 ORM 模型
from server.utils.local_stream import serve_local_range_stream  # 原有的 206 切片核心逻辑

router = APIRouter(prefix="/api/stream", tags=["stream"])

ALIST_BASE_URL = getattr(settings, "ALIST_BASE_URL", "http://alist:5244").rstrip("/")
ALIST_TOKEN = getattr(settings, "ALIST_TOKEN", "")

async def get_alist_raw_url(cloud_fs_path: str) -> str:
    """向 Alist 请求真实机房 302 签名重定向直链"""
    url = f"{ALIST_BASE_URL}/api/fs/get"
    payload = {
        "path": cloud_fs_path,
        "password": ""
    }
    headers = {"Authorization": ALIST_TOKEN} if ALIST_TOKEN else {}
    
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            res_data = resp.json()
            if res_data.get("code") == 200:
                raw_url = res_data.get("data", {}).get("raw_url")
                if raw_url:
                    return raw_url
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Alist 获取直链失败: {res_data.get('message')}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"无法连接 Alist 内部中继服务: {str(e)}"
            )

@router.get("/{video_id}")
async def stream_video(
    video_id: int,
    request: Request,
    range: str = Header(None)
):
    """
    双轨自适应流媒体入口：
    - storage_type == 'local' -> HTTP 206 本地极速字节切片
    - storage_type == 'cloud' -> HTTP 302 重定向至网盘机房原画直链
    """
    video = await Video.get_or_none(id=video_id)
    if not video:
        raise HTTPException(status_code=404, detail="影视资源不存在")

    # ================= 场景 A：本地私家影库 (HTTP 206 分块切片) =================
    if getattr(video, "storage_type", "local") == "local":
        local_path = video.local_file_path  # 映射在 /media/local 下的真实路径
        return await serve_local_range_stream(local_path, range_header=range)

    # ================= 场景 B：云端直链重定向 (HTTP 302 Redirect) =================
    elif video.storage_type == "cloud":
        if not video.cloud_fs_path:
            raise HTTPException(status_code=400, detail="云端路径未绑定，无法解析直链")

        # 检查带签名的 Direct URL 缓存是否有效 (保留 30 分钟安全阈值)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if video.direct_url_cache and video.direct_url_expire > (now_ts + 1800):
            target_url = video.direct_url_cache
        else:
            # 穿透 Alist 嗅探大厂真实落地签名直链
            target_url = await get_alist_raw_url(video.cloud_fs_path)
            # 异步写回缓存机制（假设直链有效期通常为 2~4 小时）
            video.direct_url_cache = target_url
            video.direct_url_expire = now_ts + 7200
            await video.save(update_fields=["direct_url_cache", "direct_url_expire"])

        # 核心：反手下发 302 重定向给客户端
        # 注意：此处使用 302 Found（非 301 永久，亦非部分旧客户端不支持的 307）
        return RedirectResponse(
            url=target_url,
            status_code=status.HTTP_302_FOUND,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )

    else:
        raise HTTPException(status_code=500, detail="未知存储类型，系统拒绝处理")
```

---

## 6. 核心改造点 3：移动端与大屏投屏兼容性保障

302 直链模式的最大技术陷阱是：**大厂防盗链 (Referer)、跨域保护 (CORS) 以及部分电视播放核心（如低版本 DLNA、ExoPlayer）对跨协议/跨域 302 重定向的主动阻断**。必须在协议层筑牢防线。

### 6.1 前端 Web / PWA 播放器兼容设计（防盗链剥离）

网盘直链（如夸克、百度底层 CDN）若检测到来自非官方域名的 `Referer`，会立即下发 `HTTP 403 Forbidden`。前端需全局剥离请求头：

1. **HTML 注入安全策略**：
   在前端 `index.html` 的 `<head>` 顶部注入：
   ```html
   <meta name="referrer" content="no-referrer" />
   ```
2. **Vue3 播放器组件（如 Artplayer / DPlayer / 原生 `<video>`）改造**：
   确保 video 标签明确携带属性：
   ```html
   <video
     id="yaoyao-player"
     playsinline
     webkit-playsinline
     x5-playsinline
     crossorigin="anonymous"
     referrerpolicy="no-referrer"
     :src="videoStreamUrl">
   </video>
   ```

### 6.2 投屏链路（AirPlay / DLNA）深度兼容

1. **DLNA 投屏协议特性**：
   - 电视端 DLNA Renderer（如海信、索尼、小米电视系统）在接收到控制点下发的 URL 时，通常会先发起一次 `HEAD` 请求获取媒体格式，再发起 `GET` 请求。
   - 夭夭影社的 `/api/stream/{id}` **必须支持 `HEAD` 请求方法的 302 重定向响应**。FastAPI 的 `@router.get` 默认包含 `HEAD`，但需确保没有拦截器截断 HEAD 请求。
   - 在向电视推送 DLNA DIDL-Lite XML 元数据时，`<res>` 标签必须明确带有规范的 `protocolInfo`，例如：
     ```xml
     <res protocolInfo="http-get:*:video/mp4:DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000">
       http://192.168.1.100:9900/api/stream/1024
     </res>
     ```
2. **AirPlay 投屏特性**：
   - iOS / Apple TV 的 AVPlayer 具备极其完备的 302 跟随能力，只要满足 `referrerpolicy="no-referrer"` 或直链自身不锁死 User-Agent，AirPlay 即可原生秒播。

### 6.3 Android 原生播放器（ExoPlayer / Media3）适配

若后续开发或已具备独立 Android TV / 移动客户端，原生 ExoPlayer 默认对“跨协议/跨域名重定向”有限制，工兵 Pi 需在客户端网络数据源工场中开启该项配置：

```kotlin
// Android 端 ExoPlayer 核心配置示范
val httpDataSourceFactory = DefaultHttpDataSource.Factory()
    .setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    .setConnectTimeoutMs(8000)
    .setReadTimeoutMs(15000)
    // 关键核心：必须显式开启跨协议/跨域 302 自动重定向追踪！
    .setAllowCrossProtocolRedirects(true)

val mediaSource = ProgressiveMediaSource.Factory(httpDataSourceFactory)
    .createMediaSource(MediaItem.fromUri("http://192.168.1.100:9900/api/stream/1024"))
```

---

## 7. 分阶段实施与验证清单

本清单专为工兵 Pi 制定，分阶段落地、步步设卡、明确交付验证物。

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                       PHASE 1: 基础设施与 Alist 中继就位                    │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      v
┌────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: 夭夭影社双轨重塑 (DB + API + 扫描)              │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      v
┌────────────────────────────────────────────────────────────────────────────┐
│                       PHASE 3: 全链路端到端闭环验证                         │
└────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: 基础设施与 Alist 就位
- [ ] **执行**：在宿主机编写 `/vol1/1000/alist/docker-compose.yml`，设置 `user: 1000:1000` 并挂载数据目录。
- [ ] **执行**：启动 Alist，配置并绑定【夸克网盘】或【百度网盘】账号。
- [ ] **验证交付物**：
  在宿主机终端执行 curl 测试接口直链生成：
  ```bash
  curl -s -X POST "http://127.0.0.1:5244/api/fs/get" \
       -H "Content-Type: application/json" \
       -d '{"path": "/quark/测试视频.mp4"}' | jq .
  ```
  **验收标准**：响应中 `code == 200` 且 `data.raw_url` 包含各大云盘 CDN 真实域名（如 `*.baidupcs.com` 或 `*.夸克CDN*`）。

### Phase 2: 后端直链与双轨改造
- [ ] **执行**：更新夭夭影社数据库 Schema，迁移增加 `storage_type`、`cloud_fs_path`、`direct_url_cache` 字段。
- [ ] **执行**：重构 `server/api/stream.py`，实现本地分块切片与云端 302 分流逻辑。
- [ ] **执行**：接入轻量级 `AlistScanner`，并对云端扫描动作加入 `sleep(0.2)` 速率限制。
- [ ] **验证交付物**：
  使用 `curl` 模拟客户端请求夭夭影社流媒体接口：
  ```bash
  curl -I "http://127.0.0.1:9900/api/stream/<cloud_video_id>"
  ```
  **验收标准**：响应头返回 `HTTP/1.1 302 Found`，`Location` 字段正确指示为云端网盘直链，且响应耗时 `< 300ms`。

### Phase 3: 影社端到端全链路实测验证
- [ ] **验证 1：Web 浏览器端无 Referer 原画秒播**
  - 使用 Chrome 访问夭夭影社，点击播放云端 4K MKV 影片。
  - 打开 Network 控制台，确认请求序列为：
    1. 请求 `GET /api/stream/{id}` -> 命中 `302 Found`。
    2. 浏览器跟随新地址向大厂 CDN 请求媒体流 -> 状态码 `206 Partial Content`。
  - 确认画面秒开、音频画质无压缩，宿主机 CPU 占用不超过 2%。
- [ ] **验证 2：移动端 PWA / iOS Safari 拖拽性能测试**
  - 进度条大幅度来回拖拽，验证 CDN 字节范围响应，无卡死断流现象。
- [ ] **验证 3：大屏投屏测试（AirPlay / DLNA）**
  - 将手机播放的云端影片投屏至客厅大屏（电视盒子/Apple TV）。
  - 观察电视端能否顺利解析并播放。如果黑屏，依据第 6 章重点排查 DLNA DIDL-Lite 头部及 User-Agent。
- [ ] **验证 4：双轨并发负载终测**
  - 客户端 A 播放本地私家影库文件（宿主机发生磁盘读取与 206 切片）。
  - 客户端 B 播放云端网盘 4K 影片（302 重定向脱手）。
  - 在宿主机执行 `htop`，监测指标：宿主机带宽仅产生客户端 A 的本地流量，客户端 B 流量完全脱离宿主机上行，CPU 维持在极低负载（轻量级微服务状态）。

---

### 架构师交付总结寄语

> **TIAN & 夭夭**：  
> 本方案通过引入 **Alist 嗅探层 + 夭夭影社 302 调度层 + 终端直连大厂 CDN** 的全链路架构，在保留夭夭影社纯白通透的轻量化单容器形态的同时，为影社注入了几乎无限容量的云端 4K 原画资源。  
> 宿主机从此免去了繁重的转码压力与巨额的磁盘消耗。请工兵 **Pi** 严格对照 Phase 1 至 Phase 3 清单执行，落地过程中若遇到大厂风控或特定型号电视 DLNA 握手阻断，参照第 6 章规范实施防御性参数微调即可。祝夭夭影社演进顺利！