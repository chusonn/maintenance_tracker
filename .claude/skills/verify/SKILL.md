---
name: verify
description: Verify or smoke-test that a change to the Maintenance Tracker actually works end-to-end. Use before committing nontrivial changes, or when asked to check/verify/confirm the app works.
---

# Verify a change end-to-end

1. **Tests first** (once the pytest suite exists): `venv\Scripts\python.exe -m pytest -q` must be green before manual verification.

2. **Boot check**: start the server per the `run-app` skill (background), then confirm `http://127.0.0.1:5000/healthz` returns 200 and `/dashboard` redirects to `/login` when signed out. Sign in (scratch DB: start it with `INITIAL_USER_*` env vars) and confirm `/dashboard` returns 200. In browser automation, click form buttons by text: the topbar sign-out is also a submit button.

3. **Core flow click-through** — exercise whatever the change touched, plus this minimum set (use the Flask test client for speed, or the browser when visuals matter):
   - Dashboard renders with correct stat counts.
   - Jobs list loads; filter by status and priority; search by a flat's payment reference.
   - Add a job (pick any flat), then edit it, schedule it with a contractor, mark it complete with an actual cost.
   - Soft-delete the test job → confirm it appears in the recycle bin → restore it → permanently delete it.
   - Flats and Contractors lists render.
   - Excel export downloads (check `Content-Type` is xlsx and status 200).
   - Sign out → protected pages redirect to `/login`; Settings → Download backup returns a SQLite file.

4. **UI changes**: verify in the real browser, not just the test client — check both a seeded database AND empty states, and one pass at narrow (~400px) width. Watch the browser console for JS errors.

5. **Clean up any test records you created** (permanent-delete via recycle bin) so the user's data stays clean — unless working on a scratch/seeded DB.

Never verify against the user's live `instance/maintenance_tracker.db` with destructive flows if a scratch DB will do: point `DATABASE_URL` at a scratch file and seed it instead.
