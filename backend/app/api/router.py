"""Central registry for the small set of currently implemented API routers.

New business routers are added here only after their HTTP contract is agreed.
"""

from fastapi import APIRouter

from app.api.demo.router import router as demo_router
from app.api.health.router import router as health_router

router = APIRouter()
router.include_router(health_router)
router.include_router(demo_router, prefix="/test", tags=["demo"])
