# roadmap.md — Waybern Mews OS

## Philosophy

The roadmap is organised as a series of modules, each representing a self-contained area of functionality. Modules are built one at a time, in priority order. A module is only begun once the previous one is complete and stable.

Each module gets its own spec file in `/specs/` before any code is written.

The roadmap is a living document. It is updated by the coding agent after each module is completed, and revised by Barry whenever priorities shift.

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🔄 | In progress |
| 📋 | Spec written, not yet built |
| 💡 | Planned, spec not yet written |
| 🔮 | Future / under consideration |

---

## Module 0: Foundation
**Status:** ✅ Complete  

The base application shell. No business logic, but establishes the entire structure that all future modules will plug into.

**Includes:**
- FastAPI app scaffolding (`main.py`, `app/database.py`)
- SQLAlchemy base model setup
- Jinja2 + HTMX + Tailwind integration (CDN, no build step)
- Base HTML layout template (dark sidebar, header, content area)
- Dashboard home page with Module 1 placeholder card
- SQLite database initialisation (`data/waybern.db`)
- `launch.sh` launcher script

**Note:** Google Drive backup deferred — to be added as a standalone feature after core modules are built.

---

## Module 1: Units & Owners Registry
**Status:** ✅ Complete

A registry of all 5 units and every person associated with them.

**Includes:**
- Unit records (unit number, description, participation quota)
- Unified contacts table with role flags: owner, tenant, resident, trustee
- All data entered and managed through the UI
- Units list page and unit detail page
- Edit unit, add contact, edit contact, delete contact via UI
- "Units & Owners" link added to sidebar nav

---

## Module 2: Utility Billing
**Status:** 🔄 In progress — broken into sub-modules (2a → 2b → 2c)

The full utility billing workflow, built incrementally. Each sub-module is a standalone deliverable that feeds into the next.

---

### Module 2a: Meter Readings
**Status:** ✅ Complete

Manual entry and storage of all monthly meter readings taken by Barry at the complex.

**Includes:**
- One reading set per month (year + month)
- 7 electricity meters: Unit 1–5, Public Lighting, Total (kWh)
- 6 water meters: Unit 1–5, Total (kL)
- Add, edit, and list readings via UI
- Supports historical backfill (1–2 years)
- "Meter Readings" link added to sidebar nav

---

### Module 2b: Utility Consumption & Allocation
**Status:** 💡 Planned

Calculate per-unit consumption from stored readings and allocate costs proportionally.

**Includes:**
- Consumption calculation (this month − last month per meter)
- Common property derivation (total − sum of units)
- Proportional allocation to each unit based on participation quota
- Review screen before finalising

---

### Module 2c: CoJ Bill Parsing
**Status:** 💡 Planned

Parse the City of Joburg bulk utility bill PDF to extract the rand amounts to be allocated.

**Includes:**
- PDF upload
- Automated extraction of water, electricity, sewage, refuse line items (pypdf + LLM fallback)
- Link extracted charges to the corresponding month's meter readings
- Utility invoice generation per unit (PDF)

---


## Module 3: Levy Billing
**Status:** 💡 Planned  
**Priority:** High — the most frequent recurring task.

Monthly levy generation and tracking. This replaces the most time-consuming manual task Barry currently does.

**Includes:**
- Levy schedule configuration (base levy per unit, special levies)
- Monthly levy run: one-click generation of levy records for all 5 units
- Levy notice PDF generation (professional letterhead, per unit)
- Email dispatch: send levy notices to all owners in one click
- Payment recording (manual entry of payments received)
- Outstanding balance tracking per unit
- Arrears flagging (automatic when payment is overdue)

**Success criteria:** Barry can complete the full monthly levy cycle (generate → send → record payments) in under 10 minutes, compared to the current manual process.

---

## Module 4: Financial Dashboard
**Status:** 💡 Planned  
**Priority:** Medium — needed for oversight and trustee reporting.

A live view of the complex's financial position.

**Includes:**
- Current bank balance (manually updated)
- Monthly income vs expenditure summary
- Levy collection rate (% paid for current month)
- Outstanding arrears per unit
- Reserve fund balance and target
- Simple annual budget tracking (budget vs actual per category)
- Export to PDF for trustee meetings

**Success criteria:** Barry can see the full financial picture of the complex on one screen, updated to today.

---

## Module 5: Maintenance & Repairs Log
**Status:** 💡 Planned  
**Priority:** Medium.

A log of all maintenance issues, repairs, and contractor work at the complex.

**Includes:**
- Log a new maintenance issue (description, location, date reported, priority)
- Assign to contractor (name, contact, quote amount)
- Track status (reported → quoted → approved → in progress → complete)
- Record actual cost on completion
- Photo attachments (stored locally)
- Filter/search maintenance history
- Flag issues that have exceeded expected resolution time

**Success criteria:** Every maintenance issue at the complex has a record. Barry can see all open items at a glance.

---

## Module 6: Communications
**Status:** 💡 Planned  
**Priority:** Medium.

Formal written communications to owners and tenants, sent from the complex Gmail account.

**Includes:**
- Email composer with owner/unit selection
- Pre-built templates: general notice, levy reminder, arrears notice, maintenance notice, AGM notice
- Send to individual unit or all units
- Sent communications log (what was sent, to whom, when)
- Mail merge fields (owner name, unit number, amount owed, etc.)
- PDF attachment support (e.g. attach levy notice to email)

**Success criteria:** Barry can send a professional formal notice to all owners in under 2 minutes, using a template.

---

## Module 7: Document Library
**Status:** 💡 Planned  
**Priority:** Medium-low.

A structured, searchable store of all complex documents.

**Includes:**
- Document categories: Rules & Governance, Financial, Insurance, Maintenance, Correspondence, Legal
- Upload and tag documents
- Link documents to units, owners, or maintenance records where relevant
- Quick search by category or keyword
- Integration with Google Drive (documents stored in Drive, indexed locally)

**Success criteria:** Any document relating to the complex can be found in under 30 seconds.

---

## Module 8: Meeting Management
**Status:** 💡 Planned  
**Priority:** Medium-low.

Support for trustee meetings and the Annual General Meeting (AGM).

**Includes:**
- Create meeting record (date, type, attendees)
- Agenda builder
- Minutes template (pre-populated from agenda)
- Resolution recording
- Minutes PDF generation (professional format)
- Distribution to owners via email

**Success criteria:** AGM minutes can be drafted, formatted, and distributed without leaving the app.

---

## Module 9: Compliance Calendar
**Status:** 💡 Planned  
**Priority:** Low — but important for avoiding legal risk.

A calendar of recurring compliance obligations under South African sectional title legislation and general property management requirements.

**Includes:**
- Pre-populated calendar of statutory deadlines (AGM timing, insurance renewal, financial year-end, etc.)
- Custom reminder dates (e.g. managing agent contract review)
- Dashboard widget showing upcoming deadlines in the next 30/60/90 days
- Email reminders to Barry

**Success criteria:** No compliance deadline is ever missed because it wasn't on Barry's radar.

---

## Module 10: Contractor & Supplier Directory
**Status:** 🔮 Future consideration  

A directory of trusted contractors and suppliers used at the complex, with contact details, trade, past work history, and performance notes.

---

## Module 11: Insurance Management
**Status:** 🔮 Future consideration  

Tracking of the complex's insurance policy: insurer, policy number, renewal date, cover summary, claims history.

---

## Revision History

| Date | Change | Updated by |
|------|--------|-----------|
| 2026-04-30 | Initial roadmap created | Barry + Claude |