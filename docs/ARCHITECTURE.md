# Weight Loss Companion - Architecture

## Overview

The desktop app is a PyQt6 experience that guides users through a daily weight-loss ritual. It combines habit tracking, calorie accounting, motivational content, an animated mascot, and reminder services. Functionality is split across three logical layers:

1. **Presentation (PyQt6 UI)** - Tabbed experience with dashboard, daily check-in, and analytics screens. Uses Matplotlib for plots, QMovie for GIF mascots, and bright palette/streak widgets to keep things lively.
2. **Domain & Persistence** - Dataclasses model weights, foods, workouts, and reminders. SQLite (via `sqlite3`) stores entries; a tiny repository layer exposes high-level methods the UI calls.
3. **Services** - Motivation, calorie lookup, and notification/email helpers. They hide integrations (OpenAI GPT, Nutrition API, SMTP) and provide graceful fallbacks when no keys are configured.

```
+------------+    +--------------------+    +----------------------+
|  UI Tabs   |<-->|   Data Controller  |<-->|   SQLite & Services  |
| Dashboards |    |   (signals/slots)  |    |  (calories/email)    |
+------------+    +--------------------+    +----------------------+
```

## Data model

| Table | Purpose |
| --- | --- |
| `weights` | One row per day capturing weight, calories target, and mood. |
| `food_entries` | Individual food items with meal type + calories + carbs/protein/fat. |
| `workouts` | Calories burnt per workout session. |
| `streaks` | Stores the current streak counter + last day checked in. |
| `app_meta` | Generic key/value (e.g., first_weight, last_email_date, mascot_path). |
| `fasting_sessions` | Start/end timestamps for each fasting window for the dashboard timer. |

All timestamps are stored in ISO format (UTC). Queries are wrapped in helper methods so widgets never touch SQL.

## Key services

- **`MotivationService`** - Returns a lively greeting. If `OPENAI_API_KEY` is provided, it hits GPT (`gpt-4o-mini`) for a custom pep talk; otherwise it cycles through curated quotes.
- **`CalorieAdvisor`** - Given a free-form food description, it first checks cached/local nutrition values. If an OpenAI key exists, it asks GPT to estimate calories **and** macros (JSON). Otherwise it optionally talks to Nutritionix (needs `NUTRITION_API_KEY`). Results are persisted and shown in the food table.
- **`EmailService`** - Sends the daily motivation email via SMTP using credentials stored in `.env`/environment variables.
- **`ReminderService`** - `QTimer` driven job that fires once a day, nudges the user inside the UI, and triggers the motivational email if that day's check-in is missing.
- **`AssetManager`** - Downloads mascot GIFs and also generates a custom animated GIF offline so the dashboard always has motion.
- **`AppRepository` fasting helpers** - Start/stop a fasting session, query the active one, and surface recent sessions to the dashboard widget.

## UI flow

1. **Dashboard tab**
   - Animated mascot, stat cards (start/today/net/remaining/streak), macro progress bars, meal summary list, and a fasting tracker card with live timer + history, plus motivational text/CTA buttons.
2. **Daily check-in tab**
   - Form fields for weight, mood, and date selection.
   - Meal logging grid with GPT-powered calories+macros, meal-type picker, macro fields, and delete controls.
   - Workout logging with calories burned + delete.
   - Summary banner displays deficit guidance plus macro totals.
3. **Progress tab**
   - Dark-themed Matplotlib charts: weight line with fill + calories vs burn lines with area shading and target overlay.
4. **Settings tab**
   - Configure email + API keys, target calories, reminder time, macro targets (derived from calories), and custom GIF URLs.

Signals/slots connect widgets to the controller so storage/services update the UI reactively.
