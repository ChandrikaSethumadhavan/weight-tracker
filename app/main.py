from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import AppConfig, load_config
from .database import AppRepository
from .models import DailySnapshot, FoodEntry, WeightEntry, WorkoutEntry
from .services.calorie_service import CalorieAdvisor

config = load_config()
repository = AppRepository(config.db_path)
meta_overrides = repository.get_meta_bulk()
if meta_overrides:
  config.apply_overrides(meta_overrides)
calorie_advisor = CalorieAdvisor(config.openai_api_key, config.nutrition_api_key)

FASTING_TARGET_MINUTES = 16 * 60
CICO_KCAL_PER_KG = 7700.0

app = FastAPI(title="GlowUp Weight Journey API", version="2.0.0")

allowed_origins = config.allowed_origins if hasattr(config, "allowed_origins") else ["*"]
if not allowed_origins:
  allowed_origins = ["*"]
app.add_middleware(
  CORSMiddleware,
  allow_origins=allowed_origins,
  allow_methods=["*"],
  allow_headers=["*"],
  allow_credentials=True,
)


def get_repo() -> AppRepository:
  return repository


def get_config() -> AppConfig:
  return config


class SnapshotResponse(BaseModel):
  entry_date: date
  weight: float | None
  mood: str | None = None
  calories_in: float
  calories_out: float
  carbs_in: float
  protein_in: float
  fat_in: float
  streak: int
  deficit_goal: int
  net: float
  needs_more_burn: bool
  needs_less_food: bool


class WeightPayload(BaseModel):
  entry_date: date = Field(default_factory=date.today)
  weight: float = Field(..., gt=0)
  mood: str | None = Field(default=None, max_length=140)


class WeightRecord(WeightPayload):
  pass


class FoodPayload(BaseModel):
  entry_date: date = Field(default_factory=date.today)
  description: str = Field(..., max_length=240)
  brand: str | None = Field(default=None, max_length=120)
  meal_type: str = Field(default="general", max_length=40)
  calories: float | None = Field(default=None, ge=0)
  carbs: float | None = Field(default=None, ge=0)
  protein: float | None = Field(default=None, ge=0)
  fat: float | None = Field(default=None, ge=0)
  source: str | None = Field(default=None, max_length=60)


class FoodRecord(FoodPayload):
  id: int
  source: str


class WorkoutPayload(BaseModel):
  entry_date: date = Field(default_factory=date.today)
  category: str = Field(default="custom", max_length=32)
  description: str = Field(..., max_length=400)
  duration_minutes: float | None = Field(default=None, ge=0)
  calories_burned: float | None = Field(default=None, ge=0)


class WorkoutRecord(WorkoutPayload):
  id: int


class CicoForecastPoint(BaseModel):
  entry_date: date
  predicted_weight: float
  daily_delta_kg: float
  source: str = "justcico-sim"


class FastingHistoryEntry(BaseModel):
  id: int
  start_time: datetime
  end_time: datetime
  duration_minutes: float


class FastingCalendarDay(BaseModel):
  entry_date: date
  fasted: bool
  duration_minutes: float = 0.0


class FastingStatus(BaseModel):
  is_active: bool
  start_time: datetime | None
  elapsed_minutes: float
  remaining_minutes: float
  exceeded_minutes: float
  target_minutes: float = FASTING_TARGET_MINUTES
  history: List[FastingHistoryEntry]
  calendar_days: List[FastingCalendarDay]


class FastingStartPayload(BaseModel):
  start_time: datetime | None = None


class SettingsPayload(BaseModel):
  target_calories: int | None = Field(default=None, ge=800, le=5000)
  deficit_goal: int | None = Field(default=None, ge=0, le=3000)
  reminder_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
  email_smtp_host: str | None = None
  email_smtp_port: int | None = None
  email_username: str | None = None
  email_password: str | None = None
  email_sender: str | None = None
  email_recipient: str | None = None
  openai_api_key: str | None = None
  nutrition_api_key: str | None = None


class SettingsResponse(BaseModel):
  target_calories: int
  deficit_goal: int
  reminder_time: str
  reminder_enabled: bool
  email_smtp_host: str | None = None
  email_smtp_port: int | None = None
  email_username: str | None = None
  email_sender: str | None = None
  email_recipient: str | None = None
  openai_api_key: str | None = None
  nutrition_api_key: str | None = None


