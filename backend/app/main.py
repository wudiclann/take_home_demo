# FastAPI app entrypoint, mounts routes + static frontend

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import chat, documents
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Take Home Demo", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(chat.router)