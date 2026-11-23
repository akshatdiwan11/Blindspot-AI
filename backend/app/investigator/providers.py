"""LLM provider abstraction.

Providers take a system prompt, a user prompt and a JSON schema and return raw JSON text plus
token usage. Retries (429 / 5xx / network), timeouts and error mapping live here; prompt
building and validation do not.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    kind = "llm_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LLMNotConfigured(LLMError):
    kind = "not_configured"


class LLMAuthError(LLMError):
    kind = "auth"


class LLMTimeout(LLMError):
    kind = "timeout"


class LLMRateLimited(LLMError):
    kind = "rate_limited"


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    attempts: int


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict) -> LLMResponse: ...


class OpenAIChatProvider:
    """OpenAI Chat Completions API, or any OpenAI-compatible endpoint (base URL configurable)."""

    def __init__(self, settings: Settings, *, model: str | None = None, structured: str | None = None, transport: httpx.BaseTransport | None = None):
        key = settings.active_api_key
        if not key:
            raise LLMNotConfigured("No LLM API key is configured. Set OPENAI_API_KEY (or LLM_API_KEY for an OpenAI-compatible provider) on the server.")
        self.name = settings.llm_provider
        self.model = model or settings.llm_model
        self.base_url = settings.llm_base_url.rstrip("/")
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.llm_max_retries
        self.max_tokens = settings.llm_max_output_tokens
        self.structured = structured or ("json_schema" if settings.llm_provider == "openai" else "json_object")
        self._key = key
        self._transport = transport

    def _payload(self, system: str, user: str, schema_name: str, schema: dict) -> dict:
        if self.structured == "json_schema":
            fmt = {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}}
        else:
            fmt = {"type": "json_object"}
            user = user + "\n\nReturn only a JSON object that matches this JSON schema:\n" + json.dumps(schema)
        return {"model": self.model, "temperature": 0.2, "max_tokens": self.max_tokens, "response_format": fmt,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict) -> LLMResponse:
        payload = self._payload(system, user, schema_name, schema)
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        last: Exception | None = None
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            for attempt in range(1, self.max_retries + 2):
                try:
                    r = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                except httpx.TimeoutException as e:
                    last = LLMTimeout(f"The LLM provider did not respond within {self.timeout:g} seconds.")
                    log.warning("LLM timeout (attempt %d): %s", attempt, e)
                except httpx.HTTPError as e:
                    last = LLMError(f"Could not reach the LLM provider: {e.__class__.__name__}.")
                    log.warning("LLM network error (attempt %d): %s", attempt, e)
                else:
                    if r.status_code in (401, 403):
                        raise LLMAuthError("The LLM provider rejected the API key. Check the key configured on the server.")
                    if r.status_code == 429 or r.status_code >= 500:
                        last = LLMRateLimited("The LLM provider is rate limiting requests.") if r.status_code == 429 else LLMError(f"The LLM provider returned an error ({r.status_code}).")
                        log.warning("LLM HTTP %s (attempt %d)", r.status_code, attempt)
                    elif r.status_code >= 400:
                        detail = ""
                        try:
                            detail = r.json().get("error", {}).get("message", "")[:300]
                        except ValueError:
                            pass
                        raise LLMError(f"The LLM request was rejected ({r.status_code}). {detail}".strip())
                    else:
                        data = r.json()
                        choice = (data.get("choices") or [{}])[0]
                        msg = choice.get("message") or {}
                        if msg.get("refusal"):
                            raise LLMError("The model refused to produce a report for this request.")
                        text = msg.get("content") or ""
                        usage = data.get("usage") or {}
                        return LLMResponse(text=text, model=data.get("model", self.model), prompt_tokens=int(usage.get("prompt_tokens", 0)),
                                           completion_tokens=int(usage.get("completion_tokens", 0)),
                                           latency_ms=int((time.perf_counter() - started) * 1000), attempts=attempt)
                if attempt <= self.max_retries:
                    time.sleep(min(8.0, 0.75 * 2 ** (attempt - 1)))
        assert last is not None
        raise last


def get_provider(model: str | None = None) -> LLMProvider:
    """Factory used by the investigator. Tests replace this to inject a scripted provider."""
    settings = get_settings()
    if settings.llm_provider not in ("openai", "openai_compatible"):
        raise LLMNotConfigured(f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Use 'openai' or 'openai_compatible'.")
    return OpenAIChatProvider(settings, model=model)


def estimate_cost(prompt_tokens: int, completion_tokens: int, settings: Settings | None = None) -> float:
    s = settings or get_settings()
    return round(prompt_tokens / 1e6 * s.llm_input_price_per_m + completion_tokens / 1e6 * s.llm_output_price_per_m, 6)
