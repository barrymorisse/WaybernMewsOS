# validation.md — Module 1: Units & Owners Registry

## Validation Criteria

### Functional Tests
- [ ] Navigating to `/units` shows all 5 units
- [ ] Each unit card shows the correct owner name(s) and occupancy status
- [ ] Clicking a unit opens its detail page
- [ ] Unit detail page shows correct contacts with correct role badges
- [ ] Editing a unit saves changes and returns to the detail page
- [ ] Editing a contact saves changes and returns to the detail page
- [ ] Adding a contact saves correctly and appears on the detail page
- [ ] Deleting a contact removes it and returns to the detail page
- [ ] Seed data is pre-loaded on first run — all 5 units and 13 contacts present

### Edge Case Tests
- [ ] Contacts with no phone or email display a blank (not "None" or an error)
- [ ] Restarting the server does not duplicate seed data
- [ ] Unit 3 (Glynis) correctly shows as "Tenant-occupied" and Glynis appears as Owner but not Resident
- [ ] Unit 1 correctly shows both Barry and Robynne as owners
- [ ] Trustee badges appear for Barry (Unit 1), Lenise (Unit 2), and Glynis (Unit 3)
- [ ] Deleting a contact prompts for confirmation before proceeding

### UX Validation
- [ ] Units list page is scannable at a glance — unit, owner, status visible without clicking
- [ ] Unit detail page shows all contacts and roles clearly
- [ ] Edit forms are pre-filled with current values
- [ ] Cancel buttons return to the correct page without making changes

### Data Integrity
- [ ] All 5 units exist in the database with participation_quota = 0.20
- [ ] No contact appears more than once per unit
- [ ] Role flags in the database match the seeded data in requirements.md
- [ ] Deleting a contact removes it from the database (not just the UI)

---

## Manual Test Script

### Step 1 — Fresh start

Stop the server if running. Delete the database and restart:
```bash
rm data/waybern.db
bash launch.sh
```
Navigate to `http://localhost:8000/units`.

Confirm: 5 unit cards are visible. No errors.

---

### Step 2 — Check seed data

Click **Unit 1**. Confirm:
- Barry Morisse and Robynne Morisse both appear as contacts
- Both have Owner and Resident badges
- Barry has a Trustee badge
- Participation quota shows 20%

Click **Unit 3**. Confirm:
- Glynis Mathew shows Owner and Trustee badges — but NOT Resident
- The unit shows "Tenant-occupied" status
- Noel Fety shows Tenant and Resident badges
- "Noel Fety's wife" appears with phone number only

---

### Step 3 — Edit a unit

On Unit 1, click **Edit unit**. Change the description to "Ground floor". Click Save.
Confirm: returns to Unit 1 detail page. Description now shows "Ground floor".

---

### Step 4 — Edit a contact

On Unit 1, click **Edit** next to Robynne Morisse. Change the phone number to "000 000 0000". Click Save.
Confirm: returns to Unit 1 detail page. Robynne's phone shows "000 000 0000".

Undo: edit Robynne again and restore the correct number (083 256 2578).

---

### Step 5 — Add a contact

On Unit 2, click **Add contact**. Enter:
- Name: Test Person
- Phone: 011 000 0000
- Resident: checked

Click Save. Confirm: Test Person appears in Unit 2's contacts with a Resident badge.

---

### Step 6 — Delete a contact

On Unit 2, click **Delete** next to Test Person.
Confirm: a confirmation prompt appears.
Confirm the deletion. Confirm: Test Person is gone from Unit 2.

---

### Step 7 — Restart check

Stop the server (`Ctrl+C`). Restart it (`bash launch.sh`). Navigate to `/units`.
Confirm: all data is still present. No duplicates have been added.

---

### Step 8 — Check sidebar nav

Confirm: "Units & Owners" link is visible in the sidebar on every page.
Confirm: clicking it from any page returns to `/units`.

---

If all steps pass, Module 1 is complete. Update roadmap.md status to ✅ and proceed to Module 2.