def _build_snapshot(target_date: date, repo: AppRepository, cfg: AppConfig) -> SnapshotResponse:
  summary = repo.dump_day_summary(target_date)
  snapshot = DailySnapshot(
    entry_date=target_date,
    weight=summary.get("weight"),
    mood=summary.get("mood"),
    calories_in=summary.get("calories_in", 0.0),
    carbs_in=summary.get("carbs_in", 0.0),
    protein_in=summary.get("protein_in", 0.0),
    fat_in=summary.get("fat_in", 0.0),
    calories_out=summary.get("calories_out", 0.0),
    streak=summary.get("streak", 0),
    deficit_goal=cfg.deficit_goal,
  )
  return SnapshotResponse(
    entry_date=snapshot.entry_date,
    weight=snapshot.weight,
    mood=snapshot.mood,
    calories_in=snapshot.calories_in,
    calories_out=snapshot.calories_out,
    carbs_in=snapshot.carbs_in,
    protein_in=snapshot.protein_in,
    fat_in=snapshot.fat_in,
    streak=snapshot.streak,
    deficit_goal=snapshot.deficit_goal,
    net=snapshot.net,
    needs_more_burn=snapshot.needs_more_burn,
    needs_less_food=snapshot.needs_less_food,
  )


def _settings_from_meta(cfg: AppConfig, meta: Dict[str, str]) -> SettingsResponse:
  reminder_time = meta.get("reminder_time", cfg.reminder.reminder_time.strftime("%H:%M"))
  target_calories = int(meta.get("target_calories", cfg.target_calories))
  deficit_goal = int(meta.get("deficit_goal", cfg.deficit_goal))
  reminder_enabled = meta.get("reminder_enabled", "1").lower() not in {"0", "false", "no"}
  return SettingsResponse(
    target_calories=target_calories,
    deficit_goal=deficit_goal,
    reminder_time=reminder_time,
    reminder_enabled=reminder_enabled,
    email_smtp_host=meta.get("email_smtp_host", cfg.email.smtp_host),
    email_smtp_port=int(meta.get("email_smtp_port", cfg.email.smtp_port)),
    email_username=meta.get("email_username", cfg.email.username),
    email_sender=meta.get("email_sender", cfg.email.sender),
    email_recipient=meta.get("email_recipient", cfg.email.recipient),
    openai_api_key=meta.get("openai_api_key", cfg.openai_api_key),
    nutrition_api_key=meta.get("nutrition_api_key", cfg.nutrition_api_key),
  )


def _generate_cico_forecast(days: int, repo: AppRepository) -> List[CicoForecastPoint]:
  latest_weight = repo.get_latest_weight()
  if latest_weight is None:
    return []
  rows = repo.get_recent_calorie_windows(14)
  deltas: List[float] = []
  for row in rows:
    calories_in = row["calories_in"] or 0.0
    calories_out = row["calories_out"] or 0.0
    delta = (calories_out - calories_in) / CICO_KCAL_PER_KG
    if delta != 0:
      deltas.append(delta)
  if deltas:
    daily_delta = sum(deltas) / len(deltas)
  else:
    daily_delta = -config.deficit_goal / CICO_KCAL_PER_KG
  results: List[CicoForecastPoint] = []
  current_weight = latest_weight
  start_date = date.today() + timedelta(days=1)
  for offset in range(days):
    current_weight += daily_delta
    results.append(
      CicoForecastPoint(
        entry_date=start_date + timedelta(days=offset),
        predicted_weight=round(current_weight, 2),
        daily_delta_kg=round(daily_delta, 4),
      )
    )
  return results


def _build_fasting_status(repo: AppRepository) -> FastingStatus:
  active = repo.get_active_fast()
  history_sessions = repo.get_recent_fasts(30)
  now = datetime.utcnow()
  elapsed = 0.0
  start_time = None
  if active:
    start_time = active.start_time
    elapsed = max(0.0, (now - active.start_time).total_seconds() / 60.0)
  remaining = max(0.0, FASTING_TARGET_MINUTES - elapsed)
  exceeded = max(0.0, elapsed - FASTING_TARGET_MINUTES)
  history: List[FastingHistoryEntry] = []
  for session in history_sessions[:5]:
    if not session.end_time:
      continue
    duration = max(0.0, (session.end_time - session.start_time).total_seconds() / 60.0)
    history.append(
      FastingHistoryEntry(
        id=session.id,
        start_time=session.start_time,
        end_time=session.end_time,
        duration_minutes=round(duration, 1),
      )
    )
  since_date = date.today() - timedelta(days=29)
  entries_by_day: Dict[date, float] = {}
  for session in history_sessions:
    if not session.end_time:
      continue
    day = session.end_time.date()
    duration = max(0.0, (session.end_time - session.start_time).total_seconds() / 60.0)
    entries_by_day[day] = max(entries_by_day.get(day, 0.0), duration)
  calendar_days: List[FastingCalendarDay] = []
  for offset in range(30):
    day = since_date + timedelta(days=offset)
    duration = entries_by_day.get(day, 0.0)
    calendar_days.append(
      FastingCalendarDay(
        entry_date=day,
        fasted=duration > 0.0,
        duration_minutes=round(duration, 1),
      )
    )
  return FastingStatus(
    is_active=active is not None,
    start_time=start_time,
    elapsed_minutes=round(elapsed, 1),
    remaining_minutes=round(remaining, 1),
    exceeded_minutes=round(exceeded, 1),
    history=history,
    calendar_days=calendar_days,
  )


