# Maintenance Tracker

[![CI](https://github.com/chusonn/maintenance_tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/chusonn/maintenance_tracker/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue)
![Flask](https://img.shields.io/badge/flask-3.1-black)

A Flask web app for managing UK rental-property maintenance: flats and tenancies, contractors, and maintenance jobs with scheduling, follow-up tracking, cost comparison, Excel import/export, an analytics dashboard, and a soft-delete recycle bin. Single-user, runs locally, SQLite storage — built for a property manager handling a real portfolio of 200+ flats.

![Dashboard](docs/screenshots/dashboard.png)

## Features

- **Job lifecycle** — `Pending → Scheduled → In Progress → Completed` (or `Cancelled`), with four priority levels, contractor assignment, estimated-vs-actual cost tracking, and per-job follow-up counts so nothing slips.
- **Analytics** — monthly job volume, estimated-vs-actual spend on completed jobs, status/priority breakdowns, and top contractors by completed work. Chart.js reading the app's design tokens; every chart has a data-table twin for accessibility.
- **Flats & tenancies** — properties keyed by a unique payment reference, with tenant details, rent, due dates, and open-job counts at a glance.
- **Excel round-trip** — bulk-import flats from spreadsheets (upserts by payment reference, tolerant of messy real-world data) and export the jobs register to `.xlsx`.
- **Soft-delete recycle bin** — deleting any flat, contractor, or job moves it to a bin; restore or permanently purge from there. Deleting a flat cascades to its jobs and restores them together.
- **Safety rails** — CSRF protection on every form, confirmation on every destructive action, `flask backup` / `restore` CLI for the database, idempotent startup schema migrations.
- **UK conventions** — currency in GBP, dates displayed as `dd/mm/yyyy` throughout.

| Jobs | Analytics |
| --- | --- |
| ![Jobs list with filters](docs/screenshots/jobs.png) | ![Analytics page](docs/screenshots/analytics.png) |

<details>
<summary>More screenshots</summary>

![Flats list](docs/screenshots/flats.png)

</details>

## Quickstart

Requires Python 3.12+.

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt   # Windows: venv\Scripts\pip
venv/bin/flask --app run.py seed                                  # optional: deterministic demo data
venv/bin/python run.py                                            # → http://127.0.0.1:5000
```

The SQLite database is created automatically in `instance/` on first run. Configuration is via environment variables (or a `.env` file): `SECRET_KEY`, `DATABASE_URL`, `FLASK_DEBUG`, `HOST`, `PORT`.

## Development

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest        # test suite (in-memory SQLite, fast)
venv/bin/ruff check .            # lint
```

CI runs lint + tests on Python 3.12 and 3.14 on every push and pull request.

## Architecture

App factory + blueprints, SQLAlchemy 2.0 style (`Mapped` models, `select()` queries):

```
run.py                     # entry point
app/
├── __init__.py            # create_app(): blueprints, template filters, error handlers
├── models.py              # Flat, Contractor, MaintenanceJob + SoftDeleteMixin
├── config.py              # Config / TestConfig
├── db_migrate.py          # idempotent startup schema sync (additive only)
├── cli.py                 # flask backup / list-backups / restore
├── seed.py                # flask seed — deterministic UK demo data
├── blueprints/            # dashboard, analytics, jobs, flats, contractors, recycle
├── services/
│   ├── excel_io.py        # Excel import/export (pandas lazy-imported)
│   └── analytics.py       # pure aggregation functions for the analytics page
├── templates/             # Jinja2; _components.html + _icons.html macro library
└── static/
    ├── css/app.css        # design tokens (--mt-*) + component classes
    └── js/                # app.js, analytics.js (Chart.js, token-driven colors)
tests/                     # pytest suite: models, routes, Excel IO, analytics, seed
```

Design decisions worth noting:

- **Soft delete everywhere.** All three models share a `SoftDeleteMixin`; list/count/export queries go through `Model.active_select()` so binned rows never leak into views, exports, or charts.
- **Business identity over surrogate display.** Several flats share a flat number across buildings, so the unique `payment_reference` is the identifier users see and Excel import upserts by.
- **Token-based design system.** All styling flows from CSS custom properties in `app.css`; the charts read the same tokens at runtime, so status colors in a chart always match the status badges.
- **Boring, reliable migrations.** Startup schema sync only ever adds columns and backfills — no destructive migrations against a live personal database.

## License

Copyright © 2026 Ralph Chu. All rights reserved.

This code is published for portfolio viewing only — no permission is granted to use, copy, or redistribute it. See [LICENSE](LICENSE) for details.
