# tech_stack.md — Waybern Mews OS

## Overview

Waybern Mews OS is a locally-run web application. It runs on Barry's MacBook, is accessed via a browser, and is launched via a double-click script. All data is stored locally. Google Drive provides cloud backup.

The stack is deliberately minimal. Every technology choice was made to reduce complexity, keep costs at zero, and maximise the ability of Claude Code to build and maintain the system reliably.

---

## The Stack

### Backend
| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | **Python 3.11+** | Excellent library ecosystem, strong Claude Code support, familiar from prior projects |
| Framework | **FastAPI** | Fast, modern, excellent for building APIs and serving HTML. Auto-generates API docs. Well-supported by coding agents. |
| Database | **SQLite** (via SQLAlchemy ORM) | Zero infrastructure, single file, offline, free. More than sufficient for 5 units. |
| PDF parsing | **pypdf** | Used to parse City of Joburg utility bills (existing proven pattern) |
| LLM extraction | **Groq API** (`groq` Python library, `llama-3.3-70b-versatile`, temperature=0) | Interprets pypdf raw text into structured JSON. Free tier sufficient for ~2 invoices/month. Can be swapped for Claude API if accuracy becomes insufficient. |
| Environment secrets | **python-dotenv** | Loads `GROQ_API_KEY` and other secrets from `.env` file at startup. `.env` is gitignored. |
| Document generation | **WeasyPrint** or **Jinja2 + HTML→PDF** | For generating levy notices, meeting minutes, financial reports as PDFs |
| Email | **Gmail SMTP** (via Python `smtplib`) | Free, uses existing complex Gmail account, no third-party service needed |

### Frontend
| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Templating | **Jinja2** | Server-side HTML rendering. Simple, fast, no build step. |
| Interactivity | **HTMX** | Enables dynamic page updates (e.g. modals, inline edits, live search) without writing JavaScript. Keeps the frontend simple while still feeling modern. |
| Styling | **Tailwind CSS** (CDN) | Utility-first CSS. Loaded from CDN — no build step, no npm. Clean, minimal design is straightforward to achieve. |
| Icons | **Heroicons** (inline SVG or CDN) | Free, clean icon set that pairs naturally with Tailwind. |

### Infrastructure
| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Hosting | **Local (MacBook)** | Zero cost, offline, no cloud dependency for operation |
| Launcher | **Shell script + macOS shortcut** | Double-click to start server and open browser. One-time setup. |
| Backup | **Google Drive** (complex account) | SQLite `.db` file stored inside Google Drive folder. Automatic sync. |
| Version control | **Git + GitHub** (private repo) | Code is version-controlled. Free private repos on GitHub. |

---

## Architecture

```
[Browser] ←→ [FastAPI server (localhost:8000)]
                    ↓
             [SQLite database]
             [/data/waybern.db]
                    ↓
         [Stored inside Google Drive folder]
         [Auto-synced to cloud]
```

All routes are served by FastAPI. HTML is rendered server-side via Jinja2 templates. HTMX handles partial page updates (e.g. loading a modal, submitting a form without a full reload). No separate frontend build process exists.

---

## Launcher

`launch.sh` contains the startup logic:

```bash
#!/bin/bash
cd "/Users/barrymorisse/Documents/Waybern Mews BC/Operating System"
source venv/bin/activate
uvicorn main:app --reload &
sleep 1
open http://localhost:8000
```

This script is wrapped in a macOS **Automator Application** (`Waybern Mews OS.app`) saved to the Desktop using a "Run Shell Script" action. Double-clicking the Automator app starts the server and opens the browser — no Terminal interaction required.

The server runs persistently in the background until the Mac is rebooted. There is no explicit stop mechanism — the overhead is negligible for a single-user local tool. If the server needs to be killed manually, run: `lsof -ti:8000 | xargs kill -9`

---

## Key Constraints

- **No paid APIs unless absolutely unavoidable.** LLM calls are minimised. PDF parsing, document generation, and email are handled with free Python libraries.
- **No npm, no build steps.** Tailwind is loaded from CDN. HTMX is loaded from CDN. There is no webpack, vite, or node_modules.
- **SQLite only.** No Postgres, no cloud database. The `.db` file is the single source of truth.
- **Python only on the backend.** No mixing in Node.js or other runtimes.
- **Offline first.** The app must default to being functional without internet. Only when internet is required to accomplish the objectives should it be used.

---

## Document Repository

Uploaded files that form part of the complex's records are stored in `documents/` within the project directory, organised by type:

```
documents/
  invoices/       ← CoJ electricity and water PDFs (gitignored)
  insurance/      ← Insurance policy PDFs (gitignored)
```

All document folders are gitignored — uploaded PDFs are sensitive records that must never be committed to GitHub. The SQLite database (`data/waybern.db`) is also gitignored. Both live locally and are synced to cloud via Google Drive only.

CoJ invoice filenames are deterministic: `{invoice_type}_{year}_{month:02d}.pdf` (e.g. `electricity_2026_04.pdf`). This allows duplicate uploads to overwrite cleanly without orphaned files.

Insurance PDF filenames include a timestamp to prevent collisions: `{policy_id}_{document_type}_{timestamp}_{original_stem}.pdf`.

The path relative to the project root is stored in the relevant DB record. Saved PDFs are served back to the browser via FastAPI's `FileResponse`, which streams the file inline with `media_type="application/pdf"` so it opens directly in the browser tab rather than forcing a download.

---

## LLM / AI Usage

LLM calls are reserved for tasks where they provide irreplaceable value. Current usage:

- **Module 2b:** Groq API (`llama-3.3-70b-versatile`) parses CoJ invoice PDF text into structured JSON. pypdf handles text extraction; the LLM handles interpretation. Temperature is set to 0 for deterministic output.
- **Module 11:** Groq API (`llama-3.3-70b-versatile`) is used for two tasks: (1) extracting a structured key facts summary (insurer, cover dates, premium, main covers, key exclusions, excess, emergency contact, broker) from each uploaded insurance document — one call per upload; (2) answering plain-language questions about the policy documents, with page-level citations — one call per question. Context is the full concatenated extracted text of all documents linked to the policy (~64k tokens estimated). Temperature is set to 0. Fallback: Claude Haiku (`claude-haiku-4-5`) via `ANTHROPIC_API_KEY` if Groq free-tier rate limits are hit — a one-line swap in `app/services/insurance_service.py`.

---

## Development Philosophy

- **Spec first.** Every new feature get its own spec folder in `/specs/` before code is written. We should use the workflow in /skills/create_feature_spec.md to create these.
- **One module at a time.** Features are built sequentially, fully completed and tested before the next begins.
- **Comments are mandatory.** All non-trivial functions must have docstrings. Code should be readable by a non-developer who knows what the app does.
- **Agent-friendly structure.** Clear file separation by domain means a coding agent can be given a single router or service file as context without needing the entire codebase.
- **Data Integrity.** There must never be duplicate representations of the same data. If data exists in the database, it must not be stored separately in files, emails, or derived tables. All derived values (e.g. balances) should be computed, not stored unless necessary. Violations of this rule must be corrected immediately.
- **Refactoring.** If a new feature requires messy or duplicated code: Refactor the existing code first, Then implement the feature. Do not layer new functionality on top of poor structure.
- **Flat tables for fixed schemas.** When a table has a known, fixed set of columns that will never change (e.g. 13 named meters across 5 units), prefer a flat table with one column per field over a normalised design with a rows-per-attribute approach. Flat tables are simpler to query, easier to form-build against, and avoid unnecessary joins. Normalisation is preferred when the schema is variable or unknown at design time.

---
