# Requirements

The original assessment brief and the 20 sample emails were provided as PDFs marked Confidential. They are not committed to this public repository.

In brief, the assessment asked for an email triage agent for a private equity firm that:

1. Classifies each email (category / priority / summary)
2. Decides and acts (reply draft, deadline extraction, next steps, or mark as read)
3. Produces structured JSON output, aggregations (deadlines / replies / next steps), and a clean HTML report

The agent in this repo is the response. See the top-level [`README.md`](../../README.md) for setup, the [agent spec](../AGENT_SPEC.md) for what it decides, and [`output/`](../../output/) for what it produced on the 20 sample emails.
