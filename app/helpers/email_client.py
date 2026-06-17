"""Cliente SMTP mínimo para notificações transacionais (Fase 2).

Usa apenas a stdlib (``smtplib`` + ``email``) — sem dependência nova. O envio é
bloqueante e deve rodar fora do caminho da resposta HTTP (BackgroundTask), nunca
no event loop. A interface é propositalmente pequena para que trocar o provedor
(ex.: Resend/SES via API) depois seja só implementar outro ``send``.
"""

import smtplib
from email.message import EmailMessage

from app.core.settings import Settings, get_settings


class EmailNotConfiguredError(RuntimeError):
    """SMTP não configurado (host/credenciais ausentes)."""


class EmailClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_ssl: bool = True,
        timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender or username
        self._use_ssl = use_ssl
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._sender)

    def send(self, *, to: str, subject: str, body: str) -> None:
        if not self.is_configured:
            raise EmailNotConfiguredError("SMTP host/remetente não configurados")

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        if self._use_ssl:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout) as server:
                self._login_and_send(server, message)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
                server.starttls()
                self._login_and_send(server, message)

    def _login_and_send(self, server: smtplib.SMTP, message: EmailMessage) -> None:
        if self._username and self._password:
            server.login(self._username, self._password)
        server.send_message(message)


def get_email_client(settings: Settings | None = None) -> EmailClient:
    settings = settings or get_settings()
    return EmailClient(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        sender=settings.smtp_from or settings.smtp_username,
        use_ssl=settings.smtp_use_ssl,
    )
