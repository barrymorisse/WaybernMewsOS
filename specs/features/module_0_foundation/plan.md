# plan.md — Module 0: Foundation

## Directory Structure to Create

```
Operating System/
├── app/
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy setup: engine, SessionLocal, Base
│   ├── models/
│   │   └── __init__.py       # Future models imported here
│   ├── routers/
│   │   └── __init__.py       # Future routers imported here
│   ├── services/
│   │   └── __init__.py       # Future business logic here
│   └── templates/
│       ├── base.html         # Master layout: sidebar, header, content slot
│       └── dashboard.html    # Home page with module cards
├── data/
│   └── .gitkeep             # Keeps folder in git; waybern.db is gitignored
├── static/                  # Future: local CSS/JS/images if needed
│   └── .gitkeep
├── main.py                  # FastAPI app entry point
├── requirements.txt         # Python dependencies
├── launch.sh                # Launcher script
└── .gitignore
```

---

## Plan

### Task Group 1 — Project Scaffold

1. Create the full directory structure above (all folders and empty `__init__.py` files)
2. Create `requirements.txt` with dependencies:
   - `fastapi`
   - `uvicorn[standard]`
   - `sqlalchemy`
   - `jinja2`
   - `python-multipart`
3. Create `.gitignore` — exclude:
   - `data/waybern.db`
   - `__pycache__/`
   - `*.pyc`
   - `venv/`
   - `.env`
4. Create Python virtual environment at `venv/` and install dependencies

---

### Task Group 2 — Database Setup

5. Write `app/database.py`:
   - Create SQLite engine pointed at `data/waybern.db`
   - Define `SessionLocal` (session factory)
   - Define `Base` (declarative base all models will inherit from)
   - Define `get_db()` dependency for use in FastAPI routes
   - Call `Base.metadata.create_all()` on startup (creates DB file if absent)

---

### Task Group 3 — FastAPI Application

6. Write `main.py`:
   - Instantiate `FastAPI` app with title "Waybern Mews OS"
   - Mount `static/` directory for future static file serving
   - Set up Jinja2 template rendering
   - Register `startup` event that calls `create_all()` to initialise DB
   - Define a single route: `GET /` → renders `dashboard.html`
   - Import router modules (empty for now, structure in place)

---

### Task Group 4 — Base HTML Layout

7. Write `app/templates/base.html`:
   - Full HTML5 document structure
   - `<head>`: Tailwind CSS (CDN), HTMX (CDN), Heroicons (CDN or inline), viewport meta
   - Left sidebar: app name/logo at top, empty `<nav>` section (links added per module), subtle border/background
   - Top header bar: current page title (passed as template variable)
   - Main content area: `{% block content %}{% endblock %}` slot
   - Clean, minimal aesthetic — dark sidebar, white/light-grey content area
   - Footer: app name and version (hardcoded as v0.1)

---

### Task Group 5 — Dashboard Page

8. Write `app/templates/dashboard.html`:
   - Extends `base.html`
   - Page title: "Dashboard"
   - Introductory line: "Waybern Mews OS — your property management system"
   - One module card for Module 1 only:

   | Module | Name | Description |
   |--------|------|-------------|
   | 1 | Units & Owners Registry | A record of all 5 units, their owners, and tenants — the foundation of every other module. |

   - Card: module name (bold), description (small text), "Coming soon" badge (grey pill)
   - Card is static HTML — no interactivity yet

---

### Task Group 6 — Launcher

9. Write `launch.sh`:
   ```bash
   #!/bin/bash
   cd "/Users/barrymorisse/Documents/Waybern Mews BC/Operating System"
   source venv/bin/activate
   uvicorn main:app --reload &
   sleep 1
   open http://localhost:8000
   ```
10. Make `launch.sh` executable (`chmod +x launch.sh`)
11. Add a note in comments at the top of `launch.sh` explaining how to make it a double-clickable macOS shortcut (via Automator or `.command` extension)

---

### Task Group 7 — Verification

12. Run `launch.sh` and confirm:
    - Server starts without errors
    - Browser opens to `http://localhost:8000`
    - Dashboard renders with correct layout and all 9 module cards
    - No console errors in the browser
    - Database file `data/waybern.db` is created on startup
