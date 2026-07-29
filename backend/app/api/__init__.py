from .review import router
from .autofix import router as autofix_router
from .additional import router as additional_router
from .auth import router as auth_router
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(router)
api_router.include_router(autofix_router)
api_router.include_router(additional_router)
api_router.include_router(auth_router)

__all__ = ["api_router"]
