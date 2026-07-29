# FastAPI app entrypoint, mounts routes + static frontend

from fastapi import FastAPI

from app.api.routes import documents

app = FastAPI(title="Take Home Demo")

app.include_router(documents.router)
