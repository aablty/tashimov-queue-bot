from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from src.api.core.security import protector

router = APIRouter()


@router.get("/ping", dependencies=[Depends(protector)])
async def ping_handler(
    _: Annotated[str | None, Header(alias="X-Api-Key")] = None,
) -> JSONResponse:
    return JSONResponse("pong!")
