from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import require_admin_api_key
from app.core.database import get_db
from app.core.settings import get_settings
from app.helpers import metrics_helper, wizard_lead_helper
from app.helpers.email_client import get_email_client
from app.models import LandingEvent, Lead
from app.schemas.landing_event import LandingEventCreate, LandingEventResponse
from app.schemas.metrics import FunnelMetricsResponse
from app.schemas.wizard_lead import WizardLeadCreate, WizardLeadResponse

router = APIRouter(prefix="/funnel", tags=["funnel"])


def _normalize_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if digits.startswith("55"):
        return f"+{digits}"
    if len(digits) in (10, 11):
        return f"+55{digits}"
    return phone.strip()


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
    """Registra o topo do funil: visitas e cliques na landing page."""

    event = LandingEvent(
        **payload.model_dump(),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post(
    "/wizard-leads",
    response_model=WizardLeadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_wizard_lead(
    payload: WizardLeadCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Captura lead qualificado após conclusão do wizard da landing page."""

    if payload.website:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid submission")

    normalized_phone = _normalize_phone(payload.phone)
    lead = Lead(
        phone=normalized_phone,
        name=payload.name,
        business=payload.segment,
        pain=payload.question,
        goal=payload.answer,
        contact=payload.email,
        channels="whatsapp",
        source="wizard",
        status="new",
    )
    db.add(lead)
    db.flush()

    db.add(
        LandingEvent(
            event_type="wizard_lead_captured",
            session_id=payload.session_id,
            path="/criar-agente",
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    db.refresh(lead)

    settings = get_settings()
    background_tasks.add_task(
        wizard_lead_helper.notify_team_of_wizard_lead,
        get_email_client(settings),
        notify_target=settings.wizard_lead_notify_email,
        lead_id=lead.id,
        segment=payload.segment,
        question=payload.question,
        answer=payload.answer,
        phone=normalized_phone,
        name=payload.name,
        email=payload.email,
    )

    return lead


@router.get(
    "/metrics",
    response_model=FunnelMetricsResponse,
    dependencies=[Depends(require_admin_api_key)],
)
async def funnel_metrics(db: Session = Depends(get_db)):
    """Métricas do funil: % concluídas sem humano, % handoff, tempo médio."""

    return metrics_helper.compute_funnel_metrics(db)
