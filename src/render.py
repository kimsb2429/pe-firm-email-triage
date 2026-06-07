"""Render output.json into a static HTML report. Plain CSS, no frameworks."""
from __future__ import annotations

import html

from .aggregate import summarize
from .schemas import TriageRecord


PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _priority_color(priority: str) -> str:
    return {"High": "#c0392b", "Medium": "#d68910", "Low": "#7f8c8d"}.get(
        priority, "#7f8c8d"
    )


def _category_color(category: str) -> str:
    # Distinct palette from priority's (red/orange/gray).
    return {
        "Deal Flow": "#2563eb",          # blue
        "Portfolio Update": "#059669",   # green
        "LP Communication": "#7c3aed",   # purple
        "Compliance": "#92400e",         # deep brown
        "Internal": "#475569",           # slate
        "Press": "#db2777",              # pink
        "Other": "#6b7280",              # cool gray
    }.get(category, "#6b7280")


def _render_record(r: TriageRecord) -> str:
    if r.status == "error":
        return f"""
        <div class="card error">
          <div class="card-header">
            <span class="badge error-badge">Error</span>
            <span class="email-id">#{r.id}</span>
            <span class="from">{_esc(r.from_)}</span>
          </div>
          <div class="subject">{_esc(r.subject)}</div>
          <div class="body">{_esc(r.body)}</div>
          <div class="error-msg">{_esc(r.error)}</div>
        </div>
        """

    c = r.classification
    a = r.actions
    color = _priority_color(c.priority) if c else "#7f8c8d"

    violation_html = ""
    if a.violations:
        violation_html = (
            '<div class="violations">⚠ '
            + ", ".join(_esc(v) for v in a.violations)
            + "</div>"
        )

    actions_html = ""
    if a.reply_draft:
        actions_html += f"""
        <div class="action">
          <div class="action-label">Suggested reply</div>
          <div class="action-body reply">{_esc(a.reply_draft)}</div>
        </div>
        """
    if a.deadline:
        actions_html += f"""
        <div class="action">
          <div class="action-label">Deadline</div>
          <div class="action-body">
            <strong>{_esc(a.deadline.deadline_text)}</strong>{f' <span class="date-iso">→ {_esc(a.deadline.deadline_date)}</span>' if a.deadline.deadline_date else ''}
            <span class="anchor">(received {_esc(r.received_at)})</span>
            <div class="deadline-action">{_esc(a.deadline.action_required)}</div>
          </div>
        </div>
        """
    if a.next_steps:
        items = "".join(f"<li>{_esc(s)}</li>" for s in a.next_steps)
        actions_html += f"""
        <div class="action">
          <div class="action-label">Recommended next steps</div>
          <ol class="next-steps">{items}</ol>
        </div>
        """

    if not actions_html:
        actions_html = '<div class="no-action">No action required. Marked as read.</div>'

    rationale_html = ""
    rationale_parts = []
    if c and c.rationale:
        rationale_parts.append(("Classification rationale", c.rationale))
    if a.rationale:
        rationale_parts.append(("Action rationale", a.rationale))
    if rationale_parts:
        body = "".join(
            f"<div class='rationale-section'><strong>{label}:</strong> {_esc(text)}</div>"
            for label, text in rationale_parts
        )
        rationale_html = f"<details class='rationale'><summary>Why did the agent decide this?</summary>{body}</details>"

    return f"""
    <div class="card">
      <div class="card-header">
        <span class="badge" style="background:{color}">{_esc(c.priority) if c else ''}</span>
        <span class="category" style="background:{_category_color(c.category) if c else '#6b7280'}">{_esc(c.category) if c else ''}</span>
        <span class="email-id">#{r.id}</span>
        <span class="received">received {_esc(r.received_at)}</span>
      </div>
      <div class="from-line"><strong>{_esc(r.from_)}</strong></div>
      <div class="subject">{_esc(r.subject)}</div>
      <div class="body">{_esc(r.body)}</div>
      {f'<div class="action-label">Summary</div><div class="summary">{_esc(c.summary)}</div>' if c else ''}
      {violation_html}
      {actions_html}
      {rationale_html}
    </div>
    """


