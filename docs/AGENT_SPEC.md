# Agent Spec

Two LLM calls per email, plus a Python skip check between them. Schema field order enforces dependencies within each step.

## Step 1 — Classify

Input: raw email + the email's `received_at` (for priority reasoning).

Output:

```python
class Step1(BaseModel):
    rationale: str
    category: Literal["Deal Flow", "Portfolio Update", "LP Communication",
                      "Compliance", "Internal", "Press", "Other"]
    priority: Literal["High", "Medium", "Low"]
    summary: str
    has_deadline: bool
    portco_problem_flagged: bool
```

### Category

| Category | Definition |
|---|---|
| **Deal Flow** | New investment opportunity, term sheet, NDA/CIM, co-invest, debt financing for a deal |
| **Portfolio Update** | Operational, financial, or governance update from a portfolio company |
| **LP Communication** | Anything to/from a Limited Partner — capital calls, performance reports, commitment changes |
| **Compliance** | Regulatory, legal, audit, or filing requirements |
| **Internal** | From a firm employee — admin, ops, scheduling, model review, expense |
| **Press** | Media inquiry, comment request, journalist outreach |
| **Other** | Recruiters, conferences, vendors, anything else |

Tiebreakers:
- Bank pitching debt financing for a portco *acquisition* → **Deal Flow** (about a new transaction).
- LP asking about a capital call → **LP Communication**.
- DocuSign notification about a deal NDA → **Deal Flow** (the underlying transaction governs).

### Priority

| Priority | Criteria |
|---|---|
| **High** | Active deal in motion, LP committing capital, portco crisis, compliance deadline within 30 days |
| **Medium** | Routine update with an action item, scheduling, internal review with near-term meeting |
| **Low** | FYI-only, marketing, conferences, expense approvals, no time-sensitivity |

When ambiguous, default to the higher priority.

### Signals

- `has_deadline`: true if the email states a date or relative time-bounded ask. "ASAP" without a date does not count.
- `portco_problem_flagged`: true only when `category == "Portfolio Update"` AND the body indicates a problem at the portco — leadership departure, churn spike, customer crisis, regulatory issue, missed targets without a clean explanation. Routine quarterly updates and board prep are not problems.

### Summary

One to two sentences. Specific enough that a partner can decide whether to read the full email from the summary alone. Preserve numbers and named entities.

## Skip rule (Python)

```python
def needs_step2(s1: Step1) -> bool:
    return (
        s1.priority == "High"
        or s1.has_deadline
        or (s1.category == "Portfolio Update" and s1.portco_problem_flagged)
    )
```

If False → no Step 2 call; record is returned with an empty `actions` block. If True → call Step 2.

## Step 2 model routing

```python
def select_step2_model(s1: Step1) -> str:
    needs_generation = (
        s1.priority == "High"
        or (s1.category == "Portfolio Update" and s1.portco_problem_flagged)
    )
    return "claude-sonnet-4-6" if needs_generation else "claude-haiku-4-5"
```

Sonnet only when we're generating (replies, next steps). Haiku is fine for pure extraction (deadline only).

## Step 2 — Decide and act

Input: raw email + Step 1 output + which triggers fired (computed in Python).

Output:

```python
class Step2(BaseModel):
    rationale: str
    reply_draft: Optional[str] = None
    deadline: Optional[Deadline] = None
    next_steps: Optional[list[str]] = None  # 2–3 items when fired

class Deadline(BaseModel):
    deadline_text: str                # verbatim from email
    deadline_date: Optional[str]      # ISO YYYY-MM-DD, NYC TZ; null if not derivable
    deadline_weekday: Optional[DayOfWeek]  # self-check; must match deadline_date
    action_required: str              # short imperative
```

### Rule 1 — High priority → reply_draft

Specific to the email (names, numbers, asks by name). Action-forward (propose a time, confirm a number, name a next step). Short (3–5 sentences). Plausible to send with light edits.

### Rule 2 — has_deadline → deadline

- `deadline_text`: verbatim phrase from the email ("by EOW", "June 30", "this month", "before Thursday").
- `deadline_date`: ISO `YYYY-MM-DD` in America/New_York. The prompt pins a fixed set of interpretation conventions (e.g. "this week" / "by EOW" → upcoming Friday; "by [weekday]" / "before [weekday]" → that weekday) — see [`prompts/step2_act.v2.md`](../prompts/step2_act.v2.md) for the canonical list. Null when the phrase has no derivable date (e.g. "before the close" with the close date stated elsewhere, or "on time" with no anchor).
- `deadline_weekday`: weekday name of `deadline_date`. Self-check — Python post-step nulls both `deadline_date` and `deadline_weekday` if `weekday_of(deadline_date) != deadline_weekday`, defending against the documented LLM weekday-arithmetic failure mode. Verbatim text always stays.
- `action_required`: short imperative.

### Rule 3 — portco_problem_flagged → next_steps

2–3 concrete partner actions. Each step references the email's specifics.
- Bad: "Investigate the issue."
- Good: "Get the SMB churn cohort breakdown by acquisition channel before the board call to isolate whether March's pricing change is fully causal."

## Output shape (per email)

```json
{
  "id": 1,
  "from": "...",
  "subject": "...",
  "received_at": "2026-05-19T09:00:00Z",
  "classification": {
    "rationale": "...",
    "category": "Deal Flow",
    "priority": "High",
    "summary": "...",
    "has_deadline": false,
    "portco_problem_flagged": false
  },
  "actions": {
    "rationale": "...",
    "reply_draft": "Mark — great to hear. ...",
    "deadline": null,
    "next_steps": null
  },
  "status": "ok"
}
```

## Aggregations

| Output | Rule |
|---|---|
| `all_results` | All 20 records |
| `deadlines_log` | Records where `actions.deadline != null` |
| `reply_drafts` | Records where `actions.reply_draft != null` |
| `next_steps_log` | Records where `actions.next_steps != null` |

## Edge cases

- **Linked emails:** Triaged independently. Summaries should make the relationship visible to a human reading the report.
- **Nullable action fields:** Pydantic `Optional[...]` generates JSON Schema with `anyOf [..., null]`. The model emits `null` for triggers that didn't fire.
- **Reply tone:** Match the original. Bankers/LPs formal; internal teammates conversational.
- **Hallucination guardrail:** Drafts and next steps reference only what's in the email body.
