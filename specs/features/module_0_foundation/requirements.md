# requirements.md — Module 0: Foundation

## Overview

Module 0 establishes the complete structural skeleton of Waybern Mews OS. It contains no business logic. Its sole purpose is to create a working, launchable application shell that every future module can plug into cleanly.

---

## Problem

Before any feature can be built, we need a stable, consistent base: a running FastAPI server, a SQLite database, a templating system, and a UI layout. Without this, each new module would require setting up infrastructure as well as features — which creates inconsistency and wasted effort.

---

## Goals

- A double-click launcher that starts the server and opens the app in the browser
- A working FastAPI application with a clean folder structure
- A SQLite database initialised and ready to accept models
- A base HTML layout (sidebar nav, header, content area) that all pages will extend
- A dashboard home page with a placeholder card for Module 1 (Units & Owners Registry)
- Tailwind CSS, HTMX, and Heroicons loaded and available to all templates

---

## Non-Goals

- No business logic of any kind
- No database models beyond the base SQLAlchemy setup
- No navigation links in the sidebar (added as modules are built)
- No Google Drive backup (deferred to a future module)
- No authentication or user management (single-user tool)

---

## Constraints

- Must run entirely offline — no internet required to operate
- No npm, no build steps — Tailwind and HTMX loaded from CDN
- Python only on the backend
- SQLite only — no other database
- Root directory is: `/Users/barrymorisse/Documents/Waybern Mews BC/Operating System`

---

## Key Decisions

**1. Folder structure is domain-separated from the start.**
Routers, services, models, and templates each live in their own directory. This means a coding agent can work on a single module without needing to read the whole codebase.

**2. The database file lives at `/data/waybern.db`.**
The `/data` folder is gitignored. This keeps the database out of version control while keeping it in a predictable location.

**3. Dashboard cards are hardcoded, not data-driven.**
The 9 planned modules are known. Dynamically generating placeholder cards from config would be premature abstraction. Cards are written directly into the dashboard template.

**4. The base layout uses a left sidebar + main content area.**
This is the standard layout for admin/management tools. All future pages extend `base.html` and slot their content into the main area.

**5. `launch.sh` uses `uvicorn` with `--reload` during development.**
This means changes to Python files are picked up automatically without restarting the server. Appropriate for a single-developer tool.

---

## Data Model Impact

- No new business models
- SQLAlchemy `Base` and `SessionLocal` are established in `app/database.py`
- All future models will import from this file

---

## User Flow

1. Barry double-clicks the launcher (shell script or macOS shortcut)
2. Terminal opens briefly, server starts on `localhost:8000`
3. Browser opens automatically to the dashboard
4. Dashboard shows the app name, and a grid of module cards
5. Each card shows the module name and a short description
6. Sidebar is present but empty (links added as modules are built)

---

## Edge Cases

- **Port 8000 already in use:** `uvicorn` will fail to start. The launcher will need to surface this clearly rather than silently failing. For now, a clear error message in the terminal is sufficient.
- **First run — database doesn't exist yet:** SQLAlchemy's `Base.metadata.create_all()` handles this automatically on startup.
- **CDN unavailable (offline use):** Tailwind and HTMX are loaded from CDN. If offline, styling and interactivity will be absent. Acceptable for now — the data and functionality still work. Vendoring assets locally is a future improvement if needed.

---

## Risks

- **Low.** This module contains no business logic and no external dependencies beyond standard Python libraries and CDN assets.
- The main risk is getting the folder structure wrong at this stage, since everything else builds on it. The structure must be clean and consistent from day one.
