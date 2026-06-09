from fastapi import FastAPI

from shop_backend.api.routes import admin, health


def create_app() -> FastAPI:
    app = FastAPI(title="TinfoilStore Backend", version="0.1.0")

    app.include_router(health.router)
    app.include_router(admin.router, prefix="/admin")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("shop_backend.app:app", host="0.0.0.0", port=8000, reload=True)
