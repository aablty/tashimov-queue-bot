import secrets

from fastapi import HTTPException, Request

from src.core.config import config


def protector(request: Request) -> None:
    api_key = request.headers.get("X-Api-Key")
    if api_key and secrets.compare_digest(
        api_key, config.APP_API_KEY.get_secret_value()
    ):
        return
    raise HTTPException(403, "Forbidden")
