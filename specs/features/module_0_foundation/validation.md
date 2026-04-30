# validation.md — Module 0: Foundation

## Validation Criteria

### Functional Tests
- [ ] `launch.sh` starts the server without errors
- [ ] Browser opens automatically to `http://localhost:8000`
- [ ] Dashboard page loads and displays correctly
- [ ] `data/waybern.db` is created automatically on first run (did not exist before)
- [ ] No Python import errors on startup
- [ ] FastAPI auto-docs accessible at `http://localhost:8000/docs`

### UI Validation
- [ ] Left sidebar is present with app name at top
- [ ] Main content area is distinct from the sidebar
- [ ] The Module 1 card is visible on the dashboard
- [ ] The card shows the module name and description
- [ ] The card shows a "Coming soon" badge
- [ ] Page title in the header reads "Dashboard"
- [ ] Tailwind CSS is loading (styles are applied — not a plain unstyled HTML page)
- [ ] HTMX is loading (check browser console — no 404 for htmx script)

### Edge Case Tests
- [ ] Stopping and restarting the server does not cause errors or duplicate data
- [ ] Visiting any undefined route (e.g. `/units`) returns a clean 404, not a server crash
- [ ] `data/waybern.db` is NOT committed to git (confirm `.gitignore` is working)

### Data Integrity
- [ ] Database file is created in `data/waybern.db` (correct location)
- [ ] SQLAlchemy `Base` and `SessionLocal` are importable from `app.database` without errors

### Structure Check
- [ ] All planned directories exist: `app/`, `app/models/`, `app/routers/`, `app/services/`, `app/templates/`, `data/`, `static/`
- [ ] `requirements.txt` lists all installed packages
- [ ] `venv/` is present and `.gitignore` excludes it

---

## Manual Test Script

Follow these steps exactly to verify Module 0 is complete and working.

**Step 1 — Fresh install check**

Open Terminal and run:
```bash
cd "/Users/barrymorisse/Documents/Waybern Mews BC/Operating System"
ls
```
Confirm you see: `app/`, `data/`, `static/`, `main.py`, `requirements.txt`, `launch.sh`, `.gitignore`

---

**Step 2 — Delete the database and test auto-creation**

```bash
rm -f data/waybern.db
ls data/
```
Confirm `waybern.db` is gone.

---

**Step 3 — Launch the app**

Double-click `launch.sh`, or run in terminal:
```bash
bash launch.sh
```
Confirm:
- Terminal shows `Uvicorn running on http://127.0.0.1:8000`
- Browser opens automatically

---

**Step 4 — Check the dashboard**

In the browser:
- Confirm the page loads without a white error screen
- Confirm the Module 1 card is visible
- Confirm the card has a name, description, and "Coming soon" label
- Confirm the sidebar is present on the left

---

**Step 5 — Check database was created**

Back in Terminal:
```bash
ls data/
```
Confirm `waybern.db` now exists.

---

**Step 6 — Check API docs**

Navigate to `http://localhost:8000/docs` in the browser.
Confirm the FastAPI auto-documentation page loads and shows at least the `GET /` route.

---

**Step 7 — Check git status**

```bash
git status
```
Confirm `data/waybern.db` and `venv/` do NOT appear as untracked files.

---

**Step 8 — Stop the server**

In Terminal, press `Ctrl+C` to stop uvicorn.
Confirm it shuts down cleanly.

---

If all steps pass, Module 0 is complete. Proceed to Module 1: Units & Owners Registry.
