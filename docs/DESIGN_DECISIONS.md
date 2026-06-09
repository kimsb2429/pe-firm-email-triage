# Design Decisions

A catalog of debates and the choices made, organized by area. Each entry: what we considered, what we chose, why, and what we gave up.

---

## Architecture

### Two LLM calls per email
Considered: (a) one call returning full triage; (b) two calls (classify, then act); (c) per-rule calls (1 classify + up to 3 separate Step 2 calls).
Chose: Two calls.
Why: (a) collapses the brief's framing that each step depends on the prior one into a single prompt. That works, but it hides the dependency. (c) ballooned to 4 schemas, 4 prompts, 4 call sites for what's logically one decision. Two calls preserve the sequential phases without sprawl.
Trade-off: Slightly more orchestration than a single call. Worth it for the explicit step boundary.

### Python skip-check between Step 1 and Step 2
Considered: Always run Step 2; let the model decide whether to fill any action fields.
Chose: Python decides whether to even *call* Step 2.
Why: ~30% of emails (6 of 20) don't trigger any action. Skipping saves the entire Step 2 call. Branching logic in Python is also inspectable in a way prompt branching isn't.
Trade-off: Step 1 has to emit signal fields (`has_deadline`, `portco_problem_flagged`) so Python can decide. Initially resisted adding these, then reversed when the routing payoff became clear.

### Model routing: Haiku for Step 1 + deadline-only Step 2, Sonnet for generative Step 2
Considered: Single Sonnet for everything; dual Sonnet; single Haiku.
Chose: Haiku for classification and pure extraction; Sonnet only for generation (reply drafts, next steps).
Why: Classification is bounded and Haiku is fine at it. Reply quality is where the brief puts its evaluation weight, so Sonnet earns its cost there. Deadline extraction is bounded too, so Haiku is enough.
Trade-off: Two model strings instead of one. ~5 lines of code more.

### Step 2 sees the raw email plus Step 1 output
Considered: Pass only the Step 1 summary to Step 2 (the "agent distillation" pattern).
Chose: Pass the raw email plus the classification context.
Why: Replies and next steps must reference specific names, numbers, and deadlines. Losing those to a summary guarantees generic outputs, which the brief explicitly evaluates against.
Trade-off: Longer Step 2 prompt. Marginal cost; large quality win.

---

## Structured outputs

### `output_config.format` json_schema over tool use
Considered: Tool use with `strict: true` (the older pattern); prompt-and-parse JSON.
Chose: `output_config.format` with `type: "json_schema"`.
Why: Anthropic's native JSON outputs fits what we actually want: structured data, requested directly rather than dressed up as a function call. Tool use was the historical workaround; JSON outputs is now GA. Less ceremony, same grammar-constrained reliability.
Trade-off: None at runtime. Schema must satisfy Anthropic's strict-mode requirements (`additionalProperties: false`, every property in `required`), handled by the `_strictify_schema()` helper.

### Pydantic on top of API-enforced schemas
Considered: Drop Pydantic since strict structured outputs already validates at the API layer.
Chose: Keep Pydantic as a tripwire.
Why: Pydantic is the single source of truth for the schema (`model_json_schema()` feeds the API). The `model_validate_json` on the way back catches rare edge cases (max_tokens truncation, partial responses). Type hints flow through the codebase for free.
Trade-off: Two layers of validation feel redundant. Mitigated by treating Pydantic as a tripwire that should never fire, not as a primary defense.

### `rationale` field first in every LLM schema
Considered: No rationale; rationale as a trailing field.
Chose: First field in every structured output (`Step1`, `Step2`).
Why: Grammar-constrained sampling emits fields in schema order. Putting `rationale` first forces the model to articulate reasoning *before* committing to decisions. That improves output quality and gives a debug trace.
Trade-off: Extra tokens. The rationale is a justification written alongside the decision, useful for debugging rather than as a faithful trace of the model's reasoning.

### Deadline is verbatim text; ISO date is emitted with a checkable companion field
Considered: (a) Have the model resolve "by Thursday" into an ISO date and trust it. (b) Stay verbatim-only and skip ISO conversion entirely.
Chose: Verbatim `deadline_text` is canonical. The model *also* emits `deadline_date` (ISO `YYYY-MM-DD`, regex-validated) and `deadline_weekday` (enum). A post-decode cross-check computes the actual weekday of `deadline_date`; if it doesn't match `deadline_weekday` (or either is missing), both fields are nulled. `deadline_text` always survives. The report shows the verbatim phrase, with the ISO date as a secondary annotation only when it passed the cross-check.
Why: Date arithmetic by a small model is exactly the kind of task that fails silently, so the verbatim phrase stays the source of truth. But forcing the model to commit to *both* a date and its weekday gives a cheap self-consistency check: a wrong date almost always lands on the wrong weekday, and the mismatch is detectable without external date logic.
Trade-off: Slightly more tokens per output and a small post-processing step. In exchange, sortability of deadlines is recovered whenever the cross-check passes, and silent date errors are caught instead of being surfaced as authoritative ISO dates.

