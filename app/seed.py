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

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_database
from app.helpers import tenant_helper, workflow_helper

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


# Triagem v2 da Natália — mensagens enriquecidas, confirmação antes do encerramento.
TRIAGEM_PERSONAL_V2: dict[str, Any] = {
    "start": "ask_name",
    "nodes": {
        "ask_name": {
            "type": "text",
            "prompt": (
                "Olá! Eu sou a *Assistente Virtual* da Natália🌟 Que alegria ter você "
                "por aqui!\n\nPara começarmos o seu atendimento de forma rápida, por "
                "favor, me diga: *qual é o seu nome?*"
            ),
            "collect": "nome",
            "next": "ask_age",
        },
        "ask_age": {
            "type": "text",
            "prompt": (
                "Prazer em te conhecer! 🌷\n\nPara ajudar a nossa equipe a entender "
                "melhor o seu perfil, qual é a sua *idade*?"
            ),
            "collect": "idade",
            "next": "ask_interest",
        },
        "ask_interest": {
            "type": "choice",
            "prompt": (
                "Perfeito! Para eu te direcionar para o atendimento correto, me conta: "
                "em qual dessas opções você tem interesse hoje?\n\n"
                "1️⃣ *Aulas de Personal* (Acompanhamento individual) 🏋️‍♀️\n"
                "2️⃣ *Aulas de Yoga* (Equilíbrio, mobilidade e respiração) 🧘🏻‍♀️\n"
                "3️⃣ *Consultoria Online* (Treinos personalizados de onde quiser) 📲\n\n"
                "Por favor, digite apenas o *número* da opção desejada."
            ),
            "collect": "interesse",
            "show_options": False,
            "options": [
                {"label": "Aulas de Personal", "next": "personal_mod"},
                {"label": "Aulas de Yoga", "next": "yoga_mod"},
                {"label": "Consultoria Online", "next": "consultoria_obj"},
            ],
        },
        "personal_mod": {
            "type": "choice",
            "prompt": (
                "Excelente escolha! Ter um acompanhamento de perto faz toda a "
                "diferença para os seus resultados. 🚀\n\nComo você prefere realizar "
                "as suas aulas de Personal?\n\n"
                "1️⃣ *Online* (Treino ao vivo por videochamada, de onde você estiver) "
                "👩🏻‍💻\n"
                "2️⃣ *Presencial* (Atendimento exclusivo e presencial) 👟\n\n"
                "Por favor, digite apenas o *número* da opção desejada."
            ),
            "collect": "modalidade",
            "show_options": False,
            "options": [
                {"label": "Online", "next": "confirm_personal"},
                {"label": "Presencial", "next": "confirm_personal"},
            ],
        },
        "yoga_mod": {
            "type": "choice",
            "prompt": (
                "Excelente escolha! O Yoga é incrível para trazer mais equilíbrio, "
                "consciência corporal e bem-estar para o seu dia a dia. 🧘🏻‍♀️✨\n\n"
                "Como você prefere realizar as suas práticas?\n\n"
                "1️⃣ *Particular* (Atendimento exclusivo e 100% personalizado) 🕉️\n"
                "2️⃣ *Em Grupo* (Prática coletiva com 2 a 4 pessoas) 👥\n\n"
                "Por favor, digite apenas o *número* da opção desejada."
            ),
            "collect": "modalidade",
            "show_options": False,
            "options": [
                {"label": "Particular", "next": "confirm_yoga"},
                {"label": "Em Grupo", "next": "confirm_yoga"},
            ],
        },
        "consultoria_obj": {
            "type": "choice",
            "prompt": (
                "Excelente escolha! 🚀 E qual é o seu principal objetivo no momento?\n\n"
                "1️⃣ *Fortalecimento* (Mais força, tônus muscular e definição) 💪\n"
                "2️⃣ *Fortalecimento + Corrida* (Treinos de força + iniciação na "
                "corrida) 🏃🏻‍♀️💨\n\n"
                "Por favor, digite apenas o *número* da opção desejada."
            ),
            "collect": "objetivo",
            "show_options": False,
            "options": [
                {"label": "Fortalecimento", "next": "confirm_consultoria"},
                {"label": "Fortalecimento + Corrida", "next": "confirm_consultoria"},
            ],
        },
        "confirm_personal": {
            "type": "choice",
            "prompt": (
                "Show! Já anotei tudo por aqui. 📝 Só para confirmar se o seu cadastro "
                "está certinho:\n\n"
                "👋 *Nome:* {nome}\n"
                "🎂 *Idade:* {idade}\n"
                "🎯 *Interesse:* Aulas de Personal ({modalidade})\n\n"
                "Se estiver tudo correto, digite *1*.\n\n"
                "Assim que você confirmar, eu envio a sua ficha direto para Natália e "
                "ela entrará em contato com você para conversarem melhor sobre os seus "
                "objetivos! ⚡"
            ),
            "show_options": False,
            "options": [{"label": "Confirmado", "next": "done"}],
        },
        "confirm_yoga": {
            "type": "choice",
            "prompt": (
                "Show! Já anotei tudo por aqui. 📝 Só para confirmar se o seu cadastro "
                "está certinho:\n\n"
                "👋 *Nome:* {nome}\n"
                "🎂 *Idade:* {idade}\n"
                "🎯 *Interesse:* Aulas de Yoga ({modalidade})\n\n"
                "Se estiver tudo correto, digite *1*.\n\n"
                "Assim que você confirmar, eu envio a sua ficha direto para Natália e "
                "ela entrará em contato com você para conversarem melhor sobre as "
                "práticas! ⚡"
            ),
            "show_options": False,
            "options": [{"label": "Confirmado", "next": "done"}],
        },
        "confirm_consultoria": {
            "type": "choice",
            "prompt": (
                "Show! Já anotei tudo por aqui. 📝 Só para confirmar se o seu cadastro "
                "está certinho:\n\n"
                "👋 *Nome:* {nome}\n"
                "🎂 *Idade:* {idade}\n"
                "🎯 *Interesse:* Consultoria Online\n"
                "🔥 *Foco:* {objetivo}\n\n"
                "Se estiver tudo correto, digite *1*.\n\n"
                "Assim que você confirmar, eu envio a sua ficha direto para Natália e "
                "ela entrará em contato com você para dar continuidade! ⚡"
            ),
            "show_options": False,
            "options": [{"label": "Confirmado", "next": "done"}],
        },
        "done": {
            "type": "terminal",
            "reply": (
                "Prontinho! Os seus dados já foram enviados com sucesso para Natália. "
                "📨✨\n\nMuito em breve ela entrará em contato com você diretamente para "
                "alinhar os próximos passos e entender tudinho sobre o que você busca.\n\n"
                "Tenha um excelente dia! 🏋️‍♀️🙏🏻"
            ),
        },
    },
}


def seed(db: Session) -> None:
    discovery = workflow_helper.upsert_workflow(
        db,
        key="discovery_v1",
        name="Falangelabs — descoberta de negócio",
        definition=DISCOVERY_V1,
    )
    triagem = workflow_helper.upsert_workflow(
        db,
        key="triagem_personal_v1",
        name="Natália — triagem de novos alunos",
        definition=TRIAGEM_PERSONAL_V1,
    )
    workflow_helper.upsert_workflow(
        db,
        key="triagem_personal_v2",
        name="Natália — triagem de novos alunos (v2)",
        definition=TRIAGEM_PERSONAL_V2,
    )

    falange_phone = os.getenv("FALANGE_WHATSAPP_PHONE_NUMBER_ID")
    if falange_phone:
        tenant_helper.upsert_tenant(
            db,
            name="Falangelabs",
            phone_number_id=falange_phone,
            workflow_id=discovery.id,
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
        tenant_helper.upsert_tenant(
            db,
            name="Natalia Ferreira Corpo e Mente",
            phone_number_id=natalia_phone,
            workflow_id=triagem.id,
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
