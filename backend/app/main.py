from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.database import engine
from app.core.exceptions import AppException
from app.routers import auth, cooperatives, members


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


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "is_successful": False,
            "status_code": exc.status_code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    message = errors[0]["msg"] if errors else "Validation error"
    # Strip the pydantic "Value error, " prefix when present
    message = message.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={
            "is_successful": False,
            "status_code": 422,
            "message": message,
            "data": None,
        },
    )


app.include_router(auth.router)
app.include_router(cooperatives.router)
app.include_router(members.router)


@app.get("/health")
async def health():
    return {"status": "ok"}