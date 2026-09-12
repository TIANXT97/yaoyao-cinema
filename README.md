# 夭夭影社（Yaoyao Cinema）

> 专为主人（TIAN）量身定制的私家极简、全平台四端大一统原画影院系统。  
> 拒绝转码画质劣化，拒绝会员割韭菜，拒绝正规电影库审查屏蔽；全链路 Direct Play 原画硬解直出，东方极简通透美学。

---

## 🏛️ 项目定位与核心哲学
1. **全链路 Direct Play（原画硬解直出）**：
   - 不调用 NAS 显卡进行低效损耗的二次压缩转码；
   - 充分利用手机（MediaCodec）、iPad/Mac（Metal/VideoToolbox）、Windows（DirectX/NVDEC）本地一流的 GPU 专用视频解码引擎；
   - 0 延迟秒开，拖动进度条丝滑如飞，NAS 端 CPU/GPU 占用近乎 0%。
2. **番号与私房片专属刮削引擎**：
   - 彻底摆脱 TMDB/豆瓣对特定品类的审查屏蔽；
   - 自动聚合本地 `poster.jpg` / `cover.jpg` / `.nfo` 与专属元数据源，封面墙永远饱满整齐。
3. **东方极简通透设计（Anti-Slop / Minimalist Editorial UI）**：
   - 纯白通透界面，告别直男极客风；
   - 响应式 PWA，手机/iPad/PC 一键脱壳安装为全屏原生应用。

---

## 📂 架构规划
- `backend/`: FastAPI + SQLite 极轻量分块流伺服与元数据引擎
- `frontend/`: Vue 3 + Tailwind CSS v4 纯白极简响应式 PWA
- `docker-compose.yml`: 单容器极速部署，热挂载宿主 `/vol1/1000/私人影库`

---
*Created with love by 夭夭 (妾身) for 主人 TIAN.*
