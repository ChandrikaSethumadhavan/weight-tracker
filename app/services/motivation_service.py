from __future__ import annotations

import random
import textwrap
from typing import Optional

import requests

from ..models import DailySnapshot


QUOTES = [
    "Small victories stack into big wins. Log today and keep the streak alive.",
    "Discipline is remembering what you want most. Today's check-in matters.",
    "You only need a new mindset to start over. This is the rep that counts.",
    "Fuel smart, move bold. Your future self is already cheering.",
    "Streaks love honesty: record it, own it, improve it.",
]

NEGATIVE_LINES = [
    "No shortcuts today. Do the work and make future-you proud.",
    "Tough love time: excuses don't burn calories.",
    "This is a friendly shove. You promised yourself better.",
    "Overshooting the plan? Re-center, refuel smart, and move.",
]


class MotivationService:
    def __init__(self, openai_api_key: Optional[str] = None) -> None:
        self.openai_api_key = openai_api_key
        self._session = requests.Session() if openai_api_key else None

    def pep_talk(self, snapshot: DailySnapshot) -> str:
        if self._session and self.openai_api_key:
            try:
                return self._call_openai(snapshot)
            except Exception:
                pass
        return self._local_message(snapshot)

    def tough_love(self, reason: str) -> str:
        return f"{random.choice(NEGATIVE_LINES)} {reason}"

    def _local_message(self, snapshot: DailySnapshot) -> str:
        base = random.choice(QUOTES)
        summary = (
            f"Start vs today: {snapshot.weight or '??'} kg | "
            f"Net calories: {int(snapshot.net)} | "
            f"Streak: {snapshot.streak} days"
        )
        return textwrap.dedent(
            f"""
            {base}
            {summary}
            """
        ).strip()

    def _call_openai(self, snapshot: DailySnapshot) -> str:
        payload = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a hype trainer for a weight loss buddy app. "
                        "Respond with 2 energetic sentences. Mention the streak "
                        "count and suggest either eating cleaner or moving more "
                        "based on the deficit."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Weight today: {snapshot.weight}; net calories: {snapshot.net}; "
                        f"deficit goal: {snapshot.deficit_goal}; streak: {snapshot.streak}"
                    ),
                },
            ],
        }
        response = self._session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
