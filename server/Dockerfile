# syntax=docker/dockerfile:1
#
# 夭夭影社 · 单容器一体化全栈镜像
# ------------------------------------------------
# Stage 1：Node 构建 Vue 3 PWA（含 Service Worker / 图标 / 启动屏）
# Stage 2：Python 运行时；FastAPI 同源伺服 /api 与前端 dist，零外部依赖
#
# 构建：docker build -f server/Dockerfile -t yaoyao-cinema .
# 运行：docker compose up -d

# ---------- Stage 1: 前端构建 ----------
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# 先复制依赖清单以充分利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 复制前端源码并构建（PWA 产物输出到 dist/）
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: 运行时 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ffprobe：扫描器媒体探测所需（ARCHITECTURE.md 2.4）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 依赖层
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# 服务端源码
COPY server/ /app/server/

# 前端构建产物打入镜像
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# 运行时配置（ARCHITECTURE.md 2.1 端口 9900）
ENV YAOYAO_ROOT=/app \
    YAOYAO_DATA_DIR=/app/data \
    YAOYAO_DB_PATH=/app/data/yaoyao.db \
    YAOYAO_MEDIA_ROOT=/media \
    YAOYAO_FRONTEND_DIST=/app/frontend/dist \
    YAOYAO_HOST=0.0.0.0 \
    YAOYAO_PORT=9900 \
    TZ=Asia/Shanghai

# 运行数据与媒体库挂载点
VOLUME ["/app/data", "/media"]

EXPOSE 9900

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9900/api/system/health')" || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "9900", "--proxy-headers"]
