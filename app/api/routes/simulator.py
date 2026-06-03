from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.helpers import order_agent_helper
from app.schemas.simulator import SimulatorMessageRequest, SimulatorMessageResponse

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/messages", response_model=SimulatorMessageResponse)
def send_simulator_message(
    payload: SimulatorMessageRequest,
    db: Session = Depends(get_db),
):
    return order_agent_helper.handle_message(
        db,
        external_id=payload.external_id,
        message=payload.message,
    )
