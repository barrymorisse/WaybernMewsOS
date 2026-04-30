# validation.md — Module 2a: Meter Readings

## Validation Criteria

### Functional Tests
- [ ] Navigating to `/meter-readings` loads without errors
- [ ] "Add reading" button opens the form
- [ ] A new reading can be saved successfully
- [ ] Saved reading appears in the list as the correct month/year
- [ ] Clicking "Edit" on a reading opens the form pre-filled with correct values
- [ ] Editing a reading saves changes correctly
- [ ] Readings list is ordered newest first

### Edge Case Tests
- [ ] Attempting to add a reading for a month that already exists shows a clear error — does not silently overwrite
- [ ] A reading with some blank meter fields (partial reading) saves without error
- [ ] A reading with all meter fields blank saves without error
- [ ] Historical months (e.g. January 2024) can be entered without issue
- [ ] Month displays correctly as "January 2026" not "1 2026" or "2026-01"

### UX Validation
- [ ] Electricity and Water sections are clearly separated in the form
- [ ] Each meter field is clearly labelled with its unit (kWh or kL)
- [ ] Cancel button returns to the list without saving
- [ ] Error message for duplicate month is clear and actionable

### Data Integrity
- [ ] Only one row exists per year+month combination
- [ ] Meter values are stored as Floats (not strings)
- [ ] Null values are stored as NULL in the database, not zero or empty string

---

## Manual Test Script

### Step 1 — Load the page

Navigate to `http://localhost:8000/meter-readings`.
Confirm: page loads, empty state message is visible, "Add reading" button is present.

---

### Step 2 — Add a reading

Click "Add reading". Fill in:
- Month: March, Year: 2026, Reading date: 31 March 2026
- Electricity — Unit 1: 1000, Unit 2: 2000, Unit 3: 3000, Unit 4: 4000, Unit 5: 5000, Public Lighting: 500, Total: 15500
- Water — Unit 1: 10, Unit 2: 20, Unit 3: 30, Unit 4: 40, Unit 5: 50, Total: 160

Click Save. Confirm: redirected to list. "March 2026" row is visible with reading date 31 Mar 2026.

---

### Step 3 — Edit a reading

Click "Edit" on the March 2026 row. Confirm all values are pre-filled correctly.
Change Unit 1 Electricity to 1100. Click Save.
Confirm: redirected to list. Edit the row again and confirm Unit 1 Electricity now shows 1100.

---

### Step 4 — Duplicate month check

Click "Add reading". Select March 2026 again and fill in any values. Click Save.
Confirm: an error message appears. No duplicate row is created in the list.

---

### Step 5 — Partial reading

Click "Add reading". Select April 2026. Fill in only Unit 1 Electricity (e.g. 1200). Leave all other fields blank.
Click Save. Confirm: saves without error. April 2026 appears in the list.
Edit it and confirm blank fields are blank (not zero).

---

### Step 6 — Historical entry

Click "Add reading". Select January 2025. Fill in any values. Save.
Confirm: January 2025 appears in the list in the correct chronological position (below more recent months).

---

### Step 7 — Order check

Confirm the list shows readings newest first: most recent month at the top, oldest at the bottom.

---

If all steps pass, Module 2a is complete. Proceed to entering historical data via the UI, then move on to Module 2b.
