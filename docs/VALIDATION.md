# Validation

Two kinds of validation in this project:

- Dev-time validation: manual review, grader subagent. Used during prompt iteration. Out of scope for this doc.
- Runtime validation: deterministic Python checks run every time. Covered here.

Five layers, all zero-cost (no LLM calls).

## Layer 1: schema validation (Pydantic, automatic)

Type coercion, `Literal` enum membership, required fields, `Optional` handling. Schema is enforced at the API layer via `output_config.format` with `json_schema` type: grammar-constrained sampling makes the model emit schema-valid output before Pydantic even sees it.

Fail behavior: trigger retry; if retry fails, mark email `status: "error"` and continue the run.

## Layer 2: cross-field consistency within a model

Pydantic `@model_validator` catches contradictions inside a single LLM output.

| Invariant | Where |
|---|---|
| `portco_problem_flagged=True` requires `category="Portfolio Update"` | `Step1.@model_validator` |
| `summary` is non-empty | `Step1.@field_validator` |
| `deadline.deadline_text` is non-empty | `Deadline.@field_validator` |
| `next_steps` has 2–3 items if present | `Step2.@field_validator` |

Fail behavior: same as Layer 1: retry, then `status: "error"`.

## Layer 3: cross-step consistency (must-fire / must-not-fire)

Runs in `triage.py` after both calls return. Verifies the agent's logic actually executed.

```python
def validate_triage(s1: Step1, s2: Optional[Step2]) -> list[str]:
    violations = []

    # Must-fire
    if s1.priority == "High" and (s2 is None or s2.reply_draft is None):
        violations.append("HIGH_BUT_NO_REPLY")
    if s1.has_deadline and (s2 is None or s2.deadline is None):
        violations.append("DEADLINE_SIGNAL_BUT_NO_EXTRACTION")
    if (s1.category == "Portfolio Update" and s1.portco_problem_flagged
        and (s2 is None or s2.next_steps is None)):
        violations.append("PORTCO_PROBLEM_BUT_NO_NEXT_STEPS")

    # Must-not-fire
    if s1.priority != "High" and s2 and s2.reply_draft:
        violations.append("REPLY_DRAFT_WITHOUT_HIGH_PRIORITY")
    if not s1.has_deadline and s2 and s2.deadline:
        violations.append("DEADLINE_EXTRACTED_WITHOUT_SIGNAL")

    # Skip integrity
    if s2 is None and (
        s1.priority == "High" or s1.has_deadline
        or (s1.category == "Portfolio Update" and s1.portco_problem_flagged)
    ):
        violations.append("SKIPPED_BUT_RULE_WOULD_FIRE")

    return violations
```

Fail behavior: record violations on the result, log to JSONL, continue the run. Surfaced in the HTML report as a warning badge.

## Layer 4: deadline weekday cross-check

`triage.py:_verify_deadline()` runs after Step 2 returns. The model emits both `deadline_date` (ISO `YYYY-MM-DD`) and `deadline_weekday` (Monday–Sunday). Python verifies `weekday_of(deadline_date) == deadline_weekday`. On mismatch (or if either is null), both fields are nulled; the verbatim `deadline_text` always stays.

This defends against the documented LLM weekday-arithmetic failure mode (Faith and Fate / Date Fragments): when the model writes "Tuesday + 3 = Saturday May 23" in its rationale, the cross-check rejects the bad date rather than surface false precision to the partner.

Fail behavior: silent null. Verbatim phrase + `received_at` remain as the source of truth.

## Layer 5: aggregation integrity

Runs once at end of pipeline. Bugs here indicate problems in our code, not LLM output.

| Invariant |
|---|
| `len(results) == 20` |
| All `id` values unique, in range 1–20 |
| `len(deadlines_log) == sum(r.actions.deadline is not None for r in results)` |
| Same for `reply_drafts` and `next_steps_log` |
| `run_metadata.totals.step2_skipped + step2_calls == 20` |

Fail behavior: raise. These indicate code bugs, not LLM drift.

## Out of scope for v1

Distributional sanity checks, content-heuristic guards, and LLM-as-judge validation are intentionally deferred.
