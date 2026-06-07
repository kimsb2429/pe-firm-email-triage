"""Cross-step and aggregation validation. No LLM calls."""
from __future__ import annotations

from .schemas import Step1, Step2, TriageRecord


def cross_step_violations(s1: Step1, s2: Step2, triggers: list[str]) -> list[str]:
    """
    Layer 3: verify Step 2 output is consistent with Step 1 signals.
    Returns a list of violation codes; empty list means clean.
    """
    violations: list[str] = []

    # Must-fire checks — drive off the precomputed triggers
    if "reply_draft" in triggers and s2.reply_draft is None:
        violations.append("HIGH_BUT_NO_REPLY")
    if "deadline" in triggers and s2.deadline is None:
        violations.append("DEADLINE_SIGNAL_BUT_NO_EXTRACTION")
    if "next_steps" in triggers and s2.next_steps is None:
        violations.append("PORTCO_PROBLEM_BUT_NO_NEXT_STEPS")

    # Must-not-fire checks
    if s1.priority != "High" and s2.reply_draft:
        violations.append("REPLY_DRAFT_WITHOUT_HIGH_PRIORITY")
    if not s1.has_deadline and s2.deadline:
        violations.append("DEADLINE_EXTRACTED_WITHOUT_SIGNAL")

    return violations


def check_aggregation_integrity(
    results: list[TriageRecord],
    deadlines_log: list,
    reply_drafts: list,
    next_steps_log: list,
    step2_calls: int,
    step2_skipped: int,
    expected_count: int,
) -> None:
    """
    Layer 4: verify post-processing counts match. Raises if any invariant fails;
    these indicate bugs in our code, not LLM drift.
    """
    if len(results) != expected_count:
        raise AssertionError(f"expected {expected_count} results, got {len(results)}")

    ids = [r.id for r in results]
    if len(set(ids)) != len(ids):
        raise AssertionError(f"duplicate IDs in results: {ids}")

    expected_deadlines = sum(
        r.actions.deadline is not None for r in results if r.status == "ok"
    )
    if len(deadlines_log) != expected_deadlines:
        raise AssertionError(
            f"deadlines_log count mismatch: {len(deadlines_log)} vs {expected_deadlines}"
        )

    expected_replies = sum(
        r.actions.reply_draft is not None for r in results if r.status == "ok"
    )
    if len(reply_drafts) != expected_replies:
        raise AssertionError(
            f"reply_drafts count mismatch: {len(reply_drafts)} vs {expected_replies}"
        )

    expected_next_steps = sum(
        r.actions.next_steps is not None for r in results if r.status == "ok"
    )
    if len(next_steps_log) != expected_next_steps:
        raise AssertionError(
            f"next_steps_log count mismatch: {len(next_steps_log)} vs {expected_next_steps}"
        )

    if step2_calls + step2_skipped != sum(1 for r in results if r.status == "ok"):
        raise AssertionError(
            f"step2 totals mismatch: calls={step2_calls} skipped={step2_skipped}"
        )
