from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional


@dataclass
class WeightEntry:
    entry_date: date
    weight: float
    mood: Optional[str] = None


@dataclass
class FoodEntry:
    entry_date: date
    description: str
    calories: float
    brand: Optional[str] = None
    meal_type: str = "general"
    carbs: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    source: str = "manual"


@dataclass
class WorkoutEntry:
    entry_date: date
    description: str
    calories_burned: float
    category: str = "custom"
    duration_minutes: Optional[float] = None


@dataclass
class DailySnapshot:
    entry_date: date
    weight: Optional[float]
    calories_in: float
    calories_out: float
    streak: int
    deficit_goal: int
    carbs_in: float = 0.0
    protein_in: float = 0.0
    fat_in: float = 0.0
    mood: Optional[str] = None
    message: Optional[str] = None

    @property
    def net(self) -> float:
        return self.calories_in - self.calories_out

    @property
    def needs_more_burn(self) -> bool:
        return self.net > self.deficit_goal

    @property
    def needs_less_food(self) -> bool:
        return self.net > self.deficit_goal


@dataclass
class EmailSettings:
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    use_tls: bool = True


@dataclass
class ReminderSettings:
    enabled: bool = True
    reminder_time: time = time(8, 0)


@dataclass
class FastingSession:
    id: int
    start_time: datetime
    end_time: Optional[datetime]

    @property
    def is_active(self) -> bool:
        return self.end_time is None

    def duration(self) -> float:
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()
