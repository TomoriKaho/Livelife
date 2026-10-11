from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.db.session import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database: Database = app.state.database
    try:
        yield
    finally:
        database.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Livelife API", version="0.1.0", lifespan=lifespan)
    app.state.database = Database.from_environment()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://localhost",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://localhost:8766",
            "http://127.0.0.1:8766",
        ],
        allow_methods=["GET"],
        allow_headers=["Accept"],
        expose_headers=["X-Livelife-Backend-SHA"],
    )

    app.include_router(api_router)
    return app


app = create_app()
