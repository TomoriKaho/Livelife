from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-Agent-Session"],
        expose_headers=["X-Livelife-Backend-SHA"],
    )

    app.include_router(api_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_response(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))

    return app


app = create_app()
