from fastapi import FastAPI

from shop_backend.api.routes import admin, auth, content, health, shop, users
from shop_backend.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="TinfoilStore Backend", version="0.1.0")

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth")
    app.include_router(users.router)
    app.include_router(admin.router, prefix="/admin")
    app.include_router(content.router, prefix="/content")

    if settings.ENABLE_HTTP_SHOP:
        app.include_router(shop.router, prefix="/shop")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("shop_backend.app:app", host="0.0.0.0", port=8000, reload=True)
