from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6 import QtCore

from ..models import ReminderSettings
from .email_service import EmailService


class ReminderService(QtCore.QObject):
    reminderTriggered = QtCore.pyqtSignal(str)
    emailTriggered = QtCore.pyqtSignal(str)

    def __init__(
        self,
        repo,
        email_service: EmailService,
        settings: ReminderSettings,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.email_service = email_service
        self.settings = settings
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._maybe_nudge)
        self._timer.start()

    def _maybe_nudge(self) -> None:
        if not self.settings.enabled:
            return
        now = datetime.now()
        reminder_time = datetime.combine(now.date(), self.settings.reminder_time)
        if now < reminder_time or now - reminder_time > timedelta(hours=1):
            return
        today = now.date().isoformat()
        last = self.repo.get_meta("last_reminder")
        if last == today:
            return
        self.repo.set_meta("last_reminder", today)
        message = "Quick check-in time! Log your weight and meals for the day."
        self.reminderTriggered.emit(message)
        if self.email_service.is_configured:
            try:
                last_email = self.repo.get_meta("last_email_date")
                if last_email != today:
                    self.email_service.send_motivation("Daily Weight Loss Pep Talk", message)
                    self.repo.set_meta("last_email_date", today)
                    self.emailTriggered.emit("Motivation email sent.")
            except Exception as exc:  # pragma: no cover - relies on network
                self.emailTriggered.emit(f"Email failed: {exc}")
