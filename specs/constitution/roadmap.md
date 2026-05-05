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
**Status:** ✅ Complete — broken into sub-modules (2a ✅ → 2b ✅ → 2c ✅)

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

### Module 2b: CoJ Bill Parsing
**Status:** ✅ Complete  
**Spec:** `/specs/features/module_2b_coj_bill_parsing/`

Parse the City of Joburg bulk utility bill PDFs to extract the rand amounts and meter readings to be used in consumption calculations and billing. Both Phase 1 (parse and display) and Phase 2 (save to DB) are complete.

**Includes:**
- PDF upload UI (electricity and water & sanitation handled separately, same upload form)
- Automated extraction via pypdf + Groq LLM (llama-3.3-70b-versatile, temperature=0)
- Extraction of reading dates, start/end readings, step charges (usage + rate per step), fixed charges, VAT, total due
- Six-check validation suite: invoice totals, account number, meter number, consumption arithmetic, step usage sum, VAT rate
- Auto-save to DB and PDF storage in `documents/invoices/` when all error checks pass
- Duplicate detection with overwrite confirmation UI (side-by-side comparison of existing vs. new)
- Billing period columns (`billing_year`, `billing_month`) stored on every invoice for future join to meter readings — always one month behind the statement date
- Complex Info settings page (`/complex-info`) for storing and editing reference data (account numbers, meter numbers) used in validation — extensible as more reference data is needed
- DB record panel in results view showing exact rows written to `coj_invoices` and `coj_invoice_line_items`
- Saved invoices history list on the CoJ Invoices page (type, statement month, billing period, invoice number, total due, save date); auto-refreshes after each save via HTMX
- PDF viewer: saved PDFs accessible directly from the history list, opening inline in a new browser tab

---

### Module 2c: Utility Consumption & Allocation
**Status:** ✅ Complete  
**Spec:** `/specs/features/module_2c_utility_allocation/`

Calculate per-unit consumption from stored readings, reconcile against the CoJ invoice, and allocate costs to each unit.

**Data model:**
- `billing_calculations` — one row per billing month; stores CoJ adjustment factors, fixed/variable cost totals, reconciliation results
- `unit_billing_allocations` — five rows per calculation (one per unit); stores electricity and water cost breakdown
- `billing_step_allocations` — one row per consumer per step; stores the full step-by-step workings for display
- `meter_readings` extended with 24 derived columns: raw consumption (`*_consumption`) and CoJ-adjusted consumption (`*_adjusted`) for each of the 6 consumers (5 units + common property), for both electricity and water

**Calculation logic:**
- Raw consumption: `this month reading − last month reading` per unit; common property = `total − sum(units)`, clamped to 0 if negative
- CoJ adjustment factor: `CoJ_consumption ÷ our_total_consumption` (one factor for elec, one for water); may be >1 or <1 depending on reading date differences
- Adjusted figure per consumer: `raw × adjustment_factor` — applied uniformly; adjusted figures sum exactly to CoJ invoice consumption
- Step cost allocation: iterative equal-split algorithm — within each step, usage divided equally among consumers with remaining adjusted usage; exhausted consumers absorbed and remainder redistributed
- Fixed costs split equally across 5 units; sewerage excluded from water billing entirely
- Common property variable cost split equally across 5 units
- Rounding adjustment applied to Unit 1 if needed to ensure `sum(unit bills) = CoJ target` exactly
- Full `Decimal` precision maintained throughout — no intermediate rounding; only formatted for display in templates

**UI:**
- Billing period list page with status badges (Calculated / Pending / Reconciliation Error)
- Overview page: per-unit electricity and water charges in summary table + links to detail screens
- Electricity detail screen: combined meter/adjustment table, step allocation workings, fixed costs, reconciliation
- Water detail screen: same structure with sewer exclusion shown
- Recalculate button with confirmation modal
- Auto-trigger fires when all three inputs (elec invoice, water invoice, meter readings) are present for a billing month

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

## Module 11: Insurance Documents
**Status:** ✅ Complete  
**Spec:** `/specs/features/module_11_insurance/`  

Store and query complex insurance documents via a plain-language chat interface.

**Includes:**
- Policy period records (insurer, cover dates, total premium)
- PDF upload and management via UI, linked to a policy period
- Text extraction on upload via pypdf (with `[Page N]` markers for citations)
- Automatic key facts extraction via Groq on each upload — displayed as a structured card (insurer, cover dates, premium, main covers, key exclusions, claims excess, emergency contact, broker details)
- Plain-language Q&A chat: ask any question, get answers grounded in the documents with page citations
- Original PDF viewer (inline in browser tab, same pattern as Module 2b)
- Confirmation modals on all deletes, with cascade warning when a policy has linked documents
- Visible error banners when LLM calls fail (document saved, Q&A error message shown — never silent)
- LLM: Groq (llama-3.3-70b-versatile, temperature=0); Claude Haiku fallback if free-tier limits are hit
- Uploaded PDFs stored in `documents/insurance/` — gitignored, never committed to GitHub

---

## Revision History

| Date | Change | Updated by |
|------|--------|-----------|
| 2026-04-30 | Initial roadmap created | Barry + Claude |
| 2026-04-30 | Module 2a marked complete; historical readings imported; decimal precision updated to 4dp | Barry + Claude |
| 2026-04-30 | Module 2b data model revised: CoJ data to live in separate `coj_invoices` table, not on `meter_readings` | Barry + Claude |
| 2026-04-30 | Modules 2b and 2c swapped: CoJ PDF parsing now precedes consumption calculations | Barry + Claude |
| 2026-04-30 | Module 2b spec written; folder renamed to `module_2b_coj_bill_parsing` to match naming convention | Barry + Claude |
| 2026-05-01 | Module 2b complete: parsing, 6-check validation suite, auto-save, PDF storage, duplicate handling, Complex Info settings page | Barry + Claude |
| 2026-05-01 | Module 2b extended: invoice history list + PDF viewer added to CoJ Invoices page | Barry + Claude |
| 2026-05-04 | Module 11 spec written: Insurance Documents — PDF upload, key facts extraction, plain-language Q&A with page citations | Barry + Claude |
| 2026-05-04 | Module 11 complete: all routes, models, service layer, and templates built; PDFs gitignored; delete modals with cascade warnings; LLM error handling | Barry + Claude |
| 2026-05-05 | Module 2c complete: billing calculation service, step allocation algorithm, per-unit cost allocations, reconciliation, auto-trigger, list/overview/electricity/water detail screens | Barry + Claude |
| 2026-05-05 | Module 2c: terminology updated throughout — "gross-up" renamed to "adjustment" (CoJ adjustment factor); DB columns renamed accordingly; full Decimal precision maintained, rounding deferred to display only | Barry + Claude |