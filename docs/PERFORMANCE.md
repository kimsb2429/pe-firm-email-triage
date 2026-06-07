# Performance

Observed runtime and decision-variability across 3 independent end-to-end runs against the 20-email dataset. Measured at `temperature=0` — the residual variance below is the irreducible floor, not something further tuning can remove. See `COST_ANALYSIS.md` for the cost side of the same study.

## Method

3 independent runs from fresh git worktrees, each invoking `python -m src.main` against the same 20 emails. No shared state. Anthropic's prompt cache may have been warm across runs (cache reads were elevated on runs 2/3) but per-call work is identical.

## Runtime

| Run | Wall time | Step 1 calls | Step 2 calls | Per-email avg |
|---|---|---|---|---|
| 1 | 140s | 20 | 14 (10 Sonnet, 4 Haiku) | 7.0s |
| 2 | 155s | 20 | 15 (11 Sonnet, 4 Haiku) | 7.8s |
| 3 | 173s | 20 | 15 (11 Sonnet, 4 Haiku) | 8.7s |

Sequential. Wall time is dominated by Anthropic API latency, not by Python compute. The ~25% run-to-run runtime spread is API-side variance, not pipeline-side.

`asyncio.gather` parallelization would compress this to a few seconds for the same workload — the bottleneck is sequential round-trips, not total compute.

## Decision variability

Each run produced **99/100 stable deterministic decisions** (5 deterministic fields × 20 emails). Each run flickered on exactly one borderline email — a different email each time:

| Run | Email | Drift | Notes |
|---|---|---|---|
| 1 | #10 DocuSign NDA | Priority `Medium` (golden=`High`); no reply_draft fired | Defensible: automated notification, no urgency language |
| 2 | #2 Momentum Q1 update | Priority `Low` (golden=`Medium`) | Defensible: routine FYI with no concrete ask |
| 3 | #3 Capital call wire | `has_deadline=false`; no deadline fired | Defensible: email *references* a deadline, doesn't *state* one |

**Pattern:** stable decisions stay stable; flickers cluster on emails whose facts genuinely admit two readings (e.g., #3's capital-call email *references* a deadline rather than stating one).

**This is the floor at `temperature=0`.** LLMs retain residual non-determinism at temp=0 from batching and floating-point effects — typical for both Anthropic and OpenAI models. Lower noise would require either deterministic post-processing rules over Step 1 output, or an ensemble (run 3x, take majority).

## Generative variability

Rationales paraphrase but converge structurally across runs. Reply drafts open with different greetings but hit the same beats and use `[insert ...]` placeholders consistently where the partner needs to confirm specifics. Next-step lists for #7 (CEO resignation) and #16 (churn spike) vary in wording but converge on the same substantive actions — e.g., every run for #16 asks for an SMB churn cohort breakdown and a board-call briefing note.

No fabricated commitments observed across the 3 runs — the [blanks] mechanism in `prompts/step2_act.v2.md` is holding.

## Validation

Zero cross-step consistency violations and zero pipeline errors across all 3 runs.
