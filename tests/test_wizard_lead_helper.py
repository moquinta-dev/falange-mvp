from app.helpers import wizard_lead_helper
from app.helpers.email_client import EmailClient


def test_wizard_lead_email_subject_uses_name() -> None:
    subject = wizard_lead_helper.build_wizard_lead_email_subject(
        segment="Clínica",
        name="Marcos",
    )
    assert subject == "[Novo lead wizard] Marcos — Clínica"


def test_wizard_lead_email_body_includes_flow() -> None:
    body = wizard_lead_helper.build_wizard_lead_email_body(
        lead_id=42,
        segment="Clínica",
        question="Quanto custa?",
        answer="R$250",
        phone="+5571999990000",
        name="Marcos",
        email="marcos@example.com",
    )
    assert "lead_id: 42" not in body
    assert "ID do lead: 42" in body
    assert "Quanto custa?" in body
    assert "R$250" in body
    assert "marcos@example.com" in body


def test_notify_team_of_wizard_lead_sends_email() -> None:
    sent: list[tuple[str, str, str]] = []

    class _FakeEmailClient(EmailClient):
        @property
        def is_configured(self) -> bool:
            return True

        def send(self, *, to: str, subject: str, body: str) -> None:
            sent.append((to, subject, body))

    ok = wizard_lead_helper.notify_team_of_wizard_lead(
        _FakeEmailClient(
            host="smtp.example.com",
            port=465,
            username="u",
            password="p",
            sender="support@falangelabs.io",
        ),
        notify_target="support@falangelabs.io",
        lead_id=7,
        segment="Clínica",
        question="Horário?",
        answer="Segunda a sexta",
        phone="+5571999990000",
        name=None,
        email=None,
    )

    assert ok is True
    assert len(sent) == 1
    assert sent[0][0] == "support@falangelabs.io"
    assert "[Novo lead wizard]" in sent[0][1]


def test_notify_team_of_wizard_lead_skips_when_unconfigured() -> None:
    client = EmailClient(host="", port=465, username="", password="", sender="")
    ok = wizard_lead_helper.notify_team_of_wizard_lead(
        client,
        notify_target="support@falangelabs.io",
        lead_id=1,
        segment="Clínica",
        question="?",
        answer="!",
        phone="+5571000000000",
        name=None,
        email=None,
    )
    assert ok is False
