from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_admin_api_key
from app.core.database import get_db
from app.models import Client, Lead
from app.schemas.client import ClientCreate, ClientResponse

router = APIRouter(
    prefix="/clients",
    tags=["clients"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    if db.get(Lead, payload.lead_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    client_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Client).order_by(Client.created_at.desc()).limit(limit)
    if client_status is not None:
        statement = (
            select(Client)
            .where(Client.status == client_status)
            .order_by(Client.created_at.desc())
            .limit(limit)
        )
    return list(db.scalars(statement))
