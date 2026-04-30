# plan.md — Module 1: Units & Owners Registry

## New Files to Create

```
app/
├── models/
│   └── units.py              # Unit and Contact SQLAlchemy models
├── routers/
│   └── units.py              # All routes for this module
├── services/
│   └── units.py              # Database queries and business logic
│   └── seed.py               # Seed script: pre-populates real data on first run
└── templates/
    └── units/
        ├── list.html          # All 5 units
        ├── detail.html        # One unit + its contacts
        ├── edit_unit.html     # Edit unit details form
        ├── edit_contact.html  # Edit contact form
        └── add_contact.html   # Add new contact form
```

## Files to Modify

```
main.py                        # Register units router; call seed on startup
app/models/__init__.py         # Import Unit and Contact so init_db() sees them
app/templates/base.html        # Add "Units & Owners" link to sidebar nav
```

---

## Plan

### Task Group 1 — Data Layer

1. Write `app/models/units.py` with two SQLAlchemy models:

   **Unit**
   - id (Integer, primary key)
   - unit_number (String, unique, not null)
   - description (String, nullable)
   - participation_quota (Float, not null) — stored as decimal e.g. 0.20
   - contacts (relationship → Contact, back_populates="unit")

   **Contact**
   - id (Integer, primary key)
   - unit_id (Integer, ForeignKey → units.id, not null)
   - name (String, not null)
   - phone (String, nullable)
   - email (String, nullable)
   - is_owner (Boolean, default False)
   - is_tenant (Boolean, default False)
   - is_resident (Boolean, default False)
   - is_trustee (Boolean, default False)
   - unit (relationship → Unit, back_populates="contacts")

2. Update `app/models/__init__.py` to import both models so `init_db()` picks them up:
   ```python
   from app.models.units import Unit, Contact  # noqa: F401
   ```

---

### Task Group 2 — Seed Data

3. Write `app/services/seed.py`:
   - `seed_units(db)` function: inserts all 5 units and their contacts using the data from requirements.md
   - Checks `db.query(Unit).count()` before inserting — if units already exist, skip entirely (safe to call on every startup)
   - All 5 units with participation_quota = 0.20
   - All contacts with correct role flags as per requirements.md

---

### Task Group 3 — Backend Service Layer

4. Write `app/services/units.py` with these functions:
   - `get_all_units(db)` — returns all units ordered by unit_number
   - `get_unit(db, unit_id)` — returns one unit or raises 404
   - `update_unit(db, unit_id, data)` — updates unit fields
   - `get_contact(db, contact_id)` — returns one contact or raises 404
   - `create_contact(db, unit_id, data)` — creates a new contact for a unit
   - `update_contact(db, contact_id, data)` — updates contact fields
   - `delete_contact(db, contact_id)` — deletes a contact

---

### Task Group 4 — Routes

5. Write `app/routers/units.py` with these routes:

   | Method | Path | Action |
   |--------|------|--------|
   | GET | `/units` | Render units list page |
   | GET | `/units/{id}` | Render unit detail page |
   | GET | `/units/{id}/edit` | Render edit unit form |
   | POST | `/units/{id}/edit` | Save unit changes, redirect to detail |
   | GET | `/units/{id}/contacts/add` | Render add contact form |
   | POST | `/units/{id}/contacts/add` | Save new contact, redirect to detail |
   | GET | `/units/{id}/contacts/{contact_id}/edit` | Render edit contact form |
   | POST | `/units/{id}/contacts/{contact_id}/edit` | Save contact changes, redirect to detail |
   | POST | `/units/{id}/contacts/{contact_id}/delete` | Delete contact, redirect to detail |

---

### Task Group 5 — Templates

6. Write `app/templates/units/list.html` (extends base.html):
   - Page title: "Units & Owners"
   - A card or row for each unit showing:
     - Unit number (large)
     - Owner name(s)
     - Occupancy status badge: "Owner-occupied" (green) or "Tenant-occupied" (blue)
     - Number of residents
   - Each card/row links to the unit detail page

7. Write `app/templates/units/detail.html` (extends base.html):
   - Page title: "Unit {number}"
   - Unit details section: unit number, description, participation quota — with an "Edit unit" button
   - Contacts table with columns: Name, Phone, Email, Roles (displayed as small badges: Owner / Tenant / Resident / Trustee)
   - Edit and Delete buttons per contact row
   - "Add contact" button at the bottom of the contacts table

8. Write `app/templates/units/edit_unit.html` (extends base.html):
   - Form with: unit number (read-only — unit numbers don't change), description (text input), participation quota (number input)
   - Save and Cancel buttons

9. Write `app/templates/units/edit_contact.html` (extends base.html):
   - Form with: name, phone, email (text inputs), four role checkboxes (Owner, Tenant, Resident, Trustee)
   - Save and Cancel buttons

10. Write `app/templates/units/add_contact.html` (extends base.html):
    - Same form as edit_contact but blank
    - Unit number shown at top for context (not editable)

---

### Task Group 6 — Wiring Up

11. Update `main.py`:
    - Import and register the units router: `app.include_router(units_router)`
    - Import and call `seed_units(db)` during the startup lifespan event

12. Update `app/templates/base.html`:
    - Add "Units & Owners" nav link in the sidebar pointing to `/units`

---

### Task Group 7 — Verification

13. Start the server and run through the manual test script in `validation.md`
