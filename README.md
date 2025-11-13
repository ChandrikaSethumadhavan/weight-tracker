# GlowUp Weight Journey (PyQt6)

A lively desktop companion for tracking weight loss habits. Animated mascots, GPT-powered calorie lookups, streak mechanics, and charts keep daily check-ins fun.

## Highlights

- Animated mascot panel powered by local plus downloaded GIFs so the UI feels alive even offline.
- Dashboard is now a wellness cockpit: motivational copy, macro progress rings, meal cards, and a live fasting tracker with start/stop buttons.
- Check-in tab collects weight, mood, foods, and workouts; GPT (or fallbacks) auto-estimates calories **and** carbs/protein/fat, and logs are tagged as breakfast/lunch/dinner/snack (with quick delete controls).
- Progress tab renders modern dark-themes with smooth trend lines for both weight and calories.
- Reminder service plus optional SMTP email pings you daily until you log your stats.
- Settings tab manages calorie targets, reminder time, SMTP credentials, and API keys.
- Data lives in SQLite (`data/weight_loss.sqlite3`) for portability.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m app.main
```

First launch generates `assets/gifs/` (including a procedurally generated mascot) and bootstraps the database. Set `QT_DEBUG_PLUGINS=1` before running if you need Qt logs.

## Configuration

Set environment variables (or create a `.env` file) before starting:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Enables GPT motivational copy plus calorie & macro estimates. |
| `NUTRITION_API_KEY` | Optional fallback (API Ninjas). |
| `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_USERNAME`, `EMAIL_SMTP_PASSWORD`, `EMAIL_SENDER`, `EMAIL_RECIPIENT`, `EMAIL_SMTP_USE_TLS` | SMTP settings for the daily pep email. |
| `TARGET_CALORIES` | Default calorie intake target (overridable in Settings). |
| `DAILY_DEFICIT_GOAL` | Default deficit goal in kcal. |
| `REMINDER_TIME` | HH:MM for in-app/email reminder. |
| `MASCOT_GIFS` | Comma separated list of extra GIF URLs to download on startup. |

The Settings tab writes overrides into `app_meta`, so you can adjust most of the above from inside the app too.

## Data model and assets

- Tables: `weights`, `food_entries`, `workouts`, `streaks`, `app_meta`. Details live in `app/database.py` and `docs/ARCHITECTURE.md`.
- `_MiniGifFactory` (see `app/services/asset_manager.py`) procedurally generates `assets/gifs/lively_orb.gif` so there is always an animated mascot offline.
- On first run with network access the app downloads two CC BY-SA GIFs from Wikimedia Commons for extra variety:
  - ["Animated Pushups"](https://upload.wikimedia.org/wikipedia/commons/5/5f/Animated_Pushups.gif) by Wikimedia Commons contributors.
  - ["Aerobic Dance"](https://upload.wikimedia.org/wikipedia/commons/1/19/AerobicDance.gif) by Wikimedia Commons contributors.
- Drop your own GIFs into `assets/gifs/` or point `MASCOT_GIFS` to other URLs.

## Feature notes

- Daily motivation email: press the "Send pep email" button on the dashboard or let the reminder service auto-send once per day (requires SMTP config).
- Auto nutrition lookup: GPT (`gpt-4o-mini`) now returns calories + macros in one shot. If GPT is unavailable, the Nutrition API or heuristics approximate macros for you.
- Meal segmentation: every log is tied to Breakfast/Lunch/Dinner/Snack. Use the filter above the meal table and watch the dashboard meal widget summarize each period.
- Fasting tracker: start/stop a fasting session from the dashboard. A live ticker runs while fasting and a history list shows recent durations.
- Negative nudges: if you eat more than 1,000 kcal without logging workouts, the summary calls it out.
- Streak logic: recording weight, foods, or workouts for the current day bumps the streak. Reminders fire when the day is incomplete past the configured time.

## Repository layout

```
app/
  config.py            # env loader and defaults
  database.py          # SQLite helpers
  models.py            # dataclasses
  services/            # motivation, calorie advisor, assets, email, reminders
  ui/main_window.py    # PyQt6 tabs and widgets
  main.py              # entry point
assets/
  gifs/                # generated and downloaded mascots
data/
  weight_loss.sqlite3  # created on first run
docs/ARCHITECTURE.md   # extended design notes
```

## Next steps / ideas

1. Hook up a Windows toast or macOS notification when reminders fire.
2. Export/import the SQLite log to CSV or Google Sheets.
3. Add badges or achievements for sustained streaks or best deficits.

Enjoy the journey and keep that streak flaming hot!
