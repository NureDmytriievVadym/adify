"""Version one of the shared REST contract."""

from fastapi import APIRouter

from adify_api.api.v1.accounts import router as accounts_router
from adify_api.api.v1.auth import router as auth_router
from adify_api.api.v1.health import router as health_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(accounts_router)
router.include_router(auth_router)
