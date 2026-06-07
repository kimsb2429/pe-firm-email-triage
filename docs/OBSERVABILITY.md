# Observability

Five lean additions wired into the same code paths as the triage logic. Zero external services.

## 1. `rationale` field on both LLM schemas

First field in both Step 1 and Step 2 schemas. Forces the model to articulate reasoning before committing to decisions and gives a debug trace. Honest framing: it's a justification, not a faithful trace of how the model arrived at the decision.

## 2. JSONL run log (`output/run.log`)

One line per LLM call, plus one line per skip event.

```json
{"email_id": 1, "step": 1, "model": "claude-haiku-4-5", "prompt_version": "v1", "input_tokens": 412, "output_tokens": 187, "latency_ms": 624, "attempts": 1, "status": "ok"}
{"email_id": 1, "step": 2, "model": "claude-sonnet-4-6", "prompt_version": "v1", "input_tokens": 578, "output_tokens": 312, "latency_ms": 1840, "attempts": 1, "status": "ok"}
{"email_id": 2, "step": 2, "skipped": true, "skip_reason": "no_rule_triggered"}
```

## 3. Run metadata block at top of `output.json`

```json
{
  "run_metadata": {
    "started_at": "2026-05-19T14:32:00Z",
    "runtime_s": 38.4,
    "models": {"step1": "claude-haiku-4-5", "step2_default": "claude-sonnet-4-6"},
    "prompt_versions": {"step1_classify": "v1", "step2_act": "v1"},
    "totals": {
      "step1_calls": 20,
      "step2_calls": 14,
      "step2_skipped": 6,
      "input_tokens": 11240,
      "output_tokens": 4892,
      "errors": 0
    }
  },
  ...
}
```

## 4. Per-email try/except with status field

Errors are captured per-email; one bad call doesn't void 19 good results.

```python
try:
    result = triage(email)
except Exception as e:
    result = {"id": email.id, "status": "error", "error": str(e), ...}
```

## 5. End-of-run console summary

```
Triage complete in 38.4s
  20 emails processed (0 errors)
  Step 1: 20 calls (Haiku)
  Step 2: 14 calls (Sonnet 10, Haiku 4), 6 skipped
  Tokens: 11,240 in / 4,892 out
  Categories: Deal Flow 6, Portfolio Update 4, LP 3, ...
  Priorities: High 9, Medium 8, Low 3
  Rules fired: replies 9, deadlines 8, next_steps 2
```
