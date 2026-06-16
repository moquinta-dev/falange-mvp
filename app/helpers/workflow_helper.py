"""Carregamento da definição de workflow associada a um tenant."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import Tenant, Workflow


def get_definition_for_tenant(db: Session, tenant: Tenant) -> dict[str, Any] | None:
    """Retorna a árvore (JSON) do workflow do tenant, ou ``None`` se não houver."""

    if tenant.workflow_id is None:
        return None

    workflow = db.get(Workflow, tenant.workflow_id)
    if workflow is None or not workflow.definition:
        return None

    return workflow.definition
