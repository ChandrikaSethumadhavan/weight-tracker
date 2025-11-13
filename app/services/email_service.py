from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..models import EmailSettings


class EmailService:
    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.username
            and self.settings.password
            and self.settings.sender
            and self.settings.recipient
        )

    def send_motivation(self, subject: str, body: str) -> None:
        if not self.is_configured:
            raise RuntimeError("Email settings are incomplete.")
        msg = EmailMessage()
        msg["From"] = self.settings.sender
        msg["To"] = self.settings.recipient
        msg["Subject"] = subject
        msg.set_content(body)
        context = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
        try:
            if self.settings.use_tls:
                context.starttls()
            context.login(self.settings.username, self.settings.password)
            context.send_message(msg)
        finally:
            context.quit()