@app.get("/", tags=["meta"])
def index() -> Dict[str, Any]:
  return {"message": "GlowUp Weight Journey API is online.", "docs": "/docs", "frontend": os.environ.get("FRONTEND_URL")}


@app.get("/api/health", tags=["meta"])
def healthcheck() -> Dict[str, str]:
  return {"status": "ok"}


@app.get("/api/snapshot", response_model=SnapshotResponse, tags=["snapshot"])
def get_snapshot(
  entry_date: date | None = Query(default=None, description="ISO date (YYYY-MM-DD) to inspect"),
  repo: AppRepository = Depends(get_repo),
  cfg: AppConfig = Depends(get_config),
) -> SnapshotResponse:
  target = entry_date or date.today()
  return _build_snapshot(target, repo, cfg)


@app.get("/api/weights", response_model=List[WeightRecord], tags=["weights"])
def list_weights(limit: int = Query(default=30, ge=1, le=180), repo: AppRepository = Depends(get_repo)) -> List[WeightRecord]:
  rows = repo.get_weight_history(limit)
  return [WeightRecord(entry_date=row["entry_date"], weight=row["weight"]) for row in rows]


@app.post("/api/weights", response_model=WeightRecord, status_code=status.HTTP_201_CREATED, tags=["weights"])
def upsert_weight(payload: WeightPayload, repo: AppRepository = Depends(get_repo)) -> WeightRecord:
  entry = WeightEntry(entry_date=payload.entry_date, weight=payload.weight, mood=payload.mood)
  repo.upsert_weight(entry)
  return WeightRecord(**payload.dict())


@app.delete("/api/weights/{entry_date}", status_code=status.HTTP_204_NO_CONTENT, tags=["weights"])
def delete_weight(entry_date: date, repo: AppRepository = Depends(get_repo)) -> None:
  repo.delete_weight(entry_date)


@app.get("/api/cico/forecast", response_model=List[CicoForecastPoint], tags=["forecast"])
def cico_forecast(
  days: int = Query(default=7, ge=1, le=30, description="How many days ahead to project."),
  repo: AppRepository = Depends(get_repo),
) -> List[CicoForecastPoint]:
  return _generate_cico_forecast(days, repo)


@app.get("/api/foods", response_model=List[FoodRecord], tags=["foods"])
def list_food(entry_date: date = Query(default=date.today(), description="Date to fetch meal entries for."), repo: AppRepository = Depends(get_repo)) -> List[FoodRecord]:
  rows = repo.get_food_for_date(entry_date)
  return [
    FoodRecord(
      id=row["id"],
      entry_date=entry_date,
      description=row["description"],
      brand=row["brand"],
      meal_type=row["meal_type"],
      calories=row["calories"],
      carbs=row["carbs"],
      protein=row["protein"],
      fat=row["fat"],
      source=row["source"],
    )
    for row in rows
  ]


@app.post("/api/foods", response_model=FoodRecord, status_code=status.HTTP_201_CREATED, tags=["foods"])
def create_food(payload: FoodPayload, repo: AppRepository = Depends(get_repo)) -> FoodRecord:
  description = payload.description.strip()
  brand = payload.brand.strip() if payload.brand else None
  calories = payload.calories
  carbs = payload.carbs
  protein = payload.protein
  fat = payload.fat
  source = payload.source or "manual"
  if calories is None:
    query = f"{brand} {description}".strip() if brand else description
    estimate = calorie_advisor.estimate(query)
    calories = estimate.calories
    carbs = carbs if carbs is not None else estimate.carbs
    protein = protein if protein is not None else estimate.protein
    fat = fat if fat is not None else estimate.fat
    source = estimate.source
  entry = FoodEntry(
    entry_date=payload.entry_date,
    description=description,
    calories=calories or 0.0,
    brand=brand,
    meal_type=payload.meal_type,
    carbs=carbs or 0.0,
    protein=protein or 0.0,
    fat=fat or 0.0,
    source=source,
  )
  entry_id = repo.log_food(entry)
  record = FoodRecord(id=entry_id, **payload.dict())
  record.calories = entry.calories
  record.carbs = entry.carbs
  record.protein = entry.protein
  record.fat = entry.fat
  record.source = entry.source
  record.brand = brand
  return record


