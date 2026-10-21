from aiogram import Router

from . import queue


def router() -> Router:
    router = Router()

    router.include_router(queue.router)

    return router
