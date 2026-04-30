# Create Feature Spec

## Purpose

This skill defines how to create high-quality, implementation-ready specifications for new features in Waybern Mews OS.

The goal is to:

* Ensure every feature is well thought through before coding begins
* Minimise rework and ambiguity
* Keep the system aligned with mission.md and tech_stack.md
* Help Barry think clearly about problems and solutions through structured interviewing

This is a **mandatory process**. Do not skip steps.

---

## Core Principles

* **Spec before code.** No feature may be implemented without a completed and approved spec.
* **Clarity over speed.** Take time to understand the problem properly.
* **Simple > clever.** Prefer the simplest solution that works.
* **Single-user optimisation.** This system is for Barry only — avoid unnecessary flexibility.
* **Push back when needed.** Do not blindly accept feature ideas.

---

## Definition of Ready (DoR)

A feature is ready for spec creation only when:

* The problem is clearly understood
* The desired outcome is defined
* The scope is bounded
* Dependencies are known

If these are not met, continue interviewing.

---

## Spec Creation Workflow

Follow this sequence exactly.

---

### Step 1 — Interview Barry

You must interview Barry to clarify the feature before writing anything.

Ask questions in batches (not all at once), adapting based on answers.

#### 1. Problem Understanding

* What are you trying to do?
* What’s frustrating about the current way?
* How often does this happen?
* How long does it currently take?

#### 2. Desired Outcome

* What would the ideal outcome look like?
* What does “done” mean for this feature?

#### 3. Current Process

* Walk me through how you do this today step-by-step
* What tools/files are involved?

#### 4. Data & Entities

* What data is involved?
* Does this relate to units, owners, levies, payments, maintenance, documents, or communications?

#### 5. Edge Cases

* What could go wrong?
* Are there exceptions or unusual scenarios?

#### 6. Automation Level

* Should this be:

  * Fully automatic
  * Draft + review (default)
  * Manual with assistance

#### 7. Constraints

* Does this need to work offline?
* Any legal/compliance considerations?
* Any financial risk?

#### 8. Success Criteria

* How will you know this feature is working well?

---

### Step 2 — Challenge & Simplify

Before writing the spec:

* Does this feature clearly reduce Barry’s time or stress?
* Is there a simpler way to achieve the same outcome?
* Is any part over-engineered?

If needed, propose a simpler version.

---

### Step 3 — Validate Against System Constraints

Check alignment with:

#### mission.md

* Does this support the mission?
* Does it respect guiding principles?

#### tech_stack.md

* Can this be built within the stack?
* Does it introduce new dependencies? (avoid unless necessary)


### Step 4 — Define the Feature Clearly

Before writing files, internally define:

* Problem
* Goals
* Non-goals
* Data impact
* User flow
* Risks

---

### Step 5 — Create Feature Folder

Create:

/specs/features/<feature_name>/

Naming:

* Use snake_case
* Keep it short and descriptive

---

### Step 6 — Write requirements.md

Structure:

```
# requirements.md

## Overview
Short description of the feature

## Problem
What problem this solves

## Goals
What success looks like

## Non-Goals
What this feature explicitly does NOT do

## Constraints
Technical, operational, and legal constraints

## Key Decisions
Important design decisions and reasoning

## Data Model Impact
- New entities?
- Changes to existing ones?

## User Flow
Step-by-step interaction from Barry’s perspective

## Edge Cases
List of tricky or unusual scenarios

## Risks
What could go wrong?
```

---

### Step 7 — Write plan.md

Break implementation into logical task groups:

```
# plan.md

## Plan

### Task Group 1 — Data Layer
Database models, schema changes

### Task Group 2 — Backend Logic
Business logic, services, validation

### Task Group 3 — UI
Pages, forms, interactions (HTMX)

### Task Group 4 — Integration
Connecting components end-to-end

### Task Group 5 — Testing & Validation
Manual + functional validation
```

Each task group should contain clear, numbered tasks.

---

### Step 8 — Write validation.md

This defines success.

```
# validation.md

## Validation Criteria

### Functional Tests
- [ ] Core functionality works

### Edge Case Tests
- [ ] Handles unusual scenarios

### UX Validation
- [ ] Fast and simple to use
- [ ] Minimal steps

### Data Integrity
- [ ] No duplicate data
- [ ] Database reflects correct state

### Automation Check (if applicable)
- [ ] Runs correctly without manual intervention

## Manual Test Script

Step-by-step instructions Barry can follow to verify the feature
```

---

### Step 9 — Present Spec for Approval

Before implementation:

* Show all 3 files
* Highlight:

  * Key decisions
  * Assumptions made
  * Any risks or trade-offs

WAIT for Barry’s approval.

Do not proceed without approval.

---

## Definition of Done (DoD)

A feature is complete when:

* It satisfies the spec
* It works end-to-end
* Data persists correctly
* Edge cases are handled
* Code is clear and commented
* No existing functionality is broken

---

## Post-Implementation Updates

After completing a feature:

1. Review:

   * mission.md
   * tech_stack.md
   * roadmap.md

2. Propose updates:

   * Show exact changes (diff-style or clear before/after)

3. WAIT for approval before applying changes

---

## Feature Retrospective

After completion, reflect:

* What went well?
* What was difficult?
* What should change going forward?

Use this to improve future specs.

---

## Complexity Budget

Always prefer:

* Simple over flexible
* Explicit over abstract
* Hardcoded over configurable (for now)

Avoid over-engineering.

---

## Pushback Rule

You must challenge the feature if:

* It does not clearly reduce time or stress
* It introduces unnecessary complexity
* It violates constraints
* A simpler alternative exists

---

## Anti-Patterns to Avoid

* Over-generalising for future use cases
* Adding configuration Barry won’t use
* Introducing new frameworks unnecessarily
* Duplicating data
* Storing derived values unnecessarily
* Splitting logic across too many files

---

## Naming Conventions

* Feature folders: snake_case
* Database tables: plural snake_case
* Routes: kebab-case or snake_case (consistent)

---

## LLM Usage Rule

Do NOT use LLMs for:

* CRUD logic
* validation
* deterministic workflows

ONLY use LLMs where necessary:

* text generation
* unstructured parsing

---

## Final Instruction

This system is long-lived and mission-critical.

Take the time to think clearly, ask good questions, and produce specs that make implementation straightforward and reliable.
