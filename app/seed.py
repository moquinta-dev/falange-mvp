"""Seed idempotente de tenants e workflows (Fase 0 multi-tenant).

Cadastra a Falangelabs (tenant-zero, dogfooding do discovery agent) e a Natália
(primeiro adopter, triagem de alunos). Os ``phone_number_id`` reais da Meta vêm
de variáveis de ambiente — assim não commitamos IDs falsos que poderiam rotear
tráfego real incorretamente.

Uso:

    python -m app.seed

Variáveis relevantes (um tenant só é criado se o respectivo ID estiver setado):

    FALANGE_WHATSAPP_PHONE_NUMBER_ID   phone_number_id do número da Falange
    FALANGE_NOTIFY_TARGET              e-mail/telefone para notificar a Falange
    NATALIA_WHATSAPP_PHONE_NUMBER_ID   phone_number_id do número da Natália
    NATALIA_NOTIFY_TARGET              e-mail/telefone para notificar a Natália
"""

import logging
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_database
from app.models import Tenant, Workflow

logger = logging.getLogger(__name__)


# Discovery agent da Falangelabs como workflow data-driven (linear, só texto).
# O engine genérico (Fase 1) interpretará esta árvore; por ora é apenas dado.
DISCOVERY_V1: dict[str, Any] = {
    "start": "ask_business",
    "nodes": {
        "ask_business": {
            "type": "text",
            "prompt": (
                "Oi! Eu sou o assistente virtual da Falangelabs e vou te ajudar a "
                "entender como automatizar o seu atendimento no WhatsApp. Para "
                "começar, me conta um pouco sobre o seu negócio: o que a sua "
                "empresa faz e quais produtos ou serviços você oferece?"
            ),
            "collect": "business",
            "next": "ask_channels",
        },
        "ask_channels": {
            "type": "text",
            "prompt": (
                "Mostra que faz sentido! E hoje, por onde os seus clientes "
                "costumam falar com você? (WhatsApp, telefone, Instagram, site...)"
            ),
            "collect": "channels",
            "next": "ask_pain",
        },
        "ask_pain": {
            "type": "text",
            "prompt": (
                "Entendi. Pensando no atendimento de hoje, qual é a maior "
                "dificuldade ou o que mais consome o seu tempo no dia a dia?"
            ),
            "collect": "pain",
            "next": "ask_goal",
        },
        "ask_goal": {
            "type": "text",
            "prompt": (
                "Faz sentido. Se você pudesse automatizar uma coisa primeiro, o "
                "que seria? (ex.: tirar dúvidas, agendar horários, registrar "
                "pedidos, qualificar clientes)"
            ),
            "collect": "goal",
            "next": "ask_volume",
        },
        "ask_volume": {
            "type": "text",
            "prompt": (
                "Ótimo. Para eu dimensionar melhor: qual é o volume aproximado de "
                "atendimentos que você recebe por dia ou por semana?"
            ),
            "collect": "volume",
            "next": "ask_contact",
        },
        "ask_contact": {
            "type": "text",
            "prompt": (
                "Perfeito. Por último, qual é o seu nome e o melhor horário para a "
                "nossa equipe falar com você?"
            ),
            "collect": "contact",
            "next": "done",
        },
        "done": {"type": "terminal", "summary": True},
    },
}


# Triagem de novos alunos da Natália (árvore com ramificação).
TRIAGEM_PERSONAL_V1: dict[str, Any] = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": "Oi! Que bom ter você aqui. Como é o seu nome?",
            "collect": "nome",
            "next": "ask_age",
        },
        "ask_age": {
            "type": "text",
            "prompt": "Qual a sua faixa etária?",
            "collect": "faixa_etaria",
            "next": "ask_interest",
        },
        "ask_interest": {
            "type": "choice",
            "prompt": "Você está interessada em:",
            "collect": "interesse",
            "options": [
                {"label": "Aulas de Personal", "next": "personal_mod"},
                {"label": "Aulas de Yoga", "next": "yoga_mod"},
                {"label": "Consultoria online", "next": "consultoria_obj"},
            ],
        },
        "personal_mod": {
            "type": "choice",
            "prompt": "Personal: online ou presencial?",
            "collect": "modalidade",
            "options": [
                {"label": "Online", "next": "done"},
                {"label": "Presencial", "next": "done"},
            ],
        },
        "yoga_mod": {
            "type": "choice",
            "prompt": "Yoga: particular ou em grupo?",
            "collect": "modalidade",
            "options": [
                {"label": "Particular", "next": "done"},
                {"label": "Em grupo", "next": "done"},
            ],
        },
        "consultoria_obj": {
            "type": "choice",
            "prompt": "Consultoria: qual objetivo?",
            "collect": "objetivo",
            "options": [
                {"label": "Fortalecimento", "next": "done"},
                {"label": "Fortalecimento + corrida", "next": "done"},
            ],
        },
        "done": {"type": "terminal", "summary": True},
    },
}


def upsert_workflow(db: Session, *, key: str, name: str, definition: dict[str, Any]) -> Workflow:
    workflow = db.scalar(select(Workflow).where(Workflow.key == key))
    if workflow is None:
        workflow = Workflow(key=key, name=name, definition=definition)
        db.add(workflow)
    else:
        workflow.name = name
        workflow.definition = definition
    db.commit()
    db.refresh(workflow)
    return workflow


def upsert_tenant(
    db: Session,
    *,
    name: str,
    phone_number_id: str,
    workflow: Workflow,
    notify_channel: str,
    notify_target: str | None,
) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(Tenant.whatsapp_phone_number_id == phone_number_id)
    )
    if tenant is None:
        tenant = Tenant(name=name, whatsapp_phone_number_id=phone_number_id)
        db.add(tenant)

    tenant.name = name
    tenant.workflow_id = workflow.id
    tenant.notify_channel = notify_channel
    tenant.notify_target = notify_target
    tenant.active = True
    db.commit()
    db.refresh(tenant)
    return tenant


def seed(db: Session) -> None:
    discovery = upsert_workflow(
        db,
        key="discovery_v1",
        name="Falangelabs — descoberta de negócio",
        definition=DISCOVERY_V1,
    )
    triagem = upsert_workflow(
        db,
        key="triagem_personal_v1",
        name="Natália — triagem de novos alunos",
        definition=TRIAGEM_PERSONAL_V1,
    )

    falange_phone = os.getenv("FALANGE_WHATSAPP_PHONE_NUMBER_ID")
    if falange_phone:
        upsert_tenant(
            db,
            name="Falangelabs",
            phone_number_id=falange_phone,
            workflow=discovery,
            notify_channel="email",
            notify_target=os.getenv("FALANGE_NOTIFY_TARGET"),
        )
        logger.info("Tenant Falangelabs seeded (phone_number_id=%s)", falange_phone)
    else:
        logger.warning(
            "FALANGE_WHATSAPP_PHONE_NUMBER_ID não definido; tenant Falange não criado"
        )

    natalia_phone = os.getenv("NATALIA_WHATSAPP_PHONE_NUMBER_ID")
    if natalia_phone:
        upsert_tenant(
            db,
            name="Natalia Ferreira Corpo e Mente",
            phone_number_id=natalia_phone,
            workflow=triagem,
            notify_channel="email",
            notify_target=os.getenv("NATALIA_NOTIFY_TARGET"),
        )
        logger.info("Tenant Natália seeded (phone_number_id=%s)", natalia_phone)
    else:
        logger.warning(
            "NATALIA_WHATSAPP_PHONE_NUMBER_ID não definido; tenant Natália não criado"
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_database()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
