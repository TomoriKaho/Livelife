from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.test import router as test_router

app = FastAPI(title="Livelife API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "http://localhost:8766",
        "http://127.0.0.1:8766",
    ],
    allow_methods=["GET"],
    allow_headers=["Accept"],
)

app.include_router(test_router, prefix="/test", tags=["demo"])
