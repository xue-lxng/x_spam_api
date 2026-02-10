from fastapi import APIRouter
from starlette.responses import JSONResponse

from api.v1.services.server import get_params

router = APIRouter(tags=["Server"])


@router.get("/healthcheck", summary="Healthcheck endpoint")
async def healthcheck():
    return JSONResponse({"status": "OK"})


@router.get("/params", summary="Get server parameters as Base64")
async def get_server_params():
    return await get_params()
