"""Prompt loader with version registry."""
from __future__ import annotations

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PROMPT_REGISTRY = {
    "step1_classify": "step1_classify.v1.md",
    "step2_act": "step2_act.v2.md",
}


def load_prompt(name: str) -> tuple[str, str]:
    """Return (template_text, version_tag) for the active version of a prompt."""
    filename = PROMPT_REGISTRY[name]
    version = filename.rsplit(".", 2)[-2]  # "v1" from "step1_classify.v1.md"
    text = (PROMPTS_DIR / filename).read_text()
    return text, version


def active_versions() -> dict[str, str]:
    """Used by main.py to record active prompt versions in run_metadata."""
    return {name: filename.rsplit(".", 2)[-2] for name, filename in PROMPT_REGISTRY.items()}
