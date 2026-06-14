from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.helpers import metrics_helper
from app.models import LandingEvent
from app.schemas.landing_event import LandingEventCreate, LandingEventResponse
from app.schemas.metrics import FunnelMetricsResponse

router = APIRouter(prefix="/funnel", tags=["funnel"])


@router.post(
    "/landing-events",
    response_model=LandingEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_landing_event(
    payload: LandingEventCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Registra o topo do funil: visitas e cliques no WhatsApp na landing page."""

    event = LandingEvent(
        **payload.model_dump(),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/metrics", response_model=FunnelMetricsResponse)
async def funnel_metrics(db: Session = Depends(get_db)):
    """Métricas do funil: % concluídas sem humano, % handoff, tempo médio."""

    return metrics_helper.compute_funnel_metrics(db)