def render_html(results: list[TriageRecord], run_metadata: dict) -> str:
    sorted_results = sorted(
        results,
        key=lambda r: (
            PRIORITY_ORDER.get(r.classification.priority, 99) if r.classification else 99,
            r.id,
        ),
    )

    counts = summarize(results)
    cat_chips = " ".join(
        f"<span class='chip' style='background:{_category_color(k)}; color:white;'>{_esc(k)}: {v}</span>"
        for k, v in sorted(counts["categories"].items(), key=lambda kv: -kv[1])
    )
    prio_chips = " ".join(
        f"<span class='chip' style='background:{_priority_color(k)}; color:white;'>{_esc(k)}: {counts['priorities'].get(k, 0)}</span>"
        for k in ["High", "Medium", "Low"]
        if counts["priorities"].get(k, 0) > 0
    )
    rule_chips = " ".join(
        f"<span class='chip'>{k}: {v}</span>"
        for k, v in counts["rules"].items()
        if v > 0
    )

    cards = "\n".join(_render_record(r) for r in sorted_results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Email Triage Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 960px; margin: 2rem auto; padding: 0 1rem;
          color: #2c3e50; line-height: 1.5; background: #f8f9fa; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .banner {{ background: white; padding: 1.5rem; border-radius: 8px;
             margin-bottom: 2rem; border-left: 4px solid #34495e; }}
  .meta {{ color: #7f8c8d; font-size: 0.9rem; margin-bottom: 1rem; }}
  .chips {{ margin-top: 0.8rem; }}
  .chip {{ display: inline-block; background: #ecf0f1; padding: 0.2rem 0.6rem;
           border-radius: 12px; font-size: 0.85rem; margin: 0.2rem 0.3rem 0.2rem 0; }}
  .card {{ background: white; padding: 1.2rem; border-radius: 8px;
           margin-bottom: 1rem; border-left: 4px solid #ecf0f1; }}
  .card.error {{ border-left-color: #c0392b; }}
  .card-header {{ font-size: 0.85rem; color: #7f8c8d; margin-bottom: 0.5rem; }}
  .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
            color: white; font-weight: bold; font-size: 0.75rem; margin-right: 0.5rem; }}
  .error-badge {{ background: #c0392b; }}
  .category {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
              color: white; font-weight: bold; font-size: 0.75rem; margin-right: 0.5rem; }}
  .email-id {{ color: #95a5a6; margin-right: 0.6rem; }}
  .received {{ color: #95a5a6; font-style: italic; }}
  .from-line {{ font-size: 0.95rem; color: #34495e; margin-bottom: 0.2rem; }}
  .subject {{ font-weight: bold; font-size: 1.05rem; margin-bottom: 0.6rem; }}
  .body {{ background: #f8f9fa; padding: 0.7rem 0.9rem; border-left: 3px solid #d5dbdb;
           font-size: 0.92rem; white-space: pre-wrap; margin: 0.5rem 0 0.8rem 0;
           color: #4a5568; font-family: Georgia, "Times New Roman", serif; }}
  .summary {{ margin-bottom: 0.8rem; color: #2c3e50; font-weight: 500; }}
  .violations {{ background: #fef5e7; color: #d68910; padding: 0.4rem 0.6rem;
                 border-radius: 4px; font-size: 0.85rem; margin-bottom: 0.6rem; }}
  .action {{ margin-top: 0.8rem; padding-top: 0.6rem; border-top: 1px solid #ecf0f1; }}
  .action-label {{ font-size: 0.8rem; color: #7f8c8d; text-transform: uppercase;
                   letter-spacing: 0.05em; margin-bottom: 0.3rem; }}
  .action-body {{ color: #2c3e50; }}
  .action-body.reply {{ white-space: pre-wrap; background: #f8f9fa;
                        padding: 0.7rem; border-radius: 4px; font-size: 0.95rem; }}
  .anchor {{ color: #95a5a6; font-size: 0.85rem; }}
  .date-iso {{ color: #2980b9; font-weight: 600; font-size: 0.9rem; }}
  .deadline-action {{ margin-top: 0.3rem; }}
  .next-steps {{ margin: 0.3rem 0 0 1.2rem; padding: 0; }}
  .next-steps li {{ margin-bottom: 0.3rem; }}
  .no-action {{ color: #95a5a6; font-style: italic; font-size: 0.9rem; }}
  .rationale {{ margin-top: 0.8rem; font-size: 0.85rem; color: #7f8c8d; }}
  .rationale summary {{ cursor: pointer; }}
  .rationale-section {{ margin-top: 0.4rem; padding-left: 1rem; border-left: 2px solid #ecf0f1; }}
  .error-msg {{ color: #c0392b; font-family: monospace; font-size: 0.85rem;
                background: #fadbd8; padding: 0.5rem; border-radius: 4px; }}
</style>
</head>
<body>

<div class="banner">
  <h1>Email Triage Report</h1>
  <div class="meta">
    Generated {_esc(run_metadata.get("started_at", ""))} ·
    Runtime {run_metadata.get("runtime_s", 0):.1f}s ·
    {len(results)} emails processed ·
    {counts["errors"]} errors
  </div>
  <div class="chips"><strong>Priorities:</strong> {prio_chips}</div>
  <div class="chips"><strong>Categories:</strong> {cat_chips}</div>
  <div class="chips"><strong>Rules fired:</strong> {rule_chips}</div>
</div>

{cards}

</body>
</html>
"""
