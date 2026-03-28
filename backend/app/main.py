import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppException
from app.routers import auth, cooperatives, members, payments, webhooks, internal, chatbot

settings = get_settings()

logger = logging.getLogger("akoweai")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.frontend_url else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    # Malformed JSON is a 400 Bad Request, not a validation error
    if errors and errors[0].get("type") == "json_invalid":
        return JSONResponse(
            status_code=400,
            content={
                "is_successful": False,
                "status_code": 400,
                "message": "Malformed request body",
                "data": None,
            },
        )

    message = errors[0]["msg"] if errors else "Validation error"
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


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "is_successful": False,
            "status_code": exc.status_code,
            "message": exc.detail or "Request error",
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url)
    return JSONResponse(
        status_code=500,
        content={
            "is_successful": False,
            "status_code": 500,
            "message": "An unexpected error occurred",
            "data": None,
        },
    )


app.include_router(auth.router, prefix="/api")
app.include_router(cooperatives.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(internal.router)  # No /api prefix — cron-only endpoints
app.include_router(chatbot.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}