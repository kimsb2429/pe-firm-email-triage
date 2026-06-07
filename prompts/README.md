# Prompts

Versioned by filename: `step1_classify.v1.md`, `step2_act.v2.md`.

## Conventions

- **Bump the version** when you make a change you want to A/B test, when behavior materially shifts, or when an output file in the repo was produced by a different version.
- **Old versions stay around** — useful for comparison and reproducibility.
- **The active version is selected in `src/prompts.py`** via the `PROMPT_REGISTRY` dict.
- **Every LLM call logs its prompt version** to `output/run.log`. The active versions are also written to `output.json`'s `run_metadata`.

## What's in the prompt vs. the user message

Each `.md` file in this directory contains the **system prompt only** — static instructions, rules, and criteria. The per-email content (the email itself, the Step 1 classification, which triggers fired) is constructed at runtime in `src/triage.py` and passed as the user message. This split keeps the system prompt cacheable across calls.

No templating syntax inside the prompt files — they're plain Markdown.
