from fastapi import APIRouter

from .routers import healthcheck, ping, webhooks


def router() -> APIRouter:
    router = APIRouter()

    router.include_router(webhooks.router)
    router.include_router(healthcheck.router)
    router.include_router(ping.router)

    return router
