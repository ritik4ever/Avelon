"""Unified model execution engine with strict JSON schema validation."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import settings

logger = structlog.get_logger()


class AIVulnerability(BaseModel):
    type: str = Field(min_length=2, max_length=128)
    function: Optional[str] = None
    severity: str = Field(default="medium")
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=3)

    @field_validator("severity")
    @classmethod
    def normalize_severity(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized in {"info", "low", "medium", "high", "critical"}:
            return normalized
        return "medium"


class AIAuditResponse(BaseModel):
    vulnerabilities: list[AIVulnerability] = Field(default_factory=list)


AUDIT_PROMPT = """You are red-teaming AI code reasoning for smart contract security.

Analyze the Solidity contract and return ONLY this JSON:
{
  "vulnerabilities": [
    {
      "type": "vulnerability type",
      "function": "function name or null",
      "severity": "info|low|medium|high|critical",
      "confidence": 0.0,
      "explanation": "why this is a vulnerability"
    }
  ]
}

Contract:
```solidity
{contract_source}
```"""


COST_PER_1K_TOKENS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = COST_PER_1K_TOKENS.get(model, {"input": 0.005, "output": 0.015})
    return (prompt_tokens / 1000 * rates["input"]) + (completion_tokens / 1000 * rates["output"])


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            raw = "\n".join(lines[1:-1]).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    return json.loads(raw)


def _validate_payload(payload: dict[str, Any]) -> AIAuditResponse:
    return AIAuditResponse(**payload)


def _normalized_result(result: AIAuditResponse) -> list[dict[str, Any]]:
    return [
        {
            "type": vuln.type,
            "function": vuln.function,
            "severity": vuln.severity,
            "confidence": vuln.confidence,
            "explanation": vuln.explanation,
        }
        for vuln in result.vulnerabilities
    ]


async def _audit_with_openai_compatible(
    contract_source: str,
    model: str,
    temperature: float,
    api_key: str,
    api_base: Optional[str] = None,
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if api_base:
        client_kwargs["base_url"] = api_base
    client = AsyncOpenAI(**client_kwargs)
    prompt = AUDIT_PROMPT.format(contract_source=contract_source)

    last_error: Optional[str] = None
    for attempt in range(1, 4):
        started = time.perf_counter()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Return only strict JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            latency_ms = (time.perf_counter() - started) * 1000
            content = (response.choices[0].message.content or "").strip()
            parsed = _extract_json(content)
            validated = _validate_payload(parsed)
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            return {
                "result": validated,
                "raw_response": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost": estimate_cost(model, prompt_tokens, completion_tokens),
                "latency_ms": round(latency_ms, 2),
            }
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = f"invalid_json_attempt_{attempt}: {exc}"
            logger.warning("ai_schema_validation_failed", model=model, attempt=attempt, error=str(exc))
        except Exception as exc:
            last_error = f"provider_error_attempt_{attempt}: {exc}"
            logger.error("ai_provider_call_failed", model=model, attempt=attempt, error=str(exc))

    raise RuntimeError(f"Model output validation failed after retries: {last_error}")


async def _audit_with_google(
    contract_source: str,
    model: str,
    temperature: float,
    api_key: str,
) -> dict[str, Any]:
    prompt = AUDIT_PROMPT.format(contract_source=contract_source)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096},
    }

    last_error: Optional[str] = None
    for attempt in range(1, 4):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            latency_ms = (time.perf_counter() - started) * 1000
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("google model returned no candidates")
            content = candidates[0]["content"]["parts"][0]["text"]
            parsed = _extract_json(content)
            validated = _validate_payload(parsed)
            usage = data.get("usageMetadata", {})
            prompt_tokens = int(usage.get("promptTokenCount", 0))
            completion_tokens = int(usage.get("candidatesTokenCount", 0))
            return {
                "result": validated,
                "raw_response": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost": estimate_cost(model, prompt_tokens, completion_tokens),
                "latency_ms": round(latency_ms, 2),
            }
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = f"invalid_json_attempt_{attempt}: {exc}"
            logger.warning("google_schema_validation_failed", model=model, attempt=attempt, error=str(exc))
        except Exception as exc:
            last_error = f"google_provider_error_attempt_{attempt}: {exc}"
            logger.error("google_provider_call_failed", model=model, attempt=attempt, error=str(exc))

    raise RuntimeError(f"Google model output validation failed after retries: {last_error}")


async def _audit_with_anthropic(
    contract_source: str,
    model: str,
    temperature: float,
    api_key: str,
) -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    prompt = AUDIT_PROMPT.format(contract_source=contract_source)

    last_error: Optional[str] = None
    for attempt in range(1, 4):
        started = time.perf_counter()
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system="Return only strict JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            latency_ms = (time.perf_counter() - started) * 1000
            content = response.content[0].text.strip()
            parsed = _extract_json(content)
            validated = _validate_payload(parsed)
            prompt_tokens = response.usage.input_tokens if response.usage else 0
            completion_tokens = response.usage.output_tokens if response.usage else 0
            return {
                "result": validated,
                "raw_response": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost": estimate_cost(model, prompt_tokens, completion_tokens),
                "latency_ms": round(latency_ms, 2),
            }
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = f"invalid_json_attempt_{attempt}: {exc}"
            logger.warning("anthropic_schema_validation_failed", model=model, attempt=attempt, error=str(exc))
        except Exception as exc:
            last_error = f"anthropic_provider_error_attempt_{attempt}: {exc}"
            logger.error("anthropic_provider_call_failed", model=model, attempt=attempt, error=str(exc))

    raise RuntimeError(f"Anthropic model output validation failed after retries: {last_error}")


async def run_ai_audit(
    contract_source: str,
    provider: str,
    model: str,
    temperature: float = 0.0,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch AI audit to one of supported providers."""
    provider_name = (provider or "openai").strip().lower()
    logger.info("model_execution_start", provider=provider_name, model=model)

    if provider_name == "anthropic":
        result = await _audit_with_anthropic(
            contract_source=contract_source,
            model=model,
            temperature=temperature,
            api_key=api_key or settings.anthropic_api_key,
        )
    elif provider_name == "google":
        result = await _audit_with_google(
            contract_source=contract_source,
            model=model,
            temperature=temperature,
            api_key=api_key or settings.google_api_key,
        )
    elif provider_name == "custom":
        result = await _audit_with_openai_compatible(
            contract_source=contract_source,
            model=model,
            temperature=temperature,
            api_key=api_key or settings.openai_api_key,
            api_base=api_base or settings.custom_openai_base_url or None,
        )
    else:
        result = await _audit_with_openai_compatible(
            contract_source=contract_source,
            model=model,
            temperature=temperature,
            api_key=api_key or settings.openai_api_key,
            api_base=api_base,
        )

    result["normalized_vulnerabilities"] = _normalized_result(result["result"])
    return result
