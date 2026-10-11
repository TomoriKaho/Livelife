"""Central registry for the small set of currently implemented API routers.

New business routers are added here only after their HTTP contract is agreed.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.test import router as test_router

router = APIRouter()
router.include_router(health_router)
router.include_router(test_router, prefix="/test", tags=["demo"])
