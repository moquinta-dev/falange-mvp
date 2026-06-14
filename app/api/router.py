from fastapi import APIRouter

from app.api.routes.clients import router as clients_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.funnel import router as funnel_router
from app.api.routes.health import router as health_router
from app.api.routes.leads import router as leads_router
from app.api.routes.pilots import router as pilots_router
from app.api.routes.simulator import router as simulator_router
from app.api.routes.whatsapp import router as whatsapp_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(conversations_router)
api_router.include_router(simulator_router)
api_router.include_router(whatsapp_router)
api_router.include_router(funnel_router)
api_router.include_router(leads_router)
api_router.include_router(pilots_router)
api_router.include_router(clients_router)
