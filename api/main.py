from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from services import products as products_service

from api.routers import baskets, cart, courses, orders, products


APP_TITLE = "MiniDeN API"
APP_VERSION = "1.0.0"


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(products.router, prefix="/api")
    app.include_router(baskets.router, prefix="/api")
    app.include_router(courses.router, prefix="/api")
    app.include_router(cart.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")

    @app.get("/")
    def healthcheck() -> dict[str, bool]:
        return {"ok": True}

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        products_service.list_products("basket")
        products_service.list_products("course")

    return app


app = create_app()


__all__ = ["app", "create_app"]
