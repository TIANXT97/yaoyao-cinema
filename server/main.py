"""夭夭影社 · 服务端入口。

对齐 docs/ARCHITECTURE.md 第 5 章 ``server/main.py``：
app 实例、生命周期（lifespan）、CORS 中间件、前端静态文件挂载。

启动方式::

    uvicorn server.main:app --host 0.0.0.0 --port 9900
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .api.router import api_router
from .database import db
from .utils.http_client import close_client
from .utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

VERSION = "1.0.7"


class SPAStaticFiles(StaticFiles):
    """静态资源伺服 + SPA history 路由回退。

    Vue Router 使用 history 模式，刷新 ``/library`` 等前端路由时需回退到
    ``index.html``，否则会 404。``/api/*`` 的真实 404 不受影响。
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：初始化目录 → 连接数据库 → 建表；退出时释放资源。"""
    setup_logging()
    config.ensure_directories()

    await db.connect()
    await db.init_schema()
    logger.info("夭夭影社服务端已就绪 · 监听 %s:%s", config.HOST, config.PORT)

    try:
        yield
    finally:
        await close_client()
        await db.close()
        logger.info("夭夭影社服务端已停止")


app = FastAPI(
    title="夭夭影社 API",
    description="私家极简全平台影院系统 · FastAPI + SQLite WAL",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Content-Length", "Accept-Ranges"],
)

# 所有业务 API 统一挂载到 /api（ARCHITECTURE.md 2.5 基础路径）
app.include_router(api_router, prefix="/api")


if config.FRONTEND_DIST.is_dir():
    # 前端 dist 由 FastAPI 静态伺服（ARCHITECTURE.md 第 1 章「单文件部署」）
    app.mount(
        "/",
        SPAStaticFiles(directory=str(config.FRONTEND_DIST), html=True),
        name="frontend",
    )
else:
    logger.info("未检测到前端构建产物 %s，跳过静态挂载", config.FRONTEND_DIST)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": "夭夭影社 API",
            "version": VERSION,
            "docs": "/docs",
            "api_prefix": "/api",
        }
