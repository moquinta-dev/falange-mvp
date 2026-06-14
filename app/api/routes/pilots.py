from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Lead, Pilot
from app.schemas.pilot import PilotCreate, PilotResponse, PilotUpdate

router = APIRouter(prefix="/pilots", tags=["pilots"])


@router.post("", response_model=PilotResponse, status_code=status.HTTP_201_CREATED)
async def create_pilot(payload: PilotCreate, db: Session = Depends(get_db)):
    if db.get(Lead, payload.lead_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    pilot = Pilot(**payload.model_dump())
    db.add(pilot)
    db.commit()
    db.refresh(pilot)
    return pilot


@router.get("", response_model=list[PilotResponse])
async def list_pilots(
    lead_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Pilot).order_by(Pilot.created_at.desc()).limit(limit)
    if lead_id is not None:
        statement = (
            select(Pilot)
            .where(Pilot.lead_id == lead_id)
            .order_by(Pilot.created_at.desc())
            .limit(limit)
        )
    return list(db.scalars(statement))


@router.patch("/{pilot_id}", response_model=PilotResponse)
async def update_pilot(pilot_id: int, payload: PilotUpdate, db: Session = Depends(get_db)):
    pilot = db.get(Pilot, pilot_id)
    if pilot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pilot not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pilot, field, value)
    db.add(pilot)
    db.commit()
    db.refresh(pilot)
    return pilot
