# FastAPI app entrypoint, mounts routes + static frontend

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, documents
from app.core.tts import AUDIO_DIR
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Take Home Demo", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(chat.router)

AUDIO_DIR.mkdir(parents=True, exist_ok=True)  # StaticFiles requires the dir to exist at mount time
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")