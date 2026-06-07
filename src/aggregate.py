"""Post-processing: slice per-email results into the four required outputs."""
from __future__ import annotations

from .schemas import TriageRecord


def summarize(results: list[TriageRecord]) -> dict:
    """Tally categories, priorities, rule firings, and errors across results."""
    categories: dict[str, int] = {}
    priorities: dict[str, int] = {}
    rules = {"replies": 0, "deadlines": 0, "next_steps": 0}
    errors = 0
    for r in results:
        if r.status == "error":
            errors += 1
            continue
        c = r.classification
        if c:
            categories[c.category] = categories.get(c.category, 0) + 1
            priorities[c.priority] = priorities.get(c.priority, 0) + 1
        a = r.actions
        if a.reply_draft:
            rules["replies"] += 1
        if a.deadline:
            rules["deadlines"] += 1
        if a.next_steps:
            rules["next_steps"] += 1
    return {
        "categories": categories,
        "priorities": priorities,
        "rules": rules,
        "errors": errors,
    }


def build_aggregations(results: list[TriageRecord]) -> dict:
    deadlines_log = []
    reply_drafts = []
    next_steps_log = []

    for r in results:
        if r.status != "ok":
            continue
        a = r.actions
        common = {
            "id": r.id,
            "from": r.from_,
            "subject": r.subject,
            "received_at": r.received_at,
        }
        if a.deadline is not None:
            deadlines_log.append({**common, "deadline": a.deadline.model_dump()})
        if a.reply_draft is not None:
            reply_drafts.append({**common, "reply_draft": a.reply_draft})
        if a.next_steps is not None:
            next_steps_log.append({**common, "next_steps": a.next_steps})

    return {
        "deadlines_log": deadlines_log,
        "reply_drafts": reply_drafts,
        "next_steps_log": next_steps_log,
    }
