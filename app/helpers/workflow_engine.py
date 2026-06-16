"""Engine determinístico e genérico de workflows de triagem (data-driven).

O fluxo de cada tenant vive como dados (``Workflow.definition``), uma árvore de
decisão. Este engine caminha pela árvore usando ``Conversation.current_node_id``
e ``Conversation.answers``, sem nenhuma lógica específica de tenant — adicionar
um adopter com um fluxo novo é inserir um workflow, sem deploy.

Formato da definição::

    {
      "start": "ask_name",
      "nodes": {
        "ask_name":  {"type": "text",   "prompt": "...", "collect": "nome", "next": "ask_age"},
        "ask_x":     {"type": "choice", "prompt": "...", "collect": "x",
                       "options": [{"label": "A", "next": "n1"}, {"label": "B", "next": "n2"}]},
        "done":      {"type": "terminal", "summary": true}
      }
    }

Escolhas (``choice``) são apresentadas como opções numeradas e aceitam tanto o
número quanto o texto do rótulo na resposta (UX robusta para WhatsApp).
"""

from dataclasses import dataclass
from typing import Any
from unicodedata import normalize

from sqlalchemy.orm import Session

from app.helpers import conversation_helper, lead_helper
from app.models import Conversation

COMPLETED_STATE = "completed"
HANDOFF_STATE = "handoff"

SUMMARY_HEADER = "Show! Deixa eu confirmar o que entendi:"
COMPLETED_REPLY = (
    "Maravilha! Registrei tudo e em breve entramos em contato. Obrigado pelas "
    "informações!"
)
COMPLETED_FOLLOWUP = (
    "Já registramos o seu interesse e em breve falamos com você. Se precisar de "
    "algo agora, é só pedir para falar com uma pessoa."
)
HANDOFF_REPLY = (
    "Claro! Vou encaminhar você para uma pessoa do nosso time. Em breve alguém "
    "entra em contato por aqui."
)
REASK_PREFIX = "Pode me responder, por favor? "
INVALID_CHOICE_PREFIX = "Não entendi. Escolha uma das opções: "

_HANDOFF_TOKENS = ("humano", "atendente", "reclamar", "reclamacao", "cancelar")


class WorkflowError(ValueError):
    """Definição de workflow inválida ou inconsistente."""


_VALID_NODE_TYPES = ("text", "choice", "terminal")


def validate_definition(definition: Any) -> None:
    """Valida a árvore de um workflow; levanta ``WorkflowError`` se inválida.

    Usado tanto pelo endpoint de onboarding (Fase 4) quanto pelos helpers de
    upsert, garantindo que apenas fluxos consistentes cheguem ao banco — afinal
    cadastrar um adopter não passa por code review.
    """

    if not isinstance(definition, dict):
        raise WorkflowError("definição deve ser um objeto JSON")

    nodes = definition.get("nodes")
    start_id = definition.get("start")
    if not isinstance(nodes, dict) or not nodes:
        raise WorkflowError("definição inválida: 'nodes' ausente ou vazio")
    if not isinstance(start_id, str) or start_id not in nodes:
        raise WorkflowError(
            "definição inválida: 'start' ausente ou não aponta para um nó existente"
        )

    has_terminal = False
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            raise WorkflowError(f"nó {node_id!r} deve ser um objeto")

        node_type = node.get("type")
        if node_type not in _VALID_NODE_TYPES:
            raise WorkflowError(f"nó {node_id!r} tem tipo inválido: {node_type!r}")

        if node_type == "terminal":
            has_terminal = True
            continue

        prompt = node.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise WorkflowError(f"nó {node_id!r} precisa de 'prompt' não vazio")

        if node_type == "text":
            _validate_next(node_id, node.get("next"), nodes)
        else:  # choice
            options = node.get("options")
            if not isinstance(options, list) or not options:
                raise WorkflowError(f"nó {node_id!r} precisa de 'options' não vazio")
            for index, option in enumerate(options, start=1):
                if not isinstance(option, dict):
                    raise WorkflowError(
                        f"opção #{index} do nó {node_id!r} deve ser um objeto"
                    )
                label = option.get("label")
                if not isinstance(label, str) or not label.strip():
                    raise WorkflowError(
                        f"opção #{index} do nó {node_id!r} precisa de 'label' não vazio"
                    )
                _validate_next(node_id, option.get("next"), nodes)

    if not has_terminal:
        raise WorkflowError("definição inválida: nenhum nó do tipo 'terminal'")

    _validate_reachability(start_id, nodes)


