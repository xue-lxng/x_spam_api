from fastapi import APIRouter
from api.v1.routers import (
    healthcheck, spam,
)

router = APIRouter()
router.include_router(healthcheck.router, prefix="/server")
router.include_router(spam.router, prefix="/spam")
