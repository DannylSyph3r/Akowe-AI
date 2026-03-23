from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="AkoweAI",
    description="WhatsApp-first cooperative management system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}