from fastapi import APIRouter

from api import v1

router = APIRouter()

router.include_router(v1.router, prefix="/v1")
