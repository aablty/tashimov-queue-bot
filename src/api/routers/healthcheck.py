from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from src.api.core.security import protector
from src.api.services import HealthcheckService

router = APIRouter()
service = HealthcheckService()


@router.get("/health")
async def health_handler(_: Request) -> JSONResponse:
    res = await service.health_handler()
    return JSONResponse(res)


@router.get("/health/details", dependencies=[Depends(protector)])
async def health_details_handler(
    _: Annotated[str | None, Header(alias="X-Api-Key")] = None,
) -> JSONResponse:
    res, healthy = await service.health_handler(details=True)
    return JSONResponse(res, status_code=200 if healthy else 503)
