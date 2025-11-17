# GlowUp Weight Journey (FastAPI + React)

The project has evolved from a PyQt-only desktop companion into a full-stack experience. FastAPI now powers the backend (reusing the existing SQLite + services), and a responsive React dashboard gives you access from any browser—desktop, tablet, or phone.

## Stack highlights

- **Backend** – `app/main.py` exposes REST endpoints for snapshots, weights, foods, workouts, forecasts, and fasting. Business logic (config, SQLite repository, services) stays in the `app/` package.
- **Frontend** – `/frontend` is a Vite + React SPA styled for light mode, featuring workout cards, GPT-assisted meal/workout estimation, a fasting tracker, and a JustCICO-inspired weight projection card.
- **Data** – SQLite (`data/weight_loss.sqlite3`) keeps everything portable. Docker + docker-compose are available for containerized runs.

## Project layout

```
app/
  config.py            # env loader and defaults (CORS-friendly)
  database.py          # SQLite helpers + schema migration utilities
  models.py            # dataclasses for repo/API
  services/            # motivation, calorie advisor, assets, email, reminders
  main.py              # FastAPI app with routes
frontend/
  src/                 # React SPA (Vite/TypeScript)
  package.json         # npm scripts (dev/build/preview)
.github/workflows/     # frontend deploy workflow (GitHub Pages)
assets/, data/, docs/  # unchanged resources
```

## Backend quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m app.main            # uvicorn server on :8000
```

Key environment variables (use `.env.example` as a template):

| Variable | Purpose |
| --- | --- |
| `API_ALLOWED_ORIGINS` | CSV of domains allowed to call the API (e.g., `http://localhost:5173,https://myapp.com`). |
| `OPENAI_API_KEY` | Enables GPT-powered meal + workout calorie estimates. |
| `NUTRITION_API_KEY` | Optional fallback nutrition API. |
| `EMAIL_SMTP_*` | SMTP settings for pep emails. |
| `TARGET_CALORIES`, `DAILY_DEFICIT_GOAL`, `REMINDER_*` | Default goals/reminders (overridable in-app). |

Useful endpoints (see `/docs`):

- `GET /api/snapshot?entry_date=YYYY-MM-DD`
- `GET/POST/DELETE /api/weights`
- `GET/POST/DELETE /api/foods`
- `GET/POST/DELETE /api/workouts`
- `GET /api/cico/forecast`
- `GET/POST /api/fasting`, `POST /api/fasting/stop`
- `GET/PUT /api/settings`

## Frontend quick start

```bash
cd frontend
npm install
npm run dev           # http://localhost:5173
```

Create a `.env` file in `frontend/` (see `.env.example`) and set `VITE_API_URL` to your FastAPI server. `npm run build` emits static assets into `frontend/dist/`, ready for GitHub Pages, Netlify, Vercel, etc.

While logging meals, leave calories/macros blank (optionally supply a brand/restaurant) to let GPT fill them in. Workout cards (legs/abs/arms/cardio/custom) can also auto-estimate burn from category + exercises + duration. The fasting tracker supports manual start timestamps, auto-refreshes every 30 seconds, and displays a 30-day calendar of completed fasts. The JustCICO card extrapolates weight changes using recent intake/output (7700 kcal ≈ 1 kg).

## Deployment recipe

1. **Backend container** – Use the provided `Dockerfile`.
   ```bash
   docker build -t glowup-api .
   docker run --rm -p 8000:8000 -v $(pwd)/data:/app/data --env-file .env glowup-api
   ```
   Deploy the image to Render/Railway/Fly (or connect your GitHub repo so they build the Dockerfile automatically). Provide environment variables + secrets on the host.

2. **Frontend hosting** – `npm run build` in `frontend/` and publish `frontend/dist` to GitHub Pages (workflow provided) or any static host. Set `VITE_API_URL` to your deployed API URL before building. Configure CORS via `API_ALLOWED_ORIGINS`.

3. **Custom domain (optional)** – Point DNS/HTTPS at your frontend + backend hosts and update `API_ALLOWED_ORIGINS` accordingly.

## Feature overview

- GPT-assisted meal and workout logging (brand-aware macros, category-based burn).
- Smart dashboard snapshot with streak, macros, and motivational cards.
- Daily check-in forms for weight, meals, workouts, and summaries.
- Progress charts for weight/calories plus JustCICO projections.
- Fasting tracker with manual start times, auto-updating timer, and a 30-day calendar heatmap.
- Reminder + email services with configurable schedules.

Enjoy GlowUp from any device and keep that streak blazing!
