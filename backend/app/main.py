"""Advisor Appointment API.   Run:  uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import bootstrap, config
from .db import close_pool, connection, get_conn, open_pool, one
from .errors import install_handlers
from .routers import admin, appointments, auth, notes, notifications, slots, tasks, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate()
    open_pool()
    try:
        with connection() as conn:
            bootstrap.ensure_admin(conn)
        yield
    finally:
        close_pool()


app = FastAPI(
    title="Advisor Appointment API",
    version="1.1.0",
    description="Open availability, book appointments, record advising notes and follow up on tasks.",
    lifespan=lifespan,
)

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

install_handlers(app)


@app.get("/health", tags=["system"])
def health(conn=Depends(get_conn)):
    one(conn, "SELECT 1 AS ok")
    return {"status": "ok"}


api = APIRouter(prefix="/api/v1")
for module in (auth, slots, appointments, notes, tasks, notifications, admin, users):
    api.include_router(module.router)
app.include_router(api)