@app.delete("/api/foods/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["foods"])
def delete_food(entry_id: int, repo: AppRepository = Depends(get_repo)) -> None:
  repo.delete_food_entry(entry_id)


@app.get("/api/workouts", response_model=List[WorkoutRecord], tags=["workouts"])
def list_workouts(entry_date: date = Query(default=date.today(), description="Date to read workouts from."), repo: AppRepository = Depends(get_repo)) -> List[WorkoutRecord]:
  rows = repo.get_workouts_for_date(entry_date)
  return [
    WorkoutRecord(
      id=row["id"],
      entry_date=entry_date,
      category=row["category"],
      description=row["description"],
      calories_burned=row["calories_burned"],
      duration_minutes=row["duration_minutes"],
    )
    for row in rows
  ]


@app.post("/api/workouts", response_model=WorkoutRecord, status_code=status.HTTP_201_CREATED, tags=["workouts"])
def create_workout(payload: WorkoutPayload, repo: AppRepository = Depends(get_repo)) -> WorkoutRecord:
  calories = payload.calories_burned
  if calories is None:
    if payload.duration_minutes is None:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duration required for calorie estimate.")
    estimate = calorie_advisor.estimate_workout(payload.category, payload.description, payload.duration_minutes)
    calories = estimate.calories
  entry = WorkoutEntry(
    entry_date=payload.entry_date,
    description=payload.description,
    category=payload.category,
    calories_burned=calories,
    duration_minutes=payload.duration_minutes,
  )
  entry_id = repo.log_workout(entry)
  record = WorkoutRecord(id=entry_id, **payload.dict())
  record.calories_burned = calories
  return record


@app.delete("/api/workouts/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["workouts"])
def delete_workout(entry_id: int, repo: AppRepository = Depends(get_repo)) -> None:
  repo.delete_workout_entry(entry_id)


@app.get("/api/fasting", response_model=FastingStatus, tags=["fasting"])
def get_fasting(repo: AppRepository = Depends(get_repo)) -> FastingStatus:
  return _build_fasting_status(repo)


@app.post("/api/fasting/start", response_model=FastingStatus, tags=["fasting"])
def start_fasting(payload: FastingStartPayload | None = None, repo: AppRepository = Depends(get_repo)) -> FastingStatus:
  start_time = payload.start_time if payload and payload.start_time else datetime.utcnow()
  repo.start_fasting(start_time)
  return _build_fasting_status(repo)


@app.post("/api/fasting/stop", response_model=FastingStatus, tags=["fasting"])
def stop_fasting(repo: AppRepository = Depends(get_repo)) -> FastingStatus:
  session = repo.complete_fasting(datetime.utcnow())
  if not session:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active fast to stop.")
  return _build_fasting_status(repo)


@app.get("/api/settings", response_model=SettingsResponse, tags=["settings"])
def get_settings(repo: AppRepository = Depends(get_repo), cfg: AppConfig = Depends(get_config)) -> SettingsResponse:
  meta = repo.get_meta_bulk()
  return _settings_from_meta(cfg, meta)


@app.put("/api/settings", response_model=SettingsResponse, tags=["settings"])
def update_settings(payload: SettingsPayload, repo: AppRepository = Depends(get_repo), cfg: AppConfig = Depends(get_config)) -> SettingsResponse:
  updates = {k: str(v) for k, v in payload.dict(exclude_none=True).items()}
  if not updates:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No settings provided.")
  repo.set_meta_bulk(updates)
  cfg.apply_overrides(updates)
  return _settings_from_meta(cfg, repo.get_meta_bulk())


@app.on_event("shutdown")
def _shutdown() -> None:
  repository.close()


if __name__ == "__main__":
  port = int(os.environ.get("PORT", "8000"))
  import uvicorn

  uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=os.environ.get("RELOAD", "0") == "1")
