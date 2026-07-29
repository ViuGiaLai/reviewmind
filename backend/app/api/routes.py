from fastapi import APIRouter

from .additional import router as additional_router
from .auth import router as auth_router
from .autofix import router as autofix_router
from .evaluation_profiles import router as evaluation_profiles_router
from .plugins import router as plugins_router
from .review import router as review_router
from .security import router as security_router
from .templates import router as templates_router


api_router = APIRouter()
api_router.include_router(review_router)
api_router.include_router(autofix_router)
api_router.include_router(additional_router)
api_router.include_router(auth_router)
api_router.include_router(plugins_router)
api_router.include_router(security_router)
api_router.include_router(templates_router)
api_router.include_router(evaluation_profiles_router)

__all__ = ["api_router"]