### No whitelist of relative date tags
Considered: Restrict `deadline_text` to a fixed enum (`this_week`, `next_week`, `EOW`).
Chose: Free-form non-empty string.
Why: "this month", "before the next board meeting", "in 2 weeks" are all valid; a whitelist just moves the brittleness.
Trade-off: Lose structural validation on this field. The accompanying `action_required` provides interpretive grounding.

### Anchor on email's `received_at`, not on report generation time
Considered: Use the report-generated timestamp as the temporal anchor.
Chose: Per-email `received_at`.
Why: "By Thursday" sent three weeks ago means a Thursday in the past, not next week. Anchoring on report time silently misleads.
Trade-off: Need to plumb `received_at` through to the report's display. Worth it.

---

## Step 1 signal fields

### Add `has_deadline` and `portco_problem_flagged` to Step 1's output
Considered: Keep Step 1 strictly to category/priority/summary; have Step 2 detect deadlines and problems itself.
Chose: Step 1 emits boolean signals; Python uses them to route Step 2.
Why: Without signals, we can't skip Step 2 for any email; it always has to run to detect triggers. With signals, Step 1 (cheap Haiku) tells us whether Step 2 (expensive Sonnet) is needed. Direct cost saving.
Trade-off: Step 1 carries more decisions than the spec literally lists. The spec describes outputs rather than internal signals, which is defensible.

---

## Prompts

### Externalize prompts to `.md` files
Considered: Embed prompts as Python strings in `prompts.py`.
Chose: Plain Markdown files in `prompts/`, loaded at runtime.
Why: Diffs are reviewable as content. Non-engineers can read/edit them. No escaping rules.
Trade-off: One indirection at load time. Worth it.

### Prompt versioning by filename (`step1_classify.v1.md`)
Considered: Git history alone; metadata field inside the prompt; directory-per-version.
Chose: Filename version + a registry dict in `prompts.py` that selects active version.
Why: Old versions stay around as files. Active version is explicit. Every LLM call records its prompt version to `run.log`, so historical outputs are traceable to specific prompts.
Trade-off: Filename versioning is by convention only: discipline-enforced, not code-enforced.

### Static instructions in `system` block (cached); variable content in `user` message
Considered: Put everything in the system prompt (initial implementation).
Chose: System prompt is purely instructions; per-email content is built at runtime as the user message.
Why: The initial implementation defeated prompt caching. Each system prompt was unique because the email body was embedded. Splitting fixed it: 0 cache reads → 9,603 cache reads on the same dataset.
Trade-off: Two strings to maintain per LLM call. Cache savings are large.

---

## Observability

### Lean, in-band observability, no external service
Considered: OpenTelemetry, LangSmith, Anthropic Workbench, structured metrics backend.
Chose: JSONL run log + rationale field + run metadata block + per-email try/except + console summary.
Why: At 20 emails, distributed tracing is overkill. The five lean pieces cover every real failure mode (per-call audit, per-decision explanation, per-run summary, error capture, sanity counts).
Trade-off: No central dashboard. Add one when volume justifies it.

### One retry on `ValidationError`
Considered: Retry forever, retry with exponential backoff, no retry.
Chose: One retry, then fail loudly per-email (and surface as `status: "error"` in the output).
Why: If strict mode + one retry still fails, the prompt is broken, and looping won't fix it. Anthropic SDK already handles transient HTTP retries; ours covers schema drift.
Trade-off: Rare edge cases that would succeed on attempt 3+ are lost. Outweighed by predictable cost ceiling.

---

## Validation

### Build only layers 1–4 (deterministic) into runtime, skip 5–6
Considered: All six layers (schema, intra-model, cross-step, aggregation, distributional, content-heuristic).
Chose: Layers 1–4. Skip distributional sanity and content heuristics for v1.
Why: Layers 1–4 are free, catch real bugs (especially layer 3: the agent says "High priority" but didn't draft a reply). Layers 5–6 are heuristic, misfire-prone, and better handled by the grader subagent at dev time.
Trade-off: Some categories of soft drift go unflagged at runtime. Acceptable.

### No LLM-as-judge in the runtime pipeline
Considered: Have a second model grade each output before writing it.
Chose: No.
Why: Doubles cost, adds latency, and the grader subagent does this better at dev time on the full output set.
Trade-off: Quality regressions in production won't auto-flag. Acceptable until volume justifies.

---

## Scope decisions (in vs out)

### No async/parallelization
Sequential processing for v1. Async/parallelization is the obvious next throughput lever (`asyncio.gather` would compress ~3 min of wall time to a few seconds).

### No tests beyond smoke
Why: A 4–6 hour take-home doesn't earn a test suite. The grader subagent fills the verification role.

### Model aliases, not pinned snapshots
Why: Take-home submission window is short; alias-resolution stays stable in that window. Production should pin specific snapshot IDs for reproducibility; noted in README.

### Linked emails (e-signature request + counterparty follow-up) triaged independently
Why: Cross-email reasoning is a graph problem deserving its own design. v1 acknowledges the gap; the summary text on each email surfaces the relationship to a human reader.

### Mark-as-read is a status field, not a mailbox action
Why: We don't connect to an actual inbox. `marked_read = true` always; it means "the agent has processed this." Action needed by the partner is signaled by the action fields.

