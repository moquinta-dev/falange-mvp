import smtplib

import pytest

from app.helpers import notification_helper
from app.helpers.email_client import EmailClient, EmailNotConfiguredError


class _FakeSMTP:
    last: "_FakeSMTP | None" = None

    def __init__(self, host, port, timeout=None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged: tuple[str, str] | None = None
        self.started_tls = False
        self.sent: list = []
        _FakeSMTP.last = self

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username, password) -> None:
        self.logged = (username, password)

    def send_message(self, message) -> None:
        self.sent.append(message)


def test_email_client_sends_over_ssl(monkeypatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    client = EmailClient(
        host="smtp.hostinger.com",
        port=465,
        username="support@falangelabs.io",
        password="secret",
        sender="support@falangelabs.io",
        use_ssl=True,
    )

    client.send(to="dona@example.com", subject="Assunto", body="Corpo")

    server = _FakeSMTP.last
    assert server is not None
    assert server.host == "smtp.hostinger.com"
    assert server.port == 465
    assert server.logged == ("support@falangelabs.io", "secret")
    assert len(server.sent) == 1
    message = server.sent[0]
    assert message["To"] == "dona@example.com"
    assert message["Subject"] == "Assunto"
    assert message["From"] == "support@falangelabs.io"
    assert message.get_content().strip() == "Corpo"


def test_email_client_uses_starttls_when_not_ssl(monkeypatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    client = EmailClient(
        host="smtp.example.com",
        port=587,
        username="u",
        password="p",
        sender="from@example.com",
        use_ssl=False,
    )

    client.send(to="to@example.com", subject="S", body="B")

    assert _FakeSMTP.last.started_tls is True


def test_email_client_raises_when_not_configured() -> None:
    client = EmailClient(host="", port=465, username="", password="", sender="")
    with pytest.raises(EmailNotConfiguredError):
        client.send(to="x@example.com", subject="S", body="B")


class _RecordingEmailClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to, subject, body) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


class _BrokenEmailClient:
    def send(self, *, to, subject, body) -> None:
        raise RuntimeError("smtp down")


def test_notify_sends_email_with_triagem_structure() -> None:
    client = _RecordingEmailClient()

    sent = notification_helper.notify_tenant_of_completion(
        client,
        tenant_name="Natália",
        notify_channel="email",
        notify_target="dona@example.com",
        lead_phone="5571999999999",
        summary=None,
        answers={
            "nome": "Marina",
            "idade": "32",
            "interesse": "Aulas de Personal",
            "modalidade": "Presencial",
        },
    )

    assert sent is True
    assert len(client.sent) == 1
    message = client.sent[0]
    assert message["to"] == "dona@example.com"
    assert message["subject"] == "[Novo Lead Triagem] - Marina - Aulas de Personal"
    assert message["body"] == (
        "Ficha de Triagem - Assistente Virtual\n"
        "\n"
        "* Nome: Marina\n"
        "* Idade: 32\n"
        "* Interesse: Aulas de Personal\n"
        "* Formato/Foco: Presencial\n"
        "* WhatsApp do Cliente: 5571999999999"
    )


def test_notify_skips_without_target() -> None:
    client = _RecordingEmailClient()

    sent = notification_helper.notify_tenant_of_completion(
        client,
        tenant_name="Natália",
        notify_channel="email",
        notify_target=None,
        lead_phone="5571999999999",
        summary="x",
    )

    assert sent is False
    assert client.sent == []


def test_notify_skips_unsupported_channel() -> None:
    client = _RecordingEmailClient()

    sent = notification_helper.notify_tenant_of_completion(
        client,
        tenant_name="Natália",
        notify_channel="whatsapp",
        notify_target="5571888888888",
        lead_phone="5571999999999",
        summary="x",
    )

    assert sent is False
    assert client.sent == []


def test_notify_swallows_send_errors() -> None:
    sent = notification_helper.notify_tenant_of_completion(
        _BrokenEmailClient(),
        tenant_name="Natália",
        notify_channel="email",
        notify_target="dona@example.com",
        lead_phone="5571999999999",
        summary="x",
    )

    assert sent is False


def test_build_email_body_falls_back_to_answers_for_non_triagem() -> None:
    body = notification_helper.build_email_body(
        tenant_name="Falangelabs",
        lead_phone="5571999999999",
        summary=None,
        answers={"business": "Academia", "goal": "Agendamento"},
    )

    assert "Business: Academia" in body
    assert "Goal: Agendamento" in body


def test_build_triagem_email_uses_objetivo_as_formato_foco() -> None:
    body = notification_helper.build_triagem_email_body(
        lead_phone="5571888777777",
        answers={
            "nome": "Ana",
            "idade": "28",
            "interesse": "Consultoria Online",
            "objetivo": "Fortalecimento + Corrida",
        },
    )

    assert "* Formato/Foco: Fortalecimento + Corrida" in body


def test_build_triagem_email_v1_faixa_etaria() -> None:
    body = notification_helper.build_triagem_email_body(
        lead_phone="5571999999999",
        answers={
            "nome": "Marina",
            "faixa_etaria": "30-40",
            "interesse": "Aulas de Yoga",
            "modalidade": "Particular",
        },
    )

    assert "* Idade: 30-40" in body
    assert "* Formato/Foco: Particular" in body
