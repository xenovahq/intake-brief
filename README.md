# Client Intake → Auto Brief Generator

A web application that transforms structured client intake responses into clean, AI-enriched engagement briefs — reducing brief creation from **~40 minutes of manual consolidation to under 2 minutes per submission**.

---

## Problem It Solves

Client discovery starts messy. Responses arrive through forms, emails, and calls — leaving teams to manually piece together context before they can scope, estimate, or propose. This system standardizes that translation: intake data in, structured brief out. No manual reformatting, no missed fields, no inconsistent outputs.

---

## Architecture

The system follows a four-layer model:

**Layer 1 — Input Ingestion**
Reads structured responses from the web intake form. Fields are validated and normalized on submission.

**Layer 2 — Deterministic Processing**
Validates and normalizes each field. Detects missing fields and vague responses (e.g., `"ASAP"` for timeline). Generates a completeness score (0–7) and determines a recommended next step based on what's present or absent.

**Layer 3 — Structured Output Generation**
Merges validated intake data with static firm context and produces a formatted brief. Output is persisted to SQLite and rendered as HTML.

**Layer 4 — AI Enrichment**
Passes structured intake data to `gpt-4o-mini` to generate a project summary in the client's voice, surface likely risk factors, and propose an engagement structure with phases and timeline. Appended as the "AI Consultant Notes" section. Retries up to 3× on failure; skipped gracefully if unavailable.

---

## Key Features

- **Web intake form** — `/intake` is the primary entry point; no CSV editing required
- **AI-enriched briefs** — gpt-4o-mini adds consultant-level analysis to every submission
- **Completeness scoring** — flags missing and vague fields before the brief reaches the team
- **Dynamic next steps** — derived from intake gaps, not hardcoded
- **Firm context injection** — static business context merged into every brief
- **Dashboard** — total briefs, average completeness score, briefs this week, status at a glance
- **Visual brief viewer** — progress bar, amber-highlighted gaps, distinct AI notes card

---

## How to Run

```bash
# 1. Install dependencies:
pip install flask openai

# 2. Set your OpenAI API key (required for AI enrichment):
export OPENAI_API_KEY=sk-...

# 3. Start the server:
python server.py
```

Open **http://localhost:3002/intake** to submit your first client intake.

The dashboard is at **http://localhost:3002/**.

---

## Entry Points

| Route | Purpose |
|---|---|
| `GET /intake` | Submit a new client intake (primary entry point) |
| `POST /intake` | Process form → validate + score + generate brief + AI enrich → redirect |
| `GET /` | Dashboard: all briefs with stats and status |
| `GET /brief/<id>` | Full brief viewer with progress bar and AI notes |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Recommended | Enables AI Consultant Notes via gpt-4o-mini. If absent, the section is skipped gracefully. |

---

## Example Output

The brief viewer shows:

- **Client Overview** — company, industry, decision maker
- **Project Summary** — description, pain point, desired outcome
- **Constraints** — timeline, budget, tools, constraints (amber-highlighted if missing or vague)
- **Completeness score** — rendered as a color-coded progress bar
- **Recommended Next Step** — derived from intake gaps
- **AI Consultant Notes** — project summary, risk factors, and engagement structure from gpt-4o-mini

---

## Why Structured Intake Matters

Unstructured intake creates downstream problems: scoping gaps, missed requirements, and misaligned expectations. A system that enforces structure at the point of intake means the team enters every discovery call with a shared, complete picture of the client — not a set of notes to reconcile.

For professional services firms, this translates to faster proposal cycles, fewer revision loops, and better-qualified work reaching senior staff.
