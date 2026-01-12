from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .models import FoodEntry, FastingSession, WeightEntry, WorkoutEntry


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS weights (
    entry_date TEXT PRIMARY KEY,
    weight REAL NOT NULL,
    mood TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS food_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    description TEXT NOT NULL,
    brand TEXT,
    meal_type TEXT NOT NULL DEFAULT 'general',
    calories REAL NOT NULL,
    carbs REAL NOT NULL DEFAULT 0,
    protein REAL NOT NULL DEFAULT 0,
    fat REAL NOT NULL DEFAULT 0,
    source TEXT DEFAULT 'manual',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'custom',
    calories_burned REAL NOT NULL,
    duration_minutes REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS streaks (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_streak INTEGER NOT NULL DEFAULT 0,
    last_check_in_date TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fasting_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _date_str(value: date) -> str:
    return value.isoformat()


def _parse_date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


def _datetime_str(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class AppRepository:
    """SQLite helper with tiny repository conveniences."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)
        self._ensure_schema_upgrades()

    def _ensure_schema_upgrades(self) -> None:
        def has_column(table: str, column: str) -> bool:
            cur = self._conn.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cur.fetchall())

        with self._lock, self._conn:
            food_columns = {
                "meal_type": "ALTER TABLE food_entries ADD COLUMN meal_type TEXT NOT NULL DEFAULT 'general'",
                "carbs": "ALTER TABLE food_entries ADD COLUMN carbs REAL NOT NULL DEFAULT 0",
                "protein": "ALTER TABLE food_entries ADD COLUMN protein REAL NOT NULL DEFAULT 0",
                "fat": "ALTER TABLE food_entries ADD COLUMN fat REAL NOT NULL DEFAULT 0",
                "brand": "ALTER TABLE food_entries ADD COLUMN brand TEXT",
            }
            for column, statement in food_columns.items():
                if not has_column("food_entries", column):
                    self._conn.execute(statement)
            if not has_column("workouts", "category"):
                self._conn.execute("ALTER TABLE workouts ADD COLUMN category TEXT NOT NULL DEFAULT 'custom'")

    # --- meta helpers -------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO app_meta(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def get_meta_bulk(self) -> Dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM app_meta").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_meta_bulk(self, mapping: Dict[str, str]) -> None:
        with self._lock, self._conn:
            self._conn.executemany(
                """
                INSERT INTO app_meta(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                list(mapping.items()),
            )

    # --- weight tracking ----------------------------------------------
    def upsert_weight(self, entry: WeightEntry) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO weights(entry_date, weight, mood)
                VALUES(?, ?, ?)
                ON CONFLICT(entry_date) DO UPDATE SET weight=excluded.weight, mood=excluded.mood
                """,
                (_date_str(entry.entry_date), entry.weight, entry.mood),
            )

    def get_weight(self, entry_date: date) -> Optional[float]:
        with self._lock:
            row = self._conn.execute("SELECT weight FROM weights WHERE entry_date=?", (_date_str(entry_date),)).fetchone()
        return row["weight"] if row else None

    def get_weight_history(self, limit: int = 30) -> List[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT entry_date, weight FROM weights ORDER BY entry_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed(rows))

    def get_starting_weight(self) -> Optional[float]:
        with self._lock:
            row = self._conn.execute("SELECT weight FROM weights ORDER BY entry_date ASC LIMIT 1").fetchone()
        return row["weight"] if row else None

    def get_latest_weight(self) -> Optional[float]:
        with self._lock:
            row = self._conn.execute("SELECT weight FROM weights ORDER BY entry_date DESC LIMIT 1").fetchone()
        return row["weight"] if row else None

    def delete_weight(self, entry_date: date) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM weights WHERE entry_date=?", (_date_str(entry_date),))

    # --- food ---------------------------------------------------------
    def log_food(self, entry: FoodEntry) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO food_entries(entry_date, description, brand, meal_type, calories, carbs, protein, fat, source)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _date_str(entry.entry_date),
                    entry.description,
                    entry.brand,
                    entry.meal_type,
                    entry.calories,
                    entry.carbs,
                    entry.protein,
                    entry.fat,
                    entry.source,
                ),
            )
            return cursor.lastrowid

    def get_food_for_date(self, entry_date: date) -> List[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, description, brand, meal_type, calories, carbs, protein, fat, source
                FROM food_entries WHERE entry_date=?
                ORDER BY id
                """,
                (_date_str(entry_date),),
            ).fetchall()
        return rows

    def get_recent_foods(self, limit: int = 30) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                """
                SELECT id, entry_date, description, brand, meal_type, calories, carbs, protein, fat, source
                FROM food_entries
                ORDER BY entry_date DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    # --- workouts -----------------------------------------------------
    def log_workout(self, entry: WorkoutEntry) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO workouts(entry_date, description, category, calories_burned, duration_minutes) VALUES(?, ?, ?, ?, ?)",
                (
                    _date_str(entry.entry_date),
                    entry.description,
                    entry.category,
                    entry.calories_burned,
                    entry.duration_minutes,
                ),
            )
            return cursor.lastrowid

    def get_workouts_for_date(self, entry_date: date) -> List[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, description, category, calories_burned, duration_minutes FROM workouts WHERE entry_date=? ORDER BY id",
                (_date_str(entry_date),),
            ).fetchall()
        return rows

    def delete_food_entry(self, entry_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM food_entries WHERE id=?", (entry_id,))

    def delete_workout_entry(self, entry_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM workouts WHERE id=?", (entry_id,))

    # --- totals -------------------------------------------------------
    def get_daily_totals(self, entry_date: date) -> Dict[str, float]:
        with self._lock:
            food = self._conn.execute(
                """
                SELECT
                    COALESCE(SUM(calories), 0) AS calories_in,
                    COALESCE(SUM(carbs), 0) AS carbs_in,
                    COALESCE(SUM(protein), 0) AS protein_in,
                    COALESCE(SUM(fat), 0) AS fat_in
                FROM food_entries WHERE entry_date=?
                """,
                (_date_str(entry_date),),
            ).fetchone()
            workouts = self._conn.execute(
                "SELECT COALESCE(SUM(calories_burned), 0) as calories_out FROM workouts WHERE entry_date=?",
                (_date_str(entry_date),),
            ).fetchone()
        return {
            "calories_in": float(food["calories_in"] or 0),
            "carbs_in": float(food["carbs_in"] or 0),
            "protein_in": float(food["protein_in"] or 0),
            "fat_in": float(food["fat_in"] or 0),
            "calories_out": float(workouts["calories_out"] or 0),
        }

    def get_meal_breakdown(self, entry_date: date) -> List[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT meal_type,
                       COALESCE(SUM(calories), 0) AS calories,
                       COALESCE(SUM(carbs), 0) AS carbs,
                       COALESCE(SUM(protein), 0) AS protein,
                       COALESCE(SUM(fat), 0) AS fat
                FROM food_entries
                WHERE entry_date=?
                GROUP BY meal_type
                """,
                (_date_str(entry_date),),
            ).fetchall()
        return rows

    def get_recent_calorie_windows(self, days: int = 14) -> List[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT w.entry_date,
                       COALESCE(f.total_in, 0) AS calories_in,
                       COALESCE(x.total_out, 0) AS calories_out,
                       wt.weight
                FROM (
                    SELECT DISTINCT entry_date FROM (
                        SELECT entry_date FROM weights
                        UNION
                        SELECT entry_date FROM food_entries
                        UNION
                        SELECT entry_date FROM workouts
                    )
                ) w
                LEFT JOIN weights wt ON wt.entry_date = w.entry_date
                LEFT JOIN (
                    SELECT entry_date, SUM(calories) AS total_in
                    FROM food_entries
                    GROUP BY entry_date
                ) f ON f.entry_date = w.entry_date
                LEFT JOIN (
                    SELECT entry_date, SUM(calories_burned) AS total_out
                    FROM workouts
                    GROUP BY entry_date
                ) x ON x.entry_date = w.entry_date
                ORDER BY w.entry_date DESC
                LIMIT ?
                """,
                (days,),
            ).fetchall()
        return list(reversed(rows))

    # --- fasting -------------------------------------------------------
    def start_fasting(self, start_time: datetime) -> int:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id FROM fasting_sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return row["id"]
            cursor = self._conn.execute(
                "INSERT INTO fasting_sessions(start_time, status) VALUES(?, 'active')",
                (_datetime_str(start_time),),
            )
            return cursor.lastrowid

    def complete_fasting(self, end_time: datetime) -> Optional[FastingSession]:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id, start_time FROM fasting_sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE fasting_sessions SET end_time=?, status='completed' WHERE id=?",
                (_datetime_str(end_time), row["id"]),
            )
        return FastingSession(
            id=row["id"],
            start_time=_parse_datetime(row["start_time"]),
            end_time=end_time,
        )

    def get_active_fast(self) -> Optional[FastingSession]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, start_time FROM fasting_sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return FastingSession(
            id=row["id"],
            start_time=_parse_datetime(row["start_time"]),
            end_time=None,
        )

    def get_recent_fasts(self, limit: int = 5) -> List[FastingSession]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, start_time, end_time
                FROM fasting_sessions
                WHERE status='completed'
                ORDER BY end_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        sessions: List[FastingSession] = []
        for row in rows:
            sessions.append(
                FastingSession(
                    id=row["id"],
                    start_time=_parse_datetime(row["start_time"]),
                    end_time=_parse_datetime(row["end_time"]),
                )
            )
        return sessions

    # --- streaks ------------------------------------------------------
    def bump_streak(self, today: date) -> int:
        with self._lock, self._conn:
            row = self._conn.execute("SELECT current_streak, last_check_in_date FROM streaks WHERE id=1").fetchone()
            if not row:
                streak = 1
                self._conn.execute(
                    "INSERT INTO streaks(id, current_streak, last_check_in_date) VALUES(1, ?, ?)",
                    (streak, _date_str(today)),
                )
                return streak
            last_date = _parse_date(row["last_check_in_date"])
            if last_date == today:
                return row["current_streak"]
            if last_date == today - timedelta(days=1):
                streak = row["current_streak"] + 1
            else:
                streak = 1
            self._conn.execute(
                "UPDATE streaks SET current_streak=?, last_check_in_date=? WHERE id=1",
                (streak, _date_str(today)),
            )
            return streak

    def get_streak(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT current_streak FROM streaks WHERE id=1").fetchone()
        return row["current_streak"] if row else 0

    # --- helpers ------------------------------------------------------
    def dump_day_summary(self, entry_date: date) -> Dict[str, float]:
        totals = self.get_daily_totals(entry_date)
        with self._lock:
            weight_row = self._conn.execute(
                "SELECT weight, mood FROM weights WHERE entry_date=?",
                (_date_str(entry_date),),
            ).fetchone()
        streak = self.get_streak()
        return {
            "weight": weight_row["weight"] if weight_row else None,
            "mood": weight_row["mood"] if weight_row else None,
            "calories_in": totals["calories_in"],
             "carbs_in": totals["carbs_in"],
             "protein_in": totals["protein_in"],
             "fat_in": totals["fat_in"],
            "calories_out": totals["calories_out"],
            "streak": streak,
        }

    def close(self) -> None:
        self._conn.close()
