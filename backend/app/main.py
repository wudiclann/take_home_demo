# FastAPI app entrypoint: builds the app, wires up rate limiting, mounts all
# routers, and serves saved audio files as static files.
# FastAPI 应用入口：创建应用实例、接入速率限制、挂载所有路由，
# 并将已保存的音频文件作为静态文件对外提供。

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import chat, documents, settings
from app.core.rate_limit import limiter
from app.core.reranker import preload_model
from app.core.tts import AUDIO_DIR
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at server startup/shutdown: creates the SQLite tables and
    kicks off a background warm-up of the reranker model.
    在服务启动/关闭时运行一次：创建 SQLite 数据表，
    并在后台预热重排序器（reranker）模型。"""
    init_db()
    # Warms the cross-encoder reranker (downloads/loads weights) in a background
    # thread so it doesn't block startup or the event loop -- without this, the
    # first /chat or /ask request pays that cost instead, which is slow and
    # confusing since every later request is fast.
    # 在后台线程中预热交叉编码器重排序器（下载/加载模型权重），避免阻塞启动
    # 流程或事件循环——否则这个耗时会转嫁到第一次 /chat 或 /ask 请求上，
    # 显得很慢且令人困惑，因为之后每次请求其实都很快。
    asyncio.create_task(asyncio.to_thread(preload_model))
    yield


app = FastAPI(title="Take Home Demo", lifespan=lifespan)

# Wire up slowapi rate limiting: shared limiter instance, the handler that turns
# an exceeded limit into a 429 response, and the middleware that actually enforces it.
# 接入 slowapi 速率限制：共享的 limiter 实例、把超限请求转换为 429 响应的
# 异常处理器，以及真正执行限流的中间件。
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(settings.router)

# StaticFiles requires the dir to exist at mount time / StaticFiles 要求挂载时目录必须已存在
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
