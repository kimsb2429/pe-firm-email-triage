"""Orchestrates the per-email triage: Step 1 -> skip check -> Step 2 with model routing."""
from __future__ import annotations

import json
from datetime import datetime

from .llm import call_structured, log_skip
from .prompts import load_prompt
from .schemas import Actions, Deadline, Email, Step1, Step2, TriageRecord
from .validate import cross_step_violations


STEP1_MODEL = "claude-haiku-4-5"
STEP2_MODEL_SONNET = "claude-sonnet-4-6"
STEP2_MODEL_HAIKU = "claude-haiku-4-5"


def _triggers_fired(s1: Step1) -> list[str]:
    fired = []
    if s1.priority == "High":
        fired.append("reply_draft")
    if s1.has_deadline:
        fired.append("deadline")
    if s1.category == "Portfolio Update" and s1.portco_problem_flagged:
        fired.append("next_steps")
    return fired


def needs_step2(triggers: list[str]) -> bool:
    return bool(triggers)


def select_step2_model(triggers: list[str]) -> str:
    """Sonnet when we're generating (replies, next steps). Haiku for pure extraction."""
    if {"reply_draft", "next_steps"} & set(triggers):
        return STEP2_MODEL_SONNET
    return STEP2_MODEL_HAIKU


def _email_block(email: Email) -> str:
    return (
        f"Received at: {_anchor_with_weekday(email.received_at)}\n"
        f"From: {email.from_}\n"
        f"Subject: {email.subject}\n\n"
        f"{email.body}"
    )


def _verify_deadline(deadline: Deadline | None) -> Deadline | None:
    """Cross-check: deadline_date's weekday must match the model's claimed
    deadline_weekday. On mismatch (or partial fill), null both fields. The
    verbatim deadline_text stays — that's the source of truth.
    """
    if deadline is None:
        return None
    date_s = deadline.deadline_date
    wd = deadline.deadline_weekday
    if not date_s or not wd:
        return deadline.model_copy(update={"deadline_date": None, "deadline_weekday": None})
    try:
        expected = datetime.fromisoformat(date_s).strftime("%A")
    except ValueError:
        expected = None
    if expected != wd:
        return deadline.model_copy(update={"deadline_date": None, "deadline_weekday": None})
    return deadline


def _anchor_with_weekday(received_at: str) -> str:
    """Append an explicit time + timezone + weekday so the model has an
    unambiguous temporal anchor. The TZ matters: if the model interprets a
    bare date as UTC midnight and normalizes to a default Western TZ, the
    effective 'today' can drift back by one calendar day, shifting all
    weekday arithmetic by -1.
    """
    try:
        dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        # The firm is NYC-based; anchor to noon ET to remove TZ ambiguity.
        return f"{dt.date()}T12:00:00-04:00 ({dt.strftime('%A')}, America/New_York)"
    except (ValueError, AttributeError):
        return received_at




def triage_email(email: Email, *, inbox_owner: str) -> TriageRecord:
    """Run Step 1, decide skip, optionally run Step 2, return a complete record."""
    # --- Step 1 (system prompt is static across all calls -> caches)
    s1_system, s1_version = load_prompt("step1_classify")
    s1 = call_structured(
        system_prompt=s1_system,
        user_message=f"## Email to classify\n\n{_email_block(email)}",
        model=STEP1_MODEL,
        response_model=Step1,
        email_id=email.id,
        step=1,
        prompt_version=s1_version,
    )

    triggers = _triggers_fired(s1)

    # --- Skip check
    if not needs_step2(triggers):
        log_skip(email.id, reason="no_rule_triggered")
        return TriageRecord.from_email(
            email,
            classification=s1,
            actions=Actions(),
        )

    # --- Step 2 (system prompt is static per-model -> caches)
    s2_system, s2_version = load_prompt("step2_act")
    user_message = (
        f"## Inbox owner (recipient, on whose behalf reply drafts are written)\n\n{inbox_owner}\n\n"
        f"## Email\n\n{_email_block(email)}\n\n"
        f"## Step 1 classification\n\n"
        f"```json\n{json.dumps(s1.model_dump(), indent=2)}\n```\n\n"
        f"## Triggers that fired\n\n{', '.join(triggers)}\n\n"
        f"Generate output ONLY for those triggers. All other action fields must be `null`."
    )
    s2_model = select_step2_model(triggers)
    s2 = call_structured(
        system_prompt=s2_system,
        user_message=user_message,
        model=s2_model,
        response_model=Step2,
        email_id=email.id,
        step=2,
        prompt_version=s2_version,
    )

    violations = cross_step_violations(s1, s2, triggers)
    verified_deadline = _verify_deadline(s2.deadline)
    actions = Actions(
        rationale=s2.rationale,
        reply_draft=s2.reply_draft,
        deadline=verified_deadline,
        next_steps=s2.next_steps,
        violations=violations,
    )

    return TriageRecord.from_email(email, classification=s1, actions=actions)
