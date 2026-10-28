from fastapi import FastAPI

from adify_api.api.v1.router import router
from adify_api.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        description="Shared REST API for Adify web and native Android clients.",
    )
    app.include_router(router)
    return app


app = create_app()
