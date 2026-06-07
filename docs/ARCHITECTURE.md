# Architecture

How the code is organized. For *what* the agent decides, see [AGENT_SPEC.md](AGENT_SPEC.md).

## System diagram

```
  data/emails.json          prompts/*.v*.md
        │                          │
        ▼                          ▼
  ┌──────────────────────────────────────────────────────┐
  │                    src/main.py                       │
  │   (entrypoint: load → triage each → aggregate →      │
  │    write outputs → print summary)                    │
  └────────────────────────┬─────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │     src/triage.py      │ ◀── orchestrates per-email
              │  Step 1 → skip → Step 2│
              └─────────┬──────────────┘
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
       ┌────────────┐      ┌───────────────┐
       │ src/llm.py │      │src/validate.py│
       │ Anthropic  │      │ cross-step    │
       │ wrapper +  │      │ consistency   │
       │ retry +    │      └───────────────┘
       │ JSONL log  │
       └─────┬──────┘
             │
             ▼
       ┌─────────────────┐
       │ Anthropic API   │
       │ (Haiku, Sonnet) │
       └─────────────────┘

  After all 20 emails triage:

  src/aggregate.py  → slices results into deadlines_log / replies / next_steps_log
  src/render.py     → renders output.json into report.html

  Outputs written to:
    output/output.json    output/run.log    output/report.html
```

## Module responsibilities

| Module | Responsibility |
|---|---|
| `src/main.py` | Entrypoint. Loads emails, runs per-email try/except, aggregates results, writes all output files, prints console summary. |
| `src/triage.py` | Per-email orchestration: Step 1 → skip check → Step 2 with model routing → cross-step validation. |
| `src/llm.py` | Anthropic API wrapper. Strict structured outputs (`output_config.format`), prompt caching, retry on `ValidationError`, JSONL run log. |
| `src/prompts.py` | Prompt loader with version registry. Single source of truth for which prompt version is active. |
| `src/schemas.py` | Pydantic models (`Email`, `Step1`, `Step2`, `Deadline`, `Actions`, `TriageRecord`) + intra-model validators. |
| `src/validate.py` | Cross-step and aggregation integrity checks. No LLM calls. |
| `src/aggregate.py` | Pure post-processing. Slices per-email results into the four required output collections. |
| `src/render.py` | HTML generation. Plain CSS, no JS, no frameworks. |

## Data flow

```
emails.json
   │
   ▼ load_emails()
[Email, ...]
   │
   ▼ for each email:
   │      ┌── triage_email() ──┐
   │      │                    │
   │      ▼                    │
   │   Step1 (Pydantic)        │
   │      │                    │
   │      ▼  needs_step2?      │
   │     yes ──▶ Step2 + cross-step violations
   │      │       │
   │      │       ▼
   │      └──▶ TriageRecord
   │
[TriageRecord, ...]
   │
   ├─▶ build_aggregations() ──▶ deadlines_log, reply_drafts, next_steps_log
   │
   ├─▶ check_aggregation_integrity()   (raises on bug)
   │
   └─▶ render_html() ──▶ report.html

   output.json = run_metadata + results + aggregations
   run.log     = one JSONL line per LLM call + per skip event
```

## Cross-cutting concerns

### Prompt caching
System prompts are sent with provider-appropriate caching directives; per-email content goes in the user message so the system prompt stays cacheable.

### Prompt versioning
Prompts are versioned by filename with the active version selected in `src/prompts.py`. See [`prompts/README.md`](../prompts/README.md) for the conventions.

### Structured outputs
Schemas are Pydantic models. `model_json_schema()` is run through `_strictify_schema()` in `llm.py` to satisfy Anthropic's strict mode requirements (`additionalProperties: false`, all properties in `required`, `$ref` inlining). The model emits schema-valid JSON; Pydantic validates as a tripwire.

### Validation layers
Five deterministic Python validation layers — see [VALIDATION.md](VALIDATION.md).

### Error handling
Per-email `try/except` in `main.py`. One bad email is captured as `status: "error"` on the record and the run continues — preserving the other 19 results. Errors are surfaced in the HTML report.

### Observability
JSONL log (`output/run.log`) with one line per LLM call and per skip event. Run metadata block at the top of `output.json`. End-of-run console summary. Detail: [OBSERVABILITY.md](OBSERVABILITY.md).

## External dependencies

- **Anthropic API** — Haiku 4.5 (Step 1, deadline-only Step 2), Sonnet 4.6 (generative Step 2)
- **Pydantic 2.x** — schema definition + JSON Schema generation
- **No other runtime dependencies**

Pinned in `requirements.txt`.

## Tests

`tests/test_golden.py` — deterministic regression check against `tests/golden.json`. No LLM calls. Run after every prompt iteration to catch drift in category/priority/signal decisions.
