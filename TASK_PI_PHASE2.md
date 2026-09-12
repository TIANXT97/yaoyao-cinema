# Phase 2 刮削引擎开发任务书（针对 DeepSeek 执刀）

## 绝对铁律纪律（违者重罚重做）
1. **严格阅读并遵循 docs/ARCHITECTURE.md 第 2.4 节（元数据刮削流水线）**：
   - 文件命名、模块路径、函数签名、类名必须完全与 ARCHITECTURE.md 一致！
   - 严禁凭空发明不存在的类名、方法名或字段！
2. **Phase 2 范围边界**：
   - 2.1 `server/scraper/bangou_parser.py`（番号与文件名正则解析，必须支持常规大厂字母-数字、FC2、无码系列三巨头、欧美大厂等各种复杂前缀后缀如 -C/-CD1）
   - 2.2 `server/scraper/sources/base.py`（ScraperSource 抽象基类，定义 search, get_detail 规范数据结构）
   - 2.3 `server/scraper/sources/nfo_source.py`（本地 NFO 解析器，支持 Kodi/Jellyfin 常见 XML 结构并提取标题、年份、导演、演员、标签等）
   - 2.4 `server/scraper/sources/javbus.py`、`javdb.py`、`airav.py`（主流网络数据源刮削实现，支持请求代理配置、User-Agent 轮换与反爬兜底）
   - 2.5 `server/scraper/image_processor.py`（图片处理：Pillow 库裁剪 2:3 纵向海报 poster、智能右侧/居中裁切保留主体、保存横版原图为 backdrop，图片压缩优化）
   - 2.6 `server/scraper/pipeline.py`（核心调度流水线：本地 NFO 优先 -> 提取番号 -> 级联网络源抓取 -> 缓存入库 scraper_cache -> 关联 actors/tags/series -> 下载处理海报 -> 更新 video 状态为 matched）
   - 2.7 完善 `server/api/scraper_api.py`：实现单片刮削接口 `POST /api/scraper/scrape/{video_id}` 与批量自动刮削任务接口
3. **严格自测验收**：
   - 编写完整的单测或验证脚本，验证番号提取准确率、本地 NFO 解析、图片裁切逻辑、流水线串通。
   - 所有 Python 文件必须通过 `python3 -m py_compile` 保证 0 语法错误。
