import secrets

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.services import WebhooksService
from src.core.config import config

router = APIRouter()
service = WebhooksService()


@router.post("/webhook")
async def webhook_handler(
    request: Request,
    secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> JSONResponse:
    expected_token = config.APP_API_KEY.get_secret_value()
    if secret_token is None or not secrets.compare_digest(secret_token, expected_token):
        raise HTTPException(status_code=403, detail="Forbidden")
    res = await service.webhook_handler(await request.json())
    return JSONResponse(**res.response())
