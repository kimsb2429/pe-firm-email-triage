# A Simpler Architecture for Email Date Extraction

*Research date: 2026-05-19 · Recency window applied: 12 months*

## Executive Summary

My original 4-layer proposal (LLM intent extraction → dateparser → custom regex layer → ambiguity surfacing) was overengineered. Two materially simpler paths exist for a PE firm's email triage agent:

Option A: Pure LLM via Instructor (recommended for v1). ~30 lines of code. One model call per email with a Pydantic schema, `email_sent_at` as anchor in the system prompt, and a few-shot block defining the PE vocab (Q1, EOW, COB). Recent extraction benchmarks (StructEval, LLMStructBench, RCT-extraction work hitting 94.77% field accuracy) show frontier LLMs are reliable on narrow 3-5 field schemas like this. The earlier "LLMs can't do dates" finding applies narrowly to *arithmetic from an unknown anchor*. Once you provide `email_sent_at`, you're in the LLM's strong-skill zone.

Option B: Microsoft Recognizers-Text + ~20-line preprocessor (deterministic, if cost or auditability matters). Recognizers-Text emits TIMEX3 with a `Mod` field that natively distinguishes "before Friday" (deadline) from "Friday" (event), directly solving the gap I called out as needing a custom layer. Add a tiny regex preprocessor to normalize EOW/EOD/COB/EOM into phrases the grammar understands. One library, no LLM call required for the date-resolution step.

The architecture I originally proposed (LLM + dateparser + custom regex + ambiguity layer) is what you'd build if you started from dateparser and bolted on missing pieces. Starting from Recognizers-Text's `Mod` field, or from a single Instructor call, collapses that into one component.

## Findings

### 1. No off-the-shelf API does the semantic role classification

I checked Google Cloud NL, AWS Comprehend, Azure AI Language, spaCy NER, HuggingFace temporal taggers (Almasian et al.), TempEval-3/TimeBank-trained models. All stop at TIMEX3 surface typing (`DATE`/`TIME`/`DURATION`/`SET`). None natively classify deadline-vs-event-vs-reference. AWS Comprehend Events is the closest but is being deprecated April 2026 for new customers. So "use a managed service" is off the table for the *semantic role* part; that's where you're committed to LLM or rule-based classification.

### 2. Production email-AI products went LLM-first, not parser-first

Superhuman (LangChain co-published case study). Their v1 pure-LLM agent explicitly "struggled to reason about dates accurately, e.g. identify upcoming deadlines." Their fix wasn't to bolt on Duckling. They restructured around (a) query classification, (b) tool calling with structured time-window arguments, and (c) "double-dipping" critical instructions in both system and user messages. They added structure around the LLM, not a deterministic parser before it.

Shortwave (engineering blog + Cognitive Revolution interview). Their stated philosophy: "all reasoning about how to answer a question should be handled by the LLM itself; our job is to find the right data and stuff it into the prompt." Multi-stage RAG with 6 models. No mention of dateparser/Duckling. Date parsing happens inside the LLM, given prompt-injected current-time context.

Lindy, Cal.ai, Fyxer, Motion, and others: no public engineering disclosures. Inference is they're LLM-first with tool calls into a typed API rather than parser-first.

The pattern: the two companies who shipped this at scale and disclosed their architecture both went LLM-first and responded to date-reasoning failures with better orchestration around the LLM, not with a deterministic preprocessor.

### 3. Frontier LLMs are good enough for the extraction + classification step

When the task is *extraction* (find the date phrase in text, classify its role, emit ISO) and the email's send date is provided as anchor:

- StructEval (May 2025) and LLMStructBench (Feb 2026) report frontier models are reliable on narrow schemas with well-defined fields. LLMStructBench specifically uses "everyday email communication" as a target domain.
- Clinical/finance domain-adjacent evidence: Claude hit 94.77% field-level accuracy on RCT extraction (PMC12372713, 2025). "Who Fails Where" (arXiv 2601.09053) found LLMs *outperform humans* on "structured fields like date formatting and measurement decomposition."
- Reliability degrades with schema breadth: at 369 fields, accuracy collapses; at 3-5 fields (your case), it's in the safe regime.
- The Date Fragments / "temporally blind" findings still apply narrowly to the *arithmetic-from-now* case (count days from a hallucinated anchor). They do not invalidate extraction when the anchor is given.

Net: frontier LLM + email_sent_at anchor + structured schema + few-shot for PE vocab is within the reliability envelope for triage. Confidence: medium-high.

### 4. Recognizers-Text's `Mod` field is the key to deterministic deadline semantics

I undervalued this in the first round. Recognizers-Text's TIMEX3 output includes a `Mod` annotation (`before`, `after`, `since`, `until`) alongside the resolved value. So:

- `"before Friday"` → `{timex: "2026-05-22", type: "date", value: "2026-05-22", mod: "before"}`
- `"Friday"` → `{timex: "2026-05-22", type: "date", value: "2026-05-22"}`

The deadline-vs-event distinction is preserved natively. That eliminates the custom layer I proposed.

Coverage breakdown for the PE email vocab:

| Phrase class | Recognizers-Text | Duckling | HeidelTime |
|---|---|---|---|
| Absolute dates ("April 28th") | ✓ | ✓ | ✓ |
| Bare day-of-week ("Friday") + anchor | ✓ | ✓ | ✓ |
| Date ranges ("June 12-13") | ✓ | ✓ | partial |
| "before X" / "by X" with deadline mod | ✓ (`Mod`) | partial (interval) | ✓ (`mod`) |
| Quarters ("Q1", "Q1 2026") | ✓ (.NET/JS strong, Python lags) | ✗ native | ✓ TIMEX-level |
| EOW / EOD / COB / EOM | ✗ | ✗ | ✗ |
| Bare month past-vs-future | ✓ (reference-time aware) | ✓ | ✓ |

Gaps that remain even with Recognizers-Text: business abbreviations (EOW/EOD/COB/EOM). None of the three TIMEX libraries handles these natively. A ~20-line regex preprocessor that maps "by EOW" → "by end of this week" and "by COB Friday" → "by end of day Friday" closes the gap.

Python port caveat: Recognizers-Text's Python port lags the .NET/JS ports on quarter expressions specifically. Run a 10-minute spike to verify "Q1 board pack" parses cleanly in the Python version before committing.

### 5. LLM-native frameworks don't ship a pre-built temporal extractor, but the minimal pattern is tiny

Checked: Instructor, BAML, Pydantic AI, Outlines, LangChain `with_structured_output`, LlamaIndex Pydantic extractors, Marvin AI. None ship an "ExtractTemporalEntities" primitive. They're all schema-validated output layers: you supply the schema and prompt, they handle parsing/retries.

The cleanest minimal pattern is in Instructor (~30 lines):

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import instructor
from anthropic import Anthropic

class TemporalRole(str, Enum):
    DEADLINE = "deadline"
    EVENT = "event"
    REFERENCE = "reference"  # past period mentioned for context
    VAGUE = "vague"          # "next week's meeting" (no specific day)

class TemporalEntity(BaseModel):
    phrase: str = Field(description="Verbatim span from the email")
    role: TemporalRole
    resolved_iso: datetime | None = Field(description="ISO datetime in sender's TZ, None if VAGUE")
    end_iso: datetime | None = Field(description="End of range if applicable (Q1, June 12-13)")
    confidence: float = Field(ge=0, le=1)

class TemporalExtraction(BaseModel):
    entities: list[TemporalEntity]

client = instructor.from_anthropic(Anthropic())

SYSTEM = """You extract temporal entities from PE firm emails.

Email sent at: {sent_at} ({sent_at_dow}, {tz})
Anchor all relative phrases to that datetime.

PE vocabulary:
- EOW = end of business Friday (5pm sender's TZ) of the current week
- EOD / COB = end of business day (5pm) of the day specified or today
- EOM = last business day of the month
- Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec (calendar year unless stated)
- "this Friday" = next upcoming Friday; "next Friday" = the Friday after that

Role definitions:
- DEADLINE: action required by this date ("before Thursday", "by EOW", "by June 30")
- EVENT: something occurs on this date ("offsite June 12-13", "board meeting Friday")
- REFERENCE: a past period mentioned for context ("Q1 board pack", "churn spike in April")
- VAGUE: temporal but no specific day extractable ("next week's meeting", "earliest convenience")

Show day-of-week with each resolved_iso as a self-check.
"""

def extract(email_body: str, sent_at: datetime, tz: str) -> TemporalExtraction:
    return client.chat.completions.create(
        model="claude-opus-4-7",
        response_model=TemporalExtraction,
        max_retries=2,
        messages=[
            {"role": "system", "content": SYSTEM.format(
                sent_at=sent_at.isoformat(), sent_at_dow=sent_at.strftime("%A"), tz=tz)},
            {"role": "user", "content": email_body},
        ],
    )
