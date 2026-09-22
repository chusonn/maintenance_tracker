---
name: run-app
description: Run, start, or launch the Maintenance Tracker dev server locally (Windows). Use whenever the user asks to run/start/serve the app, open it in a browser, or screenshot it.
---

# Run the app

From the repo root (`C:\Users\ralph\CascadeProjects\maintenance_tracker`):

```powershell
venv\Scripts\python.exe run.py
```

- App serves at **http://127.0.0.1:5000** (`/` redirects to `/dashboard`).
- Always use the project venv, never the system Python.
- **Every page needs sign-in.** If there's no account yet: `$env:FLASK_APP="run.py"; venv\Scripts\flask.exe create-user EMAIL` (prompts for name + password), or set `INITIAL_USER_EMAIL/NAME/PASSWORD` in `.env` (only used while no accounts exist). For screenshots/automation on a scratch DB, set `INITIAL_USER_*` as env vars for that run.
- Startup runs idempotent schema migrations automatically; with the debug reloader they appear to run twice — that's normal.
- The live database is `instance/maintenance_tracker.db`. If the user wants a clean slate for screenshots/demos, do NOT delete this file — copy it aside into `backups/` first (server stopped).
- To stop: kill the process (Ctrl+C in its terminal, or `Stop-Process` on the python PID).
- Run it in the background (`run_in_background`) when you need the shell afterwards; confirm readiness by requesting `http://127.0.0.1:5000/dashboard` and checking for HTTP 200.
- If port 5000 is busy, find the stale server with `netstat -ano | findstr :5000` and stop that PID rather than switching ports.
