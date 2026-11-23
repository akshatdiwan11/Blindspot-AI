"""FastAPI application entry point."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.services.lifecycle import on_startup

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("blindspot")

app = FastAPI(
    title="Blindspot AI API",
    version="1.0.0",
    description="Find the failures your overall metrics hide. Deterministic evaluation, failure discovery, "
    "clustering and evidence retrieval, plus an optional evidence-grounded LLM investigator.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.perf_counter() - start) * 1000)
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    body = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        body["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(p) for p in err.get("loc", []) if p != "body"), "message": err.get("msg", "")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"error": {"code": "validation_failed", "message": "The request is invalid.", "details": details}})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Something went wrong on the server. The error has been logged."}})


@app.on_event("startup")
def _startup() -> None:
    on_startup()


app.include_router(api_router, prefix="/api")
