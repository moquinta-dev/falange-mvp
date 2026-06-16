"""Carregamento e upsert de definições de workflow."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.helpers import workflow_engine
from app.models import Tenant, Workflow


def get_definition_for_tenant(db: Session, tenant: Tenant) -> dict[str, Any] | None:
    """Retorna a árvore (JSON) do workflow do tenant, ou ``None`` se não houver."""

    if tenant.workflow_id is None:
        return None

    workflow = db.get(Workflow, tenant.workflow_id)
    if workflow is None or not workflow.definition:
        return None

    return workflow.definition


def get_by_key(db: Session, key: str) -> Workflow | None:
    return db.scalar(select(Workflow).where(Workflow.key == key))


def list_workflows(db: Session) -> list[Workflow]:
    return list(db.scalars(select(Workflow).order_by(Workflow.key)))


def upsert_workflow(
    db: Session,
    *,
    key: str,
    name: str | None,
    definition: dict[str, Any],
) -> Workflow:
    """Cria/atualiza um workflow por ``key`` (idempotente).

    Valida a árvore antes de persistir; ``WorkflowError`` é propagado para que o
    chamador (endpoint/seed) decida como reportar.
    """

    workflow_engine.validate_definition(definition)

    workflow = get_by_key(db, key)
    if workflow is None:
        workflow = Workflow(key=key, name=name, definition=definition)
        db.add(workflow)
    else:
        workflow.name = name
        workflow.definition = definition
    db.commit()
    db.refresh(workflow)
    return workflow
