# requirements.md — Module 2a: Meter Readings

## Overview

A simple monthly log of all utility meter readings at Waybern Mews. Barry manually enters the cumulative meter readings for all 13 meters (7 electricity, 6 water) at the end of each month. The system stores this history so that future modules can calculate consumption and allocate costs per unit.

---

## Problem

Barry photographs meter readings each month as evidence but has nowhere to store the actual numbers in a structured way. Without stored readings there is no foundation for calculating per-unit utility consumption or billing. This is the first building block of the utility billing workflow.

---

## Goals

- Store one set of meter readings per month (year + month combination)
- Cover all 13 meters: 7 electricity, 6 water
- Allow historical readings to be entered (1–2 years of backfill)
- Allow any reading to be edited after entry
- Provide a clean chronological list of all readings months

---

## Non-Goals

- No PDF parsing or CoJ bill import — manual entry only
- No photo storage — deferred to a later spec
- No consumption calculations — readings are raw data only; subtraction for usage happens in a future module
- No allocation or invoicing — that is Module 2b/2c

---

## Constraints

- Must work offline
- No new Python dependencies required
- One reading set per month — duplicate month/year entries are not allowed

---

## Key Decisions

**1. Flat table with one row per month, one column per meter.**

13 meters × 1 row per month is a fixed, known structure. A flat table is simpler than a normalised design (a separate `meters` reference table + a readings join table) and is easier to query, form-build, and reason about. Since the meters at Waybern Mews will not change, there is no benefit to the added complexity of normalisation here.

**2. Readings are stored as cumulative values (not consumption).**

Barry reads the physical meters, which always show a running total. Storing the raw reading preserves the source data. Consumption (this month − last month) is derived at query time, not stored. This avoids storing derived data and keeps the source of truth clean.

**3. Month + year are stored as separate integer columns, not a date.**

The reading logically belongs to a month, not a specific date. Storing year and month as integers (e.g. year=2026, month=4) makes it trivial to query "all readings for 2026" or "reading for April 2026" without date arithmetic. The actual capture date is stored separately as a `reading_date` field.

**4. All meter values are nullable.**

Barry may not always have every reading available when entering data (e.g. a meter is inaccessible). The system should accept a partial reading rather than blocking entry.

**5. The add and edit forms share one template.**

The form is identical for adding and editing — pre-filled for edits, blank for adds. A single template with a conditional action URL avoids duplication.

---

## Data Model

### `meter_readings` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| year | Integer | e.g. 2026 |
| month | Integer | 1–12 |
| reading_date | Date | Actual date Barry took the readings — defaults to last day of month |
| elec_unit_1 | Float (nullable) | kWh |
| elec_unit_2 | Float (nullable) | kWh |
| elec_unit_3 | Float (nullable) | kWh |
| elec_unit_4 | Float (nullable) | kWh |
| elec_unit_5 | Float (nullable) | kWh |
| elec_public_lighting | Float (nullable) | kWh |
| elec_total | Float (nullable) | kWh |
| water_unit_1 | Float (nullable) | kL |
| water_unit_2 | Float (nullable) | kL |
| water_unit_3 | Float (nullable) | kL |
| water_unit_4 | Float (nullable) | kL |
| water_unit_5 | Float (nullable) | kL |
| water_total | Float (nullable) | kL |

**Unique constraint:** `(year, month)` — only one reading set per calendar month.

---

## User Flow

### Viewing all readings
1. Barry clicks "Meter Readings" in the sidebar
2. He sees a list of all months with readings, newest first
3. Each row shows: month/year, reading date, and an Edit button

### Adding a new reading
4. Barry clicks "Add reading"
5. A form loads with: month selector, year input, reading date (pre-filled to last day of selected month), then two sections — Electricity and Water — each with labelled fields for every meter
6. He fills in the values and clicks Save
7. He is returned to the readings list

### Editing an existing reading
8. Barry clicks "Edit" on any row
9. The same form loads, pre-filled with current values
10. He makes corrections and saves
11. He is returned to the readings list

### Entering historical data
- Barry uses "Add reading" repeatedly, selecting the correct month and year each time
- The form accepts any past month/year combination

---

## Edge Cases

- **Duplicate month:** Attempting to save a reading for a month that already exists shows a validation error — does not overwrite silently
- **Partial readings:** Some meter values may be left blank — the form allows this and saves nulls
- **Future months:** The form should not block future dates, but Barry has no reason to enter them
- **Reading date vs month:** The reading date may not fall within the selected month (e.g. Barry takes January readings on 2 February). This is allowed — the month field is what matters for billing, not the exact date

---

## Risks

- **Low.** Straightforward data entry with no business logic.
- The column-per-meter design means that if a new meter is ever added, a schema migration is needed. Acceptable given this is a fixed 5-unit complex.
