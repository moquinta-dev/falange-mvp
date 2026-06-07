from fastapi import APIRouter

from app.api.routes.conversations import router as conversations_router
from app.api.routes.health import router as health_router
from app.api.routes.simulator import router as simulator_router
from app.api.routes.whatsapp import router as whatsapp_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(conversations_router)
api_router.include_router(simulator_router)
api_router.include_router(whatsapp_router)
