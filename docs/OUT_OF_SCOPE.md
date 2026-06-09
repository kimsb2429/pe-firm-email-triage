# Out of Scope

Items considered and deliberately deferred. Each section sketches what would change and the trade-offs involved.

## 1. Email integration

Today the pipeline reads from `data/emails.json` and writes to `output/`. Three seams to replace for production:

**Email source.** Replace `src/main.py:load_emails()` (or wrap it) with a producer that yields `Email` records — same Pydantic shape:

- **Gmail API** — `users.messages.list` + `get`, or `users.watch` for push
- **Microsoft Graph** — `/me/messages` polling, or subscription webhooks for push
- **IMAP** — for self-hosted mailboxes

The producer is the only thing that knows about the source format. Everything downstream consumes `Email`.

**Result sink.** Replace batch file writes with per-email side effects:

- **Draft replies** → write back to the mailbox as drafts (Gmail `drafts.create`, MS Graph `messages` with `isDraft: true`). The partner sees them next to the original.
- **`marked_read`** → flip the actual read flag on the message.
- **Deadlines / next_steps** → fan out to a task system (Todoist, Asana, Linear) or a partner-facing dashboard.
- **`TriageRecord`** → persist to a DB for audit + future training data.

**Triggering.** Move from batch to event-driven: webhook → queue (SQS / Pub/Sub / Redis) → worker calls `triage_email(email, inbox_owner=...)` per message. Idempotency key = message ID.

**What stays the same.** `src/triage.py`, `src/llm.py`, `src/schemas.py`, the prompts, validation. The pipeline is a pure function `Email → TriageRecord` — only the I/O at the seams differs.

**Cross-cutting concerns to add:** OAuth + token refresh per inbox, rate-limit handling on both APIs, PII / data residency review, quarantine queue for `status: "error"`, multi-tenant `INBOX_OWNER` as a per-call parameter.

## 2. Writing-style adaptation

Today's reply drafts have a generic professional tone. In production they should sound like the inbox owner — a partner's note to an LP reads differently from the same person's note to a portco CEO, and a generic draft betrays that it was machine-written.

**Approach:**

- Fetch the owner's sent folder (last N months), bucket by recipient type (LP, banker, internal, portco) or by recipient address
- For each Step 2 call that generates a reply, inject 3–5 stylistically representative sent-mail examples for that bucket as few-shot context
- Or, with enough volume: fine-tune a Haiku variant on the owner's sent corpus

**Trade-offs:**

- **Privacy** — sent mail leaving the firm's VPC may be a non-starter for some clients. Run the model in-tenant if so.
- **Staleness** — style drifts; re-fetch periodically.
- **Cold start** — new inbox owners get the generic tone until they accumulate sent mail.
- **Recipient sensitivity** — bucketing matters: "match my style" averaged across all recipients produces noise; per-recipient-type is better.

## 3. Parallel email processing

The 20-email batch runs sequentially in ~40s. `asyncio.gather` over the per-email triage would land in ~3s. The pipeline is per-email independent — no shared state — so this is mostly a matter of swapping the for-loop for an async fan-out. Anthropic rate limits become the binding constraint, not the code.

## 4. Cross-email state

Linked emails (e.g., an e-signature/NDA request and a separate counterparty follow-up referencing it) are triaged independently today. In production, group threads — by `In-Reply-To` / `References` headers, subject normalization, counterparty domain — and let the agent reason across the group. Concretely: don't draft two separate replies when one acknowledgment covers both, and surface the linkage in the report.

## 5. Learned thresholds

Priority criteria are heuristic — "active deal in motion," "compliance deadline within 30 days." With outcome data (which emails the partner actually responded to, how quickly, with what action), those thresholds could be learned per-inbox. A reinforcement signal as simple as "did the partner accept the draft as-is, edit it, or delete it" is enough to start tuning over weeks.

## 6. Batch processing for cost at scale

The Anthropic Message Batches API offers a 50% discount on input and output tokens in exchange for a 24-hour SLA. Stacks with prompt caching (already on). The biggest cost lever available once volume justifies the latency trade.

**Hybrid routing keyed off Step 1 signals:**

- Real-time path: `priority == "High"` OR `has_deadline` → Step 2 runs immediately
- Batched path: everything else that triggers Step 2 → submitted to the Batches endpoint, results returned the next morning
- Step 1 itself could also batch on short windows (e.g., hourly) — Anthropic batches typically complete in minutes, so freshness is acceptable for most inboxes

**Indicative savings (1K/10K/100K emails per day):**

| Volume | Baseline/year | Hybrid savings | Full-batch savings (24h on everything) |
|---|---|---|---|
| 1K emails/day | ~$2,000 | ~$400 | ~$1,000 |
| 10K emails/day | ~$20,000 | ~$4,000 | ~$10,000 |
| 100K emails/day | ~$200,000 | ~$40,000 | ~$100,000 |

Hybrid saves less than full-batch because under our current skip rule, most non-urgent emails skip Step 2 entirely — there isn't much non-urgent generative work left to discount. The hybrid becomes more compelling for clients who want richer triage on routine mail (e.g., summaries or polite-acknowledge drafts on Medium/Low items) — those naturally route to the batched path.

**Not for MVP:** the brief reads as real-time triage and the absolute dollar savings at low volume are modest. Worth wiring once a production customer with overnight-acceptable workflows comes online.

## 7. Golden-set evolution

The current golden set (`tests/golden.json`, human-readable view at `tests/golden_review.md`) was seeded from the 20-email sample and locks our interpretation of category, priority, signals, and which actions fire per email. It serves as a deterministic regression baseline — zero LLM cost, catches drift after every prompt iteration.

Today it's small enough to over-fit on: a single borderline email (e.g., a "before the close" deadline phrase) can't reliably be flipped via prompt nudges without causing drift elsewhere. With a richer golden set built from real production traffic — say, 200+ partner-reviewed emails covering more category/phrasing variants — prompt changes can be evaluated against a representative sample rather than guessed against 20 cases. Borderline interpretations get calibrated by accumulation rather than debate.

This is the natural next iteration once the agent is integrated with a real inbox (section 1).