def _validate_next(node_id: str, next_id: Any, nodes: dict[str, Any]) -> None:
    if not isinstance(next_id, str) or next_id not in nodes:
        raise WorkflowError(
            f"nó {node_id!r} aponta para destino inexistente: {next_id!r}"
        )


def _validate_reachability(start_id: str, nodes: dict[str, Any]) -> None:
    seen: set[str] = set()
    stack = [start_id]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = nodes[node_id]
        if node.get("type") == "text":
            stack.append(node["next"])
        elif node.get("type") == "choice":
            for option in node.get("options", []):
                stack.append(option["next"])

    unreachable = set(nodes) - seen
    if unreachable:
        raise WorkflowError(
            "definição inválida: nós inalcançáveis a partir de 'start': "
            + ", ".join(sorted(unreachable))
        )


@dataclass(frozen=True)
class WorkflowResult:
    conversation_id: int
    reply: str
    state: str
    current_node_id: str | None
    completed: bool
    summary: str | None = None


@dataclass(frozen=True)
class _Decision:
    reply: str
    current_node_id: str
    answers: dict[str, Any]
    state: str
    completed: bool = False
    handoff: bool = False
    summary: str | None = None


def handle_message(
    db: Session,
    *,
    conversation: Conversation,
    workflow: dict[str, Any],
    message: str,
    external_message_id: str | None = None,
) -> WorkflowResult:
    previous_state = conversation.state

    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="inbound",
        content=message,
        external_message_id=external_message_id,
    )

    decision = _decide(
        workflow,
        current_node_id=conversation.current_node_id,
        answers=dict(conversation.answers or {}),
        message=message,
    )

    conversation_helper.update_workflow_state(
        db,
        conversation=conversation,
        current_node_id=decision.current_node_id,
        answers=decision.answers,
        state=decision.state,
    )
    conversation_helper.add_message(
        db,
        conversation=conversation,
        direction="outbound",
        content=decision.reply,
    )

    _persist_funnel(db, conversation, decision, previous_state)

    return WorkflowResult(
        conversation_id=conversation.id,
        reply=decision.reply,
        state=decision.state,
        current_node_id=decision.current_node_id,
        completed=decision.completed,
        summary=decision.summary,
    )


def _decide(
    workflow: dict[str, Any],
    *,
    current_node_id: str | None,
    answers: dict[str, Any],
    message: str,
) -> _Decision:
    nodes = workflow.get("nodes")
    start_id = workflow.get("start")
    if not isinstance(nodes, dict) or start_id not in nodes:
        raise WorkflowError("workflow inválido: 'start'/'nodes' ausentes")

    normalized_message = _normalize(message)

    if _should_handoff(normalized_message):
        return _Decision(
            reply=HANDOFF_REPLY,
            current_node_id=current_node_id or start_id,
            answers=answers,
            state=HANDOFF_STATE,
            handoff=True,
        )

    # Primeiro contato: apresenta o nó inicial sem consumir a mensagem.
    if current_node_id is None:
        return _present_node(nodes, start_id, answers)

    current_node = nodes.get(current_node_id)
    if current_node is None or current_node.get("type") == "terminal":
        return _Decision(
            reply=COMPLETED_FOLLOWUP,
            current_node_id=current_node_id,
            answers=answers,
            state=COMPLETED_STATE,
        )

    node_type = current_node.get("type")
    if node_type == "text":
        return _advance_text(nodes, current_node_id, current_node, answers, message)
    if node_type == "choice":
        return _advance_choice(nodes, current_node_id, current_node, answers, message)

    raise WorkflowError(f"tipo de nó não suportado: {node_type!r}")


