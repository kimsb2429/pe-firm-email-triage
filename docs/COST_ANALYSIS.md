# Cost Analysis

## Pricing (per million tokens, as of 2026-05)

| Model | Input | Output | Cache read |
|---|---|---|---|
| Claude Haiku 4.5 | $1.00 | $5.00 | $0.10 |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $0.30 |

*Prices estimated. Verify on Anthropic's pricing page. Cache writes cost 25% more than base input.*

## Token estimates per call

| Component | Step 1 (Haiku) | Step 2 (Sonnet) |
|---|---|---|
| System prompt (cached) | ~1,500 | ~1,800 |
| Email + context | ~250 | ~450 |
| Output | ~200 | ~500 |

## Per-run cost (20 emails)

Assumes ~14 emails trigger Step 2 (10 Sonnet + 4 Haiku), prompt caching on.

| Step | Calls | Cost |
|---|---|---|
| Step 1 (Haiku, cache hit on 19/20) | 20 | ~$0.009 |
| Step 2 Sonnet (cache hit on 9/10) | 10 | ~$0.039 |
| Step 2 Haiku (cache hit on 3/4) | 4 | ~$0.005 |
| **Total** | | **~$0.05** |

## Observed (3-run study)

Three independent end-to-end runs against the 20-email dataset, fresh worktrees, no shared state. See `PERFORMANCE.md` for the runtime / variability side.

| Run | Total | Step 1 Haiku | Step 2 Sonnet | Step 2 Haiku |
|---|---|---|---|---|
| 1 | $0.113 | $0.044 | $0.060 | $0.009 |
| 2 | $0.114 | $0.044 | $0.062 | $0.009 |
| 3 | $0.112 | $0.044 | $0.060 | $0.009 |

Run-to-run variance under 1%: cost is highly stable.

Observed runs ran ~2x the $0.05 estimate. The estimate undersized output tokens (rationale + reply_draft + next_steps pushes Step 2 output higher than the 500-token figure) and per-email Step 2 input tokens ran ~30% above the 450 estimate due to richer email bodies than assumed. The scaling projections table below uses the observed ~$0.113/run figure.

## Architecture comparison

| Architecture | Per-run cost |
|---|---|
| Routed (Haiku S1 + Sonnet/Haiku S2 with skip) + caching | $0.05 |
| Routed without caching | $0.25 |
| Single Sonnet call (no Step 1/2 split), with caching | $0.16 |
| Single Sonnet without caching | $0.36 |

Caching + routing combined drops cost ~85% vs the single-Sonnet baseline.

## Scaling projections

Based on the observed ~$0.113/run for 20 emails (~$0.0057/email).

| Volume | Daily cost (routed + cache) | Annual cost |
|---|---|---|
| 100 emails/day | $0.57 | ~$210 |
| 1,000 emails/day | $5.65 | ~$2,065 |
| 10,000 emails/day | $56.50 | ~$20,625 |

## Project budget

| Phase | Cost |
|---|---|
| Development iterations (~20 runs) | ~$1 |
| Grader subagent validation | ~$0.50 |
| Final submission run | ~$0.05 |
| **Total** | **~$2** |

## Not implemented (production notes)

- Finer-grained model routing within Step 2: e.g., Haiku for short deadline + Sonnet for reply on the same email.
