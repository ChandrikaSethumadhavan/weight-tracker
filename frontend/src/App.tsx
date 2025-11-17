import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  CicoForecastPoint,
  FoodRecord,
  FastingStatus,
  Snapshot,
  WeightRecord,
  WorkoutPayload,
  WorkoutRecord,
} from "./types";

const MEAL_OPTIONS = ["breakfast", "lunch", "dinner", "snack", "general"];
const WORKOUT_CARDS = [
  { id: "legs", title: "Leg Day", details: "Squats, lunges, deadlifts" },
  { id: "abs", title: "Abs/Core", details: "Planks, crunches, hollow holds" },
  { id: "arms", title: "Arms & Back", details: "Pull-ups, rows, curls" },
  { id: "cardio", title: "Cardio", details: "Running, cycling, HIIT" },
  { id: "custom", title: "Custom", details: "Anything else" },
];
const todayISO = new Date().toISOString().slice(0, 10);

type WeightFormState = { weight: string; mood: string };
type FoodFormState = {
  description: string;
  brand: string;
  meal_type: string;
  calories: string;
  carbs: string;
  protein: string;
  fat: string;
};
type WorkoutFormState = { category: string; description: string; duration_minutes: string; calories_burned: string };

function App() {
  const [selectedDate, setSelectedDate] = useState(todayISO);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [weights, setWeights] = useState<WeightRecord[]>([]);
  const [foods, setFoods] = useState<FoodRecord[]>([]);
  const [workouts, setWorkouts] = useState<WorkoutRecord[]>([]);
  const [forecast, setForecast] = useState<CicoForecastPoint[]>([]);
  const [fasting, setFasting] = useState<FastingStatus | null>(null);
  const [manualStart, setManualStart] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [weightForm, setWeightForm] = useState<WeightFormState>({ weight: "", mood: "" });
  const [foodForm, setFoodForm] = useState<FoodFormState>({
    description: "",
    brand: "",
    meal_type: MEAL_OPTIONS[0],
    calories: "",
    carbs: "",
    protein: "",
    fat: "",
  });
  const [workoutForm, setWorkoutForm] = useState<WorkoutFormState>({
    category: "custom",
    description: "",
    duration_minutes: "",
    calories_burned: "",
  });

  useEffect(() => {
    refreshSnapshot();
    refreshDayEntries();
    refreshForecast();
  }, [selectedDate]);

  useEffect(() => {
    refreshWeights();
    refreshFasting();
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      refreshFasting();
    }, 30000);
    return () => clearInterval(id);
  }, []);

  const refreshSnapshot = async () => {
    try {
      const data = await api.getSnapshot(selectedDate);
      setSnapshot(data);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const refreshWeights = async () => {
    try {
      const rows = await api.getWeights();
      setWeights(rows);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const refreshDayEntries = async () => {
    try {
      const [mealRows, workoutRows] = await Promise.all([api.getFoods(selectedDate), api.getWorkouts(selectedDate)]);
      setFoods(mealRows);
      setWorkouts(workoutRows);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const refreshForecast = async () => {
    try {
      const points = await api.getForecast();
      setForecast(points);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const refreshFasting = async () => {
    try {
      const status = await api.getFastingStatus();
      setFasting(status);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleWeightSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const value = Number(weightForm.weight);
    if (!value || Number.isNaN(value)) {
      setError("Enter a valid weight.");
      return;
    }
    setLoading(true);
    try {
      await api.saveWeight({ entry_date: selectedDate, weight: value, mood: weightForm.mood || null });
      setWeightForm({ weight: "", mood: "" });
      await Promise.all([refreshWeights(), refreshSnapshot(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleFoodSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!foodForm.description.trim()) {
      setError("Describe your meal first.");
      return;
    }
    const maybeNumber = (value: string) => (value.trim() ? Number(value) : undefined);
    const payload = {
      entry_date: selectedDate,
      description: foodForm.description.trim(),
      meal_type: foodForm.meal_type,
      brand: foodForm.brand.trim() || undefined,
      calories: maybeNumber(foodForm.calories),
      carbs: maybeNumber(foodForm.carbs),
      protein: maybeNumber(foodForm.protein),
      fat: maybeNumber(foodForm.fat),
    };
    setLoading(true);
    try {
      await api.createFood(payload);
      setFoodForm({
        description: "",
        brand: "",
        meal_type: foodForm.meal_type,
        calories: "",
        carbs: "",
        protein: "",
        fat: "",
      });
      await Promise.all([refreshSnapshot(), refreshDayEntries(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleWorkoutSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!workoutForm.description.trim()) {
      setError("Describe the workout first.");
      return;
    }
    const duration = workoutForm.duration_minutes.trim() ? Number(workoutForm.duration_minutes) : undefined;
    const caloriesOverride = workoutForm.calories_burned.trim() ? Number(workoutForm.calories_burned) : undefined;
    setLoading(true);
    try {
      const payload: WorkoutPayload = {
        entry_date: selectedDate,
        category: workoutForm.category,
        description: workoutForm.description.trim(),
      };
      if (duration !== undefined && !Number.isNaN(duration)) {
        payload.duration_minutes = duration;
      }
      if (caloriesOverride !== undefined && !Number.isNaN(caloriesOverride)) {
        payload.calories_burned = caloriesOverride;
      }
      await api.createWorkout(payload);
      setWorkoutForm({
        category: workoutForm.category,
        description: "",
        duration_minutes: "",
        calories_burned: "",
      });
      await Promise.all([refreshSnapshot(), refreshDayEntries(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const deleteMeal = async (id: number) => {
    setLoading(true);
    try {
      await api.deleteFood(id);
      await Promise.all([refreshSnapshot(), refreshDayEntries(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const deleteWorkout = async (id: number) => {
    setLoading(true);
    try {
      await api.deleteWorkout(id);
      await Promise.all([refreshSnapshot(), refreshDayEntries(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const deleteWeight = async (entryDate: string) => {
    setLoading(true);
    try {
      await api.deleteWeight(entryDate);
      await Promise.all([refreshWeights(), refreshSnapshot(), refreshForecast()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleStartFast = async () => {
    try {
      const status = await api.startFasting(manualStart ? new Date(manualStart).toISOString() : undefined);
      setFasting(status);
      setManualStart("");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleStopFast = async () => {
    try {
      const status = await api.stopFasting();
      setFasting(status);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const fastingProgress = useMemo(() => {
    if (!fasting || !fasting.target_minutes) {
      return 0;
    }
    return Math.min(1, fasting.elapsed_minutes / fasting.target_minutes);
  }, [fasting]);
  const fastingTargetMinutes = fasting?.target_minutes ?? 16 * 60;
  const fastingElapsed = fasting?.elapsed_minutes ?? 0;
  const fastingRemaining = fasting?.remaining_minutes ?? Math.max(0, fastingTargetMinutes - fastingElapsed);
  const fastingExceeded = fasting?.exceeded_minutes ?? Math.max(0, fastingElapsed - fastingTargetMinutes);
  const fastingHistory = fasting?.history ?? [];
  const fastingCalendar = fasting?.calendar_days ?? [];

  const summaryBadge = useMemo(() => {
    if (!snapshot) return null;
    return snapshot.needs_more_burn
      ? { text: "Calorie deficit not met", tone: "#f87171" }
      : { text: "Great deficit today", tone: "#22c55e" };
  }, [snapshot]);

  return (
    <div className="app-grid">
      <header>
        <h1>GlowUp Weight Journey</h1>
        <p>FastAPI + React, ready for desktop and mobile browsers.</p>
      </header>

      <section className="card hero">
        <div className="hero-controls">
          <label>
            Track date
            <input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
          </label>
        </div>
        {snapshot ? (
          <>
            <div className="tiles">
              <div>
                <p className="eyebrow">Weight today</p>
                <h2>{snapshot.weight ? `${snapshot.weight.toFixed(1)} kg` : "Log weight"}</h2>
              </div>
              <div>
                <p className="eyebrow">Net calories</p>
                <h2>{snapshot.net.toFixed(0)} kcal</h2>
              </div>
              <div>
                <p className="eyebrow">Streak</p>
                <h2>{snapshot.streak} days</h2>
              </div>
              <div>
                <p className="eyebrow">Mood</p>
                <h2>{snapshot.mood || "—"}</h2>
              </div>
            </div>
            {summaryBadge && (
              <div className="badge" style={{ background: `${summaryBadge.tone}15`, color: summaryBadge.tone }}>
                {summaryBadge.text}
              </div>
            )}
            <div className="macro-grid">
              <span>Carbs {snapshot.carbs_in.toFixed(0)} g</span>
              <span>Protein {snapshot.protein_in.toFixed(0)} g</span>
              <span>Fat {snapshot.fat_in.toFixed(0)} g</span>
            </div>
          </>
        ) : (
          <p>Loading snapshot...</p>
        )}
      </section>

      {error && (
        <div className="card error">
          <strong>Oops:</strong> {error}
        </div>
      )}

      <section className="card form-grid">
        <div>
          <h3>Log weight</h3>
          <form onSubmit={handleWeightSubmit}>
            <input
              type="number"
              placeholder="Weight in kg"
              value={weightForm.weight}
              onChange={(event) => setWeightForm((prev) => ({ ...prev, weight: event.target.value }))}
            />
            <input
              type="text"
              placeholder="Mood (optional)"
              value={weightForm.mood}
              onChange={(event) => setWeightForm((prev) => ({ ...prev, mood: event.target.value }))}
            />
            <button type="submit" disabled={loading}>
              Save weight
            </button>
          </form>
        </div>
        <div>
          <h3>Recent weights</h3>
          <ul className="list">
            {weights.length ? (
              weights.map((row) => (
                <li key={row.entry_date}>
                  <div>
                    <strong>{row.weight.toFixed(1)} kg</strong>
                    <span className="muted">{row.entry_date}</span>
                  </div>
                  <button type="button" onClick={() => deleteWeight(row.entry_date)} disabled={loading}>
                    Delete
                  </button>
                </li>
              ))
            ) : (
              <li className="muted">Log your first weight to see history here.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="card form-grid">
        <div>
          <h3>Meals</h3>
          <form onSubmit={handleFoodSubmit}>
            <input
              type="text"
              placeholder="What did you eat?"
              value={foodForm.description}
              onChange={(event) => setFoodForm((prev) => ({ ...prev, description: event.target.value }))}
            />
            <input
              type="text"
              placeholder="Brand or restaurant (optional)"
              value={foodForm.brand}
              onChange={(event) => setFoodForm((prev) => ({ ...prev, brand: event.target.value }))}
            />
            <select
              value={foodForm.meal_type}
              onChange={(event) => setFoodForm((prev) => ({ ...prev, meal_type: event.target.value }))}
            >
              {MEAL_OPTIONS.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
            <div className="triple">
              <input
                type="number"
                placeholder="Calories (leave blank to auto-estimate)"
                value={foodForm.calories}
                onChange={(event) => setFoodForm((prev) => ({ ...prev, calories: event.target.value }))}
              />
              <input
                type="number"
                placeholder="Carbs (g)"
                value={foodForm.carbs}
                onChange={(event) => setFoodForm((prev) => ({ ...prev, carbs: event.target.value }))}
              />
              <input
                type="number"
                placeholder="Protein (g)"
                value={foodForm.protein}
                onChange={(event) => setFoodForm((prev) => ({ ...prev, protein: event.target.value }))}
              />
            </div>
            <input
              type="number"
              placeholder="Fat (g)"
              value={foodForm.fat}
              onChange={(event) => setFoodForm((prev) => ({ ...prev, fat: event.target.value }))}
            />
            <small className="muted">Skip macros to let GPT estimate them for you.</small>
            <button type="submit" disabled={loading}>
              Add meal
            </button>
          </form>
        </div>
        <div>
          <h3>Logged meals</h3>
          <table>
            <thead>
              <tr>
                <th>Meal</th>
                <th>Calories</th>
                <th style={{ width: 80 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {foods.map((meal) => (
                <tr key={meal.id}>
                  <td>
                    <strong>{meal.description}</strong>
                    <div className="muted">
                      {meal.meal_type}
                      {meal.brand ? ` · ${meal.brand}` : ""}
                    </div>
                    <div className="tag">{meal.source}</div>
                  </td>
                  <td>{meal.calories.toFixed(0)}</td>
                  <td>
                    <button type="button" onClick={() => deleteMeal(meal.id)} disabled={loading}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!foods.length && (
                <tr>
                  <td colSpan={3}>Log a meal to see it here.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card form-grid">
        <div>
          <h3>Workouts</h3>
          <div className="card-grid">
            {WORKOUT_CARDS.map((card) => (
              <button
                key={card.id}
                type="button"
                className={`pill ${workoutForm.category === card.id ? "pill--active" : ""}`}
                onClick={() => setWorkoutForm((prev) => ({ ...prev, category: card.id }))}
              >
                <strong>{card.title}</strong>
                <span>{card.details}</span>
              </button>
            ))}
          </div>
          <form onSubmit={handleWorkoutSubmit}>
            <input
              type="text"
              placeholder="What exercises did you do?"
              value={workoutForm.description}
              onChange={(event) => setWorkoutForm((prev) => ({ ...prev, description: event.target.value }))}
            />
            <input
              type="number"
              placeholder="Duration (minutes)"
              value={workoutForm.duration_minutes}
              onChange={(event) => setWorkoutForm((prev) => ({ ...prev, duration_minutes: event.target.value }))}
            />
            <input
              type="number"
              placeholder="Override calories (optional)"
              value={workoutForm.calories_burned}
              onChange={(event) => setWorkoutForm((prev) => ({ ...prev, calories_burned: event.target.value }))}
            />
            <small className="muted">
              Leave calories empty and we&apos;ll ask GPT based on category, exercises, and duration.
            </small>
            <button type="submit" disabled={loading}>
              Add workout
            </button>
          </form>
        </div>
        <div>
          <h3>Logged workouts</h3>
          <table>
            <thead>
              <tr>
                <th>Workout</th>
                <th>Calories</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {workouts.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.description}</strong>
                    <div className="muted">
                      {item.category} · {item.duration_minutes ? `${item.duration_minutes} min` : "—"}
                    </div>
                  </td>
                  <td>{item.calories_burned.toFixed(0)}</td>
                  <td>
                    <button type="button" onClick={() => deleteWorkout(item.id)} disabled={loading}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!workouts.length && (
                <tr>
                  <td colSpan={3}>Workouts will show here once logged.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card form-grid">
        <div>
          <h3>Weight trajectory (CICO)</h3>
          <p className="muted">Based on recent calories in/out (7700 kcal ≈ 1 kg).</p>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Weight</th>
                <th>Δ kg</th>
              </tr>
            </thead>
            <tbody>
              {forecast.length ? (
                forecast.map((point) => (
                  <tr key={point.entry_date}>
                    <td>{point.entry_date}</td>
                    <td>{point.predicted_weight.toFixed(2)} kg</td>
                    <td>{point.daily_delta_kg.toFixed(3)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3}>Log food + workouts to unlock projections.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div>
          <h3>Fasting tracker</h3>
          <div className="fasting-layout">
            <div
              className="fasting-circle"
              style={{ background: `conic-gradient(#2563eb ${fastingProgress * 360}deg, #e5e7eb 0deg)` }}
            >
              <div className="fasting-circle__inner">
                <strong>{fastingElapsed.toFixed(1)}m</strong>
                <span>Elapsed</span>
              </div>
            </div>
            <div className="fasting-info">
              <p>
                Target: {(fastingTargetMinutes / 60).toFixed(1)}h · Remaining: {fastingRemaining.toFixed(1)}m
              </p>
              {fastingExceeded > 0 ? (
                <p className="muted">Exceeded window by {fastingExceeded.toFixed(1)} minutes</p>
              ) : (
                <p className="muted">Keep going to hit 16 hours!</p>
              )}
              <label className="muted">
                Started at (optional)
                <input
                  type="datetime-local"
                  value={manualStart}
                  onChange={(event) => setManualStart(event.target.value)}
                />
              </label>
              <div className="fasting-actions">
                {fasting?.is_active ? (
                  <button type="button" onClick={handleStopFast} disabled={loading}>
                    Stop fast
                  </button>
                ) : (
                  <button type="button" onClick={handleStartFast} disabled={loading}>
                    Start fast
                  </button>
                )}
                <button type="button" onClick={refreshFasting}>
                  Refresh
                </button>
              </div>
            </div>
          </div>
          <h4>Recent fasts</h4>
          <ul className="list">
            {fastingHistory.length ? (
              fastingHistory.map((entry) => (
                <li key={entry.id}>
                  <div>
                    <strong>{(entry.duration_minutes / 60).toFixed(1)} h</strong>
                    <span className="muted">
                      {new Date(entry.start_time).toLocaleString()} → {new Date(entry.end_time).toLocaleString()}
                    </span>
                  </div>
                </li>
              ))
            ) : (
              <li className="muted">No completed fasts yet.</li>
            )}
          </ul>
          <h4>Last 30 days</h4>
          <div className="calendar-grid">
            {fastingCalendar.map((day) => (
              <div
                key={day.entry_date}
                className={`calendar-day ${day.fasted ? "calendar-day--fasted" : ""}`}
                title={`${day.entry_date} · ${(day.duration_minutes / 60).toFixed(1)} h`}
              >
                {new Date(day.entry_date).getDate()}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export default App;