def _advance_text(
    nodes: dict[str, Any],
    current_node_id: str,
    node: dict[str, Any],
    answers: dict[str, Any],
    message: str,
) -> _Decision:
    if not message.strip():
        return _Decision(
            reply=REASK_PREFIX + node["prompt"],
            current_node_id=current_node_id,
            answers=answers,
            state=current_node_id,
        )

    collect = node.get("collect")
    if collect:
        answers[collect] = message.strip()
    return _move_to(nodes, node["next"], answers)


def _advance_choice(
    nodes: dict[str, Any],
    current_node_id: str,
    node: dict[str, Any],
    answers: dict[str, Any],
    message: str,
) -> _Decision:
    options = node.get("options", [])
    chosen = _match_option(message, options)
    if chosen is None:
        return _Decision(
            reply=_render_choice(node),
            current_node_id=current_node_id,
            answers=answers,
            state=current_node_id,
        )

    collect = node.get("collect")
    if collect:
        answers[collect] = chosen.get("value", chosen["label"])
    return _move_to(nodes, chosen["next"], answers)


def _move_to(
    nodes: dict[str, Any],
    next_id: str,
    answers: dict[str, Any],
) -> _Decision:
    next_node = nodes.get(next_id)
    if next_node is None:
        raise WorkflowError(f"nó destino inexistente: {next_id!r}")

    if next_node.get("type") == "terminal":
        summary = _build_summary(answers) if next_node.get("summary") else None
        reply = next_node.get("reply") or COMPLETED_REPLY
        if summary:
            reply = f"{summary}\n\n{reply}"
        return _Decision(
            reply=reply,
            current_node_id=next_id,
            answers=answers,
            state=COMPLETED_STATE,
            completed=True,
            summary=summary,
        )

    return _present_node(nodes, next_id, answers)


def _present_node(
    nodes: dict[str, Any],
    node_id: str,
    answers: dict[str, Any],
) -> _Decision:
    node = nodes[node_id]
    return _Decision(
        reply=_render_node(node),
        current_node_id=node_id,
        answers=answers,
        state=node_id,
    )


def _render_node(node: dict[str, Any]) -> str:
    if node.get("type") == "choice":
        return _render_choice(node)
    return node["prompt"]


def _render_choice(node: dict[str, Any]) -> str:
    lines = [node["prompt"]]
    for index, option in enumerate(node.get("options", []), start=1):
        lines.append(f"{index}. {option['label']}")
    return "\n".join(lines)


def _match_option(message: str, options: list[dict[str, Any]]) -> dict[str, Any] | None:
    stripped = message.strip()
    if stripped.isdigit():
        index = int(stripped) - 1
        if 0 <= index < len(options):
            return options[index]

    normalized = _normalize(message)
    for option in options:
        if _normalize(option["label"]) == normalized:
            return option
    return None


def _build_summary(answers: dict[str, Any]) -> str:
    lines = [SUMMARY_HEADER, ""]
    for key, value in answers.items():
        lines.append(f"- {_humanize(key)}: {value}")
    return "\n".join(lines)


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _persist_funnel(
    db: Session,
    conversation: Conversation,
    decision: _Decision,
    previous_state: str,
) -> None:
    if decision.handoff and previous_state != HANDOFF_STATE:
        conversation_helper.mark_handed_off(db, conversation=conversation)
        _upsert_lead(db, conversation, status="handoff")
        return

    if decision.completed and previous_state != COMPLETED_STATE:
        conversation_helper.mark_completed(db, conversation=conversation)
        _upsert_lead(db, conversation, status="qualified")


def _upsert_lead(db: Session, conversation: Conversation, *, status: str) -> None:
    lead = lead_helper.get_lead_by_conversation(db, conversation.id)
    if lead is None:
        lead_helper.upsert_lead_for_conversation(
            db,
            conversation=conversation,
            answers_by_key=dict(conversation.answers or {}),
            status=status,
        )
    else:
        lead_helper.update_lead_status(db, lead=lead, status=status)


def _normalize(value: str) -> str:
    ascii_text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip().strip(".!,?")


def _should_handoff(normalized_message: str) -> bool:
    return any(token in normalized_message for token in _HANDOFF_TOKENS)
