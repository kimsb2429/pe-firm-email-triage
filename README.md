# Email Triage Agent

Triages a private equity firm's inbox: classifies each email, decides what action is needed, and produces a JSON output and HTML report.

## Requirements

The original assessment brief and sample emails were provided as Confidential PDFs and are not committed. [`docs/requirements/`](docs/requirements/) summarizes what was asked.

## Output

The HTML report (`output/report.html`) is generated each run. Open it in any browser. Each email shows its classification, priority, one-line summary, original body, and any actions the agent generated (reply draft, deadline, next steps). Raw structured data is in `output/output.json`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env       # then add your ANTHROPIC_API_KEY
```

Python 3.10+.

## Run

```bash
python -m src.main
```

Outputs land in `output/`:
- `output.json`: structured results + run metadata
- `report.html`: clean report for non-technical readers
- `run.log`: JSONL, one line per LLM call (and per skip)

## Architecture

Two-call pipeline per email:

1. Step 1, classify (Haiku 4.5): category, priority, summary, and trigger signals (`has_deadline`, `portco_problem_flagged`).
2. Skip check (Python): if no rule will fire, mark read and skip Step 2.
3. Step 2, decide & act (Sonnet 4.6, or Haiku if deadline-only): fills `reply_draft`, `deadline`, and `next_steps` for the triggers that fired.

Full design notes (agent spec, architecture, design decisions, what's deliberately out of scope, validation, observability, cost, performance) live in [`docs/`](docs/), with research on date-extraction architecture in [`docs/research/`](docs/research/).

## Assumptions

- The source PDF doesn't include sent timestamps, so all 20 emails are assigned `received_at` of 2026-05-19. In a real inbox this would come from email metadata.
- All dates resolve in America/New_York (firm is NYC-based).
