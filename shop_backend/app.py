from fastapi import FastAPI

from shop_backend.api.routes import health, auth, users, admin, content


def create_app() -> FastAPI:
    app = FastAPI(title="TinfoilStore Backend", version="0.1.0")

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth")
    app.include_router(users.router)
    app.include_router(admin.router, prefix="/admin")
    app.include_router(content.router, prefix="/content")

    return app


app = create_app()


def run() -> None:
    import uvicorn
    uvicorn.run("shop_backend.app:app", host="0.0.0.0", port=8000, reload=True)
