"""Entrypoint. Loads emails, triages each, writes output.json, run.log, report.html."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .aggregate import build_aggregations, summarize
from .llm import get_totals, set_log_path
from .prompts import active_versions
from .render import render_html
from .schemas import Email, TriageRecord
from .triage import (
    STEP1_MODEL,
    STEP2_MODEL_HAIKU,
    STEP2_MODEL_SONNET,
    triage_email,
)
from .validate import check_aggregation_integrity


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "emails.json"
OUTPUT_DIR = ROOT / "output"
OUTPUT_JSON = OUTPUT_DIR / "output.json"
OUTPUT_HTML = OUTPUT_DIR / "report.html"
RUN_LOG = OUTPUT_DIR / "run.log"

# The inbox owner — the person whose mail is being triaged. Reply drafts are
# written on their behalf. In production this would come from the email
# system's authenticated user or a workspace config; hardcoded here for the
# take-home dataset.
INBOX_OWNER = "Alex Carter"


def load_emails() -> list[Email]:
    raw = json.loads(DATA_FILE.read_text())
    return [Email.model_validate(item) for item in raw]


def _print_summary(results: list[TriageRecord], totals: dict, runtime_s: float) -> None:
    counts = summarize(results)
    cats = counts["categories"]
    prios = counts["priorities"]
    rules = counts["rules"]
    err_count = counts["errors"]

    print()
    print(f"Triage complete in {runtime_s:.1f}s")
    print(f"  {len(results)} emails processed ({err_count} errors)")
    print(f"  Step 1: {totals['step1_calls']} calls (Haiku)")
    print(
        f"  Step 2: {totals['step2_calls']} calls "
        f"(Sonnet {totals['step2_sonnet_calls']}, Haiku {totals['step2_haiku_calls']}), "
        f"{totals['step2_skipped']} skipped"
    )
    print(
        f"  Tokens: {totals['input_tokens']:,} in / {totals['output_tokens']:,} out"
        + (
            f" ({totals['cache_read_tokens']:,} cache reads)"
            if totals["cache_read_tokens"]
            else ""
        )
    )
    print("  Categories: " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])))
    print("  Priorities: " + ", ".join(f"{k} {prios.get(k, 0)}" for k in ["High", "Medium", "Low"] if prios.get(k, 0) > 0))
    print("  Rules fired: " + ", ".join(f"{k} {v}" for k, v in rules.items() if v > 0))
    print(f"  Output → {OUTPUT_JSON}")
    print(f"  Report → {OUTPUT_HTML}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    set_log_path(RUN_LOG)

    emails = load_emails()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()

    results: list[TriageRecord] = []
    for email in emails:
        try:
            result = triage_email(email, inbox_owner=INBOX_OWNER)
        except Exception as e:
            result = TriageRecord.from_email(
                email,
                status="error",
                error=f"{type(e).__name__}: {e}",
            )
        results.append(result)

    runtime_s = time.time() - t0
    totals = get_totals()
    aggregations = build_aggregations(results)

    check_aggregation_integrity(
        results=results,
        deadlines_log=aggregations["deadlines_log"],
        reply_drafts=aggregations["reply_drafts"],
        next_steps_log=aggregations["next_steps_log"],
        step2_calls=totals["step2_calls"],
        step2_skipped=totals["step2_skipped"],
        expected_count=len(emails),
    )

    run_metadata = {
        "started_at": started_at,
        "runtime_s": round(runtime_s, 2),
        "models": {
            "step1": STEP1_MODEL,
            "step2_default": STEP2_MODEL_SONNET,
            "step2_fallback": STEP2_MODEL_HAIKU,
        },
        "prompt_versions": active_versions(),
        "totals": totals,
    }

    output = {
        "run_metadata": run_metadata,
        "results": [r.model_dump(by_alias=True) for r in results],
        **aggregations,
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2))
    OUTPUT_HTML.write_text(render_html(results, run_metadata))

    _print_summary(results, totals, runtime_s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
