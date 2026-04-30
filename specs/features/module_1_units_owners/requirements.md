# requirements.md — Module 1: Units & Owners Registry

## Overview

A registry of all 5 units at Waybern Mews and every person associated with them — owners, tenants, residents, and trustees. This is the foundational data module that all future modules (billing, communications, compliance) will reference.

---

## Problem

Barry currently has no single place to look up who owns each unit, who lives there, and how to contact them. This information lives in his head, his phone contacts, and scattered files. When he needs to contact an owner or check who is a trustee, he has to go hunting.

---

## Goals

- All 5 units and their associated people captured in one place
- Any record can be viewed and edited through the UI — no SQL required
- Contact information for every person at the complex is findable in under 30 seconds
- Data is ready to be used by future modules (levy billing, communications, compliance)

---

## Non-Goals

- No lease tracking (start/end dates, rental amounts) — Barry doesn't manage tenant leases
- No ownership history — we start from today and track current state only
- No document attachments to units or contacts
- No ownership transfer workflow — changes are made by editing records directly

---

## Constraints

- Must work offline
- No new Python dependencies required
- All data is entered and managed through the UI

---

## Key Decisions

**1. Single unified contacts table, not separate owner/tenant/resident tables.**

Every person associated with a unit is one row in the `contacts` table with boolean role flags (`is_owner`, `is_tenant`, `is_resident`, `is_trustee`). A person can hold multiple roles simultaneously (e.g. an owner who is also a trustee).

This design was chosen because:
- Future communication features need to query by role across the whole complex (e.g. "send to all trustees")
- It avoids duplicating contact data across multiple tables
- It is simpler to build, query, and maintain

**2. Owners are also marked as residents if they live in their unit.**

An owner-occupier has `is_owner=true` and `is_resident=true`. An absentee owner has `is_owner=true` and `is_resident=false`. This ensures "all residents" queries return the right people.

**3. Participation quota is equal: 20% per unit.**

All 5 units have equal participation quota. This is stored per unit for correctness (the utility billing module will use it), even though the value is currently the same for all.

**4. All phone numbers and emails are optional.**

Some contacts have incomplete information (no email, no phone). The system stores what is known and leaves the rest blank — no fabricated placeholders.

**5. Edit UI uses dedicated form pages, not inline editing.**

Editing a unit or contact navigates to a separate form page. This is simpler to build and makes the edit action explicit and deliberate.

---

## Data Model

### `units` table
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| unit_number | String | e.g. "1", "2" — unique |
| description | String (nullable) | Optional free-text description |
| participation_quota | Float | Stored as decimal, e.g. 0.20 for 20% |

### `contacts` table
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| unit_id | Integer (FK) | References units.id |
| name | String | Required |
| phone | String (nullable) | |
| email | String (nullable) | |
| is_owner | Boolean | Default false |
| is_tenant | Boolean | Default false |
| is_resident | Boolean | Default false |
| is_trustee | Boolean | Default false |

---

## User Flow

### Viewing units
1. Barry clicks "Units & Owners" in the sidebar
2. He sees a list of all 5 units, each showing: unit number, owner name(s), occupancy status (owner-occupied / tenant-occupied)
3. He clicks a unit to open the detail page

### Viewing a unit
4. The unit detail page shows: unit number, description, participation quota
5. Below that, a table of all contacts for the unit with their name, phone, email, and role badges
6. Edit buttons are present for the unit details and each contact
7. An "Add contact" button allows adding a new person to the unit

### Editing a unit
8. Barry clicks "Edit" on the unit details
9. A form page loads with the current values pre-filled
10. He makes changes and clicks Save — returns to the unit detail page

### Editing a contact
11. Barry clicks "Edit" next to a contact
12. A form page loads with current values pre-filled (name, phone, email, role checkboxes)
13. He makes changes and clicks Save — returns to the unit detail page

### Adding a contact
14. Barry clicks "Add contact" on a unit detail page
15. A blank form loads with the unit pre-selected
16. He fills in the details and saves

### Deleting a contact
17. Barry clicks "Delete" next to a contact
18. A confirmation prompt appears before deletion

---

## Edge Cases

- **Missing phone/email:** Form fields are optional — saving with blanks is valid
- **Absentee owner:** An owner who doesn't live in their unit has `is_owner=true, is_resident=false` — handled correctly via role flags
- **Multiple owners:** A unit can have multiple contacts with `is_owner=true` (joint ownership)
- **Contact with no roles checked:** The system allows this — Barry may want to record a person without assigning roles yet

---

## Risks

- **Low.** This is straightforward CRUD with no business logic.
- The main risk is getting the data model wrong before other modules depend on it. The unified contacts design must be solid before Module 2 begins.