```

That's the whole thing. No separate dateparser call, no custom regex, no ambiguity layer; the LLM handles all of it given the anchor and few-shot. `max_retries=2` covers Pydantic validation failures. Add a server-side `day_of_week(resolved_iso) == claimed_dow` validator if you want the off-by-one self-check.

### 6. Decision: which path

| Criterion | Option A (Instructor + LLM) | Option B (Recognizers-Text + preprocessor) |
|---|---|---|
| Lines of code | ~30 | ~100 (preprocessor + extractor + role classifier still needs LLM or rules) |
| Per-email cost | ~$0.002-0.01 (one LLM call) | $0 (deterministic) |
| Latency | ~1-2s (LLM call) | ~10-50ms (in-process) |
| Audit trail | LLM reasoning is opaque | Deterministic, fully traceable |
| Handles novel PE vocab | Yes if in few-shot, otherwise reasoning generalizes | No, every new abbrev needs a regex update |
| Handles deadline vs event | Yes via LLM understanding | Yes via `Mod` field, natively |
| Risk profile | Occasional weird outputs; need confidence threshold | Misses anything outside grammar |

Recommendation for v1: Option A. Start with the single Instructor call. You can always migrate the hot-path to Option B later if cost/latency becomes a constraint, and you'll have real production data on which expressions matter most by then. The PE/finance domain has enough novel vocabulary ("dry powder timing", "vintage year", "fund III commitment timing") that the LLM's generalization is more valuable than the deterministic guarantee.

The role classification is the load-bearing piece either way. Whether you use LLM or rules, the four-way classification (deadline/event/reference/vague) is what turns "extracted date" into "actionable triage signal," because a PE firm cares whether "by June 30" is a regulatory deadline or just a calendar date someone mentioned in passing.

## Open Questions

- Per-LLM cost at 200-500 emails/day scale: budget this before committing to Option A.
- Whether the Python port of Recognizers-Text handles "Q1 2026" cleanly: verify with a 10-minute spike if Option B becomes the path.
- Whether the triage agent should also extract *event* objects (not just dates), e.g., "board meeting Friday" → `{event: "board meeting", when: "2026-05-22"}` rather than just the date. If yes, that pushes harder toward LLM-only (Option A) since events need linguistic understanding.

## Sources

Production architectures
- LangChain Breakout Agents: Superhuman's AI: https://www.langchain.com/breakoutagents/superhuman
- ZenML LLMOps Database: Superhuman: https://www.zenml.io/llmops-database/ai-powered-email-search-assistant-with-advanced-cognitive-architecture
- Shortwave: A deep dive into the world's smartest email AI: https://www.shortwave.com/blog/deep-dive-into-worlds-smartest-email-ai/
- Cognitive Revolution: Andrew Lee of Shortwave interview: https://www.cognitiverevolution.ai/the-ai-email-assistant-ive-been-waiting-for-with-andrew-lee-of-shortwave/

Frontier LLM extraction reliability
- StructEval: Benchmarking LLM Structural Outputs (arXiv 2505.20139): https://arxiv.org/html/2505.20139v1
- LLMStructBench (arXiv 2602.14743): https://arxiv.org/abs/2602.14743
- ExtractBench (arXiv 2602.12247): https://arxiv.org/pdf/2602.12247
- SLOT: Structuring LLM Output (EMNLP-Industry 2025): https://aclanthology.org/2025.emnlp-industry.32.pdf
- Claude RCT extraction 94.77% field accuracy: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12372713/
- "Who Fails Where": LLM vs human error patterns in clinical extraction (arXiv 2601.09053): https://arxiv.org/pdf/2601.09053

Temporal libraries & TIMEX3
- Microsoft Recognizers-Text: https://github.com/microsoft/Recognizers-Text
- Recognizers-Text Specs (grammar source of truth): https://github.com/Microsoft/Recognizers-Text/tree/master/Specs
- Recognizers-Text datatypes-timex-expression (Python): https://github.com/microsoft/Recognizers-Text/tree/master/Python/libraries/datatypes-timex-expression
- Facebook Duckling (maintenance mode): https://github.com/facebook/duckling
- HeidelTime: https://github.com/HeidelTime/heideltime
- Almasian temporal_tagger_BERT (HF): https://huggingface.co/satyaalmasian/temporal_tagger_BERT_tokenclassifier
- "A Modular Approach for Multilingual Timex Detection" (arXiv 2304.14221): https://arxiv.org/pdf/2304.14221

LLM-native extraction frameworks
- Instructor docs: https://python.useinstructor.com/
- Instructor: Pydantic Models for Structured Outputs: https://python.useinstructor.com/concepts/models/
- BAML vs Instructor (Glukhov, Dec 2025): https://www.glukhov.org/post/2025/12/baml-vs-instruct-for-structured-output-llm-in-python/
- Pydantic AI: https://ai.pydantic.dev/
- Top 5 Structured Output Libraries for LLMs in 2026: https://dev.to/thedailyagent/top-5-structured-output-libraries-for-llms-in-2026-48g0

Managed services baseline
- Google Cloud Natural Language: https://cloud.google.com/natural-language
- AWS Comprehend Features: https://aws.amazon.com/comprehend/features/

## Excluded Sources

- Marketing comparison posts (unboxd.ai, quotaengine.com, get-alfred.ai, superhuman.com competitor pages): SEO listicles with vendor bias.
- arxiv 1206.5333 (TempEval-3, 2012): foundational but stale; only cited for taxonomic background.
- HeidelTime / SUTime detail pages: heavyweight academic tools not recommended for this use case.
