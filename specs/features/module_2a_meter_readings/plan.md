# plan.md — Module 2a: Meter Readings

## New Files to Create

```
app/
├── models/
│   └── meter_readings.py         # MeterReading SQLAlchemy model
├── routers/
│   └── meter_readings.py         # Routes for list, add, edit
├── services/
│   └── meter_readings.py         # DB queries and write operations
└── templates/
    └── meter_readings/
        ├── list.html              # All months, reverse chronological
        └── form.html              # Shared add/edit form
```

## Files to Modify

```
app/models/__init__.py             # Import MeterReading so init_db() sees it
main.py                            # Register meter_readings router
app/templates/base.html            # Add "Meter Readings" link to sidebar
```

---

## Plan

### Task Group 1 — Data Layer

1. Write `app/models/meter_readings.py`:

   **MeterReading**
   - id (Integer, primary key)
   - year (Integer, not null)
   - month (Integer, not null) — 1 to 12
   - reading_date (Date, not null)
   - elec_unit_1 through elec_unit_5 (Float, nullable) — kWh
   - elec_public_lighting (Float, nullable) — kWh
   - elec_total (Float, nullable) — kWh
   - water_unit_1 through water_unit_5 (Float, nullable) — kL
   - water_total (Float, nullable) — kL
   - UniqueConstraint on (year, month)

2. Update `app/models/__init__.py` to import MeterReading so `init_db()` creates the table on startup.

---

### Task Group 2 — Service Layer

3. Write `app/services/meter_readings.py`:
   - `get_all_readings(db)` — returns all rows ordered by year desc, month desc
   - `get_reading(db, reading_id)` — returns one row or raises 404
   - `get_reading_for_month(db, year, month)` — returns row or None (used for duplicate check)
   - `create_reading(db, data)` — inserts a new row; raises 400 if month already exists
   - `update_reading(db, reading_id, data)` — updates all fields on an existing row

---

### Task Group 3 — Routes

4. Write `app/routers/meter_readings.py`:

   | Method | Path | Action |
   |--------|------|--------|
   | GET | `/meter-readings` | Render readings list |
   | GET | `/meter-readings/add` | Render blank add form |
   | POST | `/meter-readings/add` | Save new reading, redirect to list |
   | GET | `/meter-readings/{id}/edit` | Render pre-filled edit form |
   | POST | `/meter-readings/{id}/edit` | Save changes, redirect to list |

---

### Task Group 4 — Templates

5. Write `app/templates/meter_readings/list.html` (extends base.html):
   - Page title: "Meter Readings"
   - "Add reading" button top-right
   - Table with columns: Month, Reading Date, Edit
   - Months displayed as "April 2026" (not raw integers)
   - Rows ordered newest first
   - Empty state message if no readings yet

6. Write `app/templates/meter_readings/form.html` (extends base.html):
   - Used for both add and edit (action URL passed from route)
   - Month dropdown (January–December) and year input
   - Reading date input (type="date")
   - **Electricity section** with 7 labelled fields:
     - Unit 1, Unit 2, Unit 3, Unit 4, Unit 5, Public Lighting, Total
     - Unit: kWh shown next to each field
   - **Water section** with 6 labelled fields:
     - Unit 1, Unit 2, Unit 3, Unit 4, Unit 5, Total
     - Unit: kL shown next to each field
   - Save and Cancel buttons
   - Error message area for duplicate month validation errors

---

### Task Group 5 — Wiring Up

7. Update `app/models/__init__.py` — add MeterReading import
8. Update `main.py` — import and register the meter_readings router
9. Update `app/templates/base.html` — add "Meter Readings" nav link in sidebar

---

### Task Group 6 — Verification

10. Start the server and run through the manual test script in `validation.md`
