"""Anthropic API wrapper with structured outputs, prompt caching, retry, and JSONL logging."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError


# Retryable HTTP status codes for transient Anthropic API errors.
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


T = TypeVar("T", bound=BaseModel)

_client: Optional[anthropic.Anthropic] = None
_log_path: Optional[Path] = None


def _new_totals() -> dict:
    return {
        "step1_calls": 0,
        "step2_calls": 0,
        "step2_skipped": 0,
        "step2_sonnet_calls": 0,
        "step2_haiku_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "errors": 0,
    }


_totals: dict = _new_totals()


def set_log_path(path: Path) -> None:
    global _log_path, _totals
    _log_path = path
    path.parent.mkdir(parents=True, exist_ok=True)
    # Truncate at start of run.
    path.write_text("")
    _totals = _new_totals()


def get_totals() -> dict:
    """Return a copy of in-process run totals."""
    return dict(_totals)


def _log(record: dict) -> None:
    if _log_path is None:
        return
    with _log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def log_skip(email_id: int, reason: str) -> None:
    _totals["step2_skipped"] += 1
    _log({"email_id": email_id, "step": 2, "skipped": True, "skip_reason": reason})


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _strictify_schema(schema: dict) -> dict:
    """
    Recursively transform a Pydantic-generated JSON Schema to satisfy Anthropic's
    strict structured outputs requirements:
      - Every object must have additionalProperties: false
      - Every object must list ALL its properties in `required`
      - Inline $ref into $defs/definitions (Pydantic generates these for nested models)
    """
    defs = schema.get("$defs", {}) or schema.get("definitions", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                name = ref.rsplit("/", 1)[-1]
                if name in defs:
                    return resolve(defs[name])
                return node
            out = {k: resolve(v) for k, v in node.items() if k not in ("$defs", "definitions")}
            if out.get("type") == "object" and "properties" in out:
                out["additionalProperties"] = False
                out["required"] = list(out["properties"].keys())
            return out
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ValidationError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return getattr(exc, "status_code", None) in _RETRYABLE_STATUS
    return False


def call_structured(
    *,
    system_prompt: str,
    user_message: str,
    model: str,
    response_model: type[T],
    email_id: int,
    step: int,
    prompt_version: str,
    max_tokens: int = 2048,
    max_attempts: int = 2,
) -> T:
    """
    Call Claude with structured output and Pydantic validation.

    System prompt is sent with cache_control for prompt caching across calls.
    Retries once on ValidationError or retryable transient API errors (429/5xx).
    Logs each call (and each retry attempt) as JSONL.
    """
    client = _get_client()
    schema = _strictify_schema(response_model.model_json_schema())

    for attempt in range(1, max_attempts + 1):
        started = time.time()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )

            latency_ms = int((time.time() - started) * 1000)
            text = next(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            result = response_model.model_validate_json(text)

            u = response.usage
            usage = {
                "input_tokens": getattr(u, "input_tokens", 0) or 0,
                "output_tokens": getattr(u, "output_tokens", 0) or 0,
                "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                "cache_creation_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            }

            if step == 1:
                _totals["step1_calls"] += 1
            elif step == 2:
                _totals["step2_calls"] += 1
                if model == "claude-sonnet-4-6":
                    _totals["step2_sonnet_calls"] += 1
                elif model == "claude-haiku-4-5":
                    _totals["step2_haiku_calls"] += 1
            for key, val in usage.items():
                _totals[key] += val

            _log(
                {
                    "email_id": email_id,
                    "step": step,
                    "model": model,
                    "prompt_version": prompt_version,
                    **usage,
                    "latency_ms": latency_ms,
                    "attempts": attempt,
                    "status": "ok",
                }
            )
            return result

        except (ValidationError, anthropic.APIError) as e:
            latency_ms = int((time.time() - started) * 1000)
            retryable = _is_retryable(e) and attempt < max_attempts
            if not retryable:
                _totals["errors"] += 1
            _log(
                {
                    "email_id": email_id,
                    "step": step,
                    "model": model,
                    "prompt_version": prompt_version,
                    "latency_ms": latency_ms,
                    "attempts": attempt,
                    "status": "retry" if retryable else "error",
                    "error": str(e),
                }
            )
            if not retryable:
                raise

    raise RuntimeError("call_structured exhausted retries without success")
