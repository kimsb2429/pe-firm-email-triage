"""
Deterministic golden-set regression test.

Compares the current output.json against a locked tests/golden.json. Catches
prompt-tweak regressions on the deterministic parts of the agent's decisions
(category, priority, signals, which actions fired) without making any LLM
calls. Generative outputs (rationale, summary, reply text, next-step text)
are intentionally NOT checked — they have natural model variance.

A golden field value may be either a scalar (single expected value) or a
list of acceptable values, used for emails on a documented borderline (see
docs/PERFORMANCE.md). The test passes if the observed value is in the set.

Usage:
    python -m tests.test_golden            # run diff; exit 1 on mismatch
    python -m tests.test_golden --update   # re-seed from current output.json
                                           # NOTE: --update writes scalar values
                                           # only; any list-valued borderlines
                                           # must be re-applied by hand.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
GOLDEN_FILE = ROOT / "tests" / "golden.json"
REVIEW_FILE = ROOT / "tests" / "golden_review.md"
EMAILS_FILE = ROOT / "data" / "emails.json"
OUTPUT_FILE = ROOT / "output" / "output.json"

CHECKED_FIELDS = [
    "category",
    "priority",
    "has_deadline",
    "portco_problem_flagged",
    "reply_draft_fired",
    "deadline_fired",
    "next_steps_fired",
]


def _extract_checked(record: dict) -> dict[str, Any]:
    """Pull just the deterministic fields we golden-check."""
    c = record.get("classification") or {}
    a = record.get("actions") or {}
    return {
        "category": c.get("category"),
        "priority": c.get("priority"),
        "has_deadline": c.get("has_deadline"),
        "portco_problem_flagged": c.get("portco_problem_flagged"),
        "reply_draft_fired": a.get("reply_draft") is not None,
        "deadline_fired": a.get("deadline") is not None,
        "next_steps_fired": a.get("next_steps") is not None,
    }


def build_golden_from_output(output: dict) -> dict[str, dict]:
    """Seed golden values from the current output.json."""
    golden = {}
    for r in output["results"]:
        if r.get("status") != "ok":
            continue
        golden[str(r["id"])] = _extract_checked(r)
    return golden


def diff_records(golden: dict, actual: dict) -> list[str]:
    """Return a list of human-readable mismatch lines for one email."""
    mismatches = []
    for field in CHECKED_FIELDS:
        expected = golden.get(field)
        got = actual.get(field)
        acceptable = expected if isinstance(expected, list) else [expected]
        if got not in acceptable:
            expected_repr = " or ".join(repr(v) for v in acceptable)
            mismatches.append(f"  {field}: expected {expected_repr}, got {got!r}")
    return mismatches


def run_diff() -> int:
    if not GOLDEN_FILE.exists():
        print(f"ERROR: {GOLDEN_FILE} not found. Run with --update to seed.")
        return 2

    golden = json.loads(GOLDEN_FILE.read_text())
    output = json.loads(OUTPUT_FILE.read_text())

    actual = {str(r["id"]): _extract_checked(r) for r in output["results"] if r.get("status") == "ok"}

    all_clean = True
    missing_in_actual = sorted(set(golden) - set(actual))
    extra_in_actual = sorted(set(actual) - set(golden))

    if missing_in_actual:
        print(f"MISSING from output (expected in golden): {missing_in_actual}")
        all_clean = False
    if extra_in_actual:
        print(f"EXTRA in output (not in golden): {extra_in_actual}")
        all_clean = False

    mismatch_count = 0
    for email_id in sorted(golden, key=int):
        if email_id not in actual:
            continue
        mismatches = diff_records(golden[email_id], actual[email_id])
        if mismatches:
            mismatch_count += 1
            all_clean = False
            print(f"\nEmail #{email_id} — {len(mismatches)} mismatch(es):")
            for line in mismatches:
                print(line)

    print()
    if all_clean:
        print(f"✓ Golden set clean: all {len(golden)} emails match expected values.")
        return 0
    else:
        print(f"✗ {mismatch_count} email(s) mismatched against golden set.")
        print("  → If the new behavior is intended, re-seed with: python -m tests.test_golden --update")
        return 1


def update_golden() -> int:
    if not OUTPUT_FILE.exists():
        print(f"ERROR: {OUTPUT_FILE} not found. Run the triage pipeline first.")
        return 2

    output = json.loads(OUTPUT_FILE.read_text())
    golden = build_golden_from_output(output)
    GOLDEN_FILE.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
    print(f"✓ Wrote {len(golden)} expected records to {GOLDEN_FILE}")

    emails = {str(e["id"]): e for e in json.loads(EMAILS_FILE.read_text())}
    REVIEW_FILE.write_text(_render_review(golden, emails))
    print(f"✓ Wrote human-readable review to {REVIEW_FILE}")
    return 0


def _render_review(golden: dict, emails: dict) -> str:
    lines = [
        "# Golden Set — Expected Triage Decisions",
        "",
        "Auto-seeded from the most recent `output/output.json`. Review each email below ",
        "and flag any decision you'd grade differently. Corrections should be applied to ",
        "`tests/golden.json` (the regression test reads from there).",
        "",
        "**Fields checked:** `category`, `priority`, `has_deadline`, `portco_problem_flagged`, ",
        "and whether each Step 2 action fired (`reply_draft`, `deadline`, `next_steps`).",
        "",
        "**Not checked:** the generative outputs (rationale, summary, reply text, next-step text). ",
        "Those have natural model variance and are evaluated separately by the LLM grader.",
        "",
        "---",
        "",
    ]

    def fmt(v):
        if isinstance(v, list):
            return " or ".join(str(x) for x in v) + " _(borderline — either accepted)_"
        return str(v)

    def action_label(name, fired):
        if isinstance(fired, list):
            return f"{name} _(borderline — either fires or doesn't)_"
        return name if fired else None

    for email_id in sorted(golden, key=int):
        g = golden[email_id]
        e = emails[email_id]
        action_items = [
            action_label("reply_draft", g["reply_draft_fired"]),
            action_label("deadline", g["deadline_fired"]),
            action_label("next_steps", g["next_steps_fired"]),
        ]
        action_items = [a for a in action_items if a]
        actions_str = ", ".join(action_items) if action_items else "_(none — marked as read)_"

        body = e["body"].strip().replace("\n", " ")

        lines.extend(
            [
                f"### Email #{email_id}",
                f"**From:** {e['from']}  ",
                f"**Subject:** {e['subject']}",
                "",
                f"> {body}",
                "",
                f"- **Category:** {fmt(g['category'])}",
                f"- **Priority:** {fmt(g['priority'])}",
                f"- **has_deadline:** {fmt(g['has_deadline'])}",
                f"- **portco_problem_flagged:** {fmt(g['portco_problem_flagged'])}",
                f"- **Actions fired:** {actions_str}",
                "",
                "---",
                "",
            ]
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Refresh golden from current output.json")
    args = parser.parse_args(argv)

    if args.update:
        return update_golden()
    return run_diff()


def test_golden_set_matches() -> None:
    assert run_diff() == 0


if __name__ == "__main__":
    sys.exit(main())
