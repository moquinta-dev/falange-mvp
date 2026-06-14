from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_admin_api_key
from app.core.database import get_db
from app.helpers import discovery_agent_helper
from app.schemas.simulator import SimulatorMessageRequest, SimulatorMessageResponse

router = APIRouter(
    prefix="/simulator",
    tags=["simulator"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("/messages", response_model=SimulatorMessageResponse)
async def send_simulator_message(
    payload: SimulatorMessageRequest,
    db: Session = Depends(get_db),
):
    return discovery_agent_helper.handle_message(
        db,
        external_id=payload.external_id,
        message=payload.message,
    )
