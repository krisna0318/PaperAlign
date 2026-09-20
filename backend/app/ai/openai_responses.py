"""Minimal stateless OpenAI Responses API adapter with strict output validation."""

import json
import time
from collections.abc import Mapping
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from app.domain.ai_review import (
    AiModelDecision,
    AiReviewPacket,
    AiReviewProposal,
    AiUsage,
)
from app.services.ai_review import validate_ai_proposal


class AiProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _nullable_enum(values: list[str]) -> dict[str, Any]:
    if not values:
        return {"type": "null"}
    return {
        "anyOf": [
            {"type": "string", "enum": values},
            {"type": "null"},
        ]
    }


def _decision_schema(packet: AiReviewPacket) -> dict[str, Any]:
    context_ids = [item.block_id for item in packet.context]
    return {
        "type": "object",
        "properties": {
            "selected_role": _nullable_enum([role.value for role in packet.allowed_roles]),
            "selected_scope": _nullable_enum([scope.value for scope in packet.allowed_scopes]),
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "abstained": {"type": "boolean"},
            "reason": {"type": "string"},
            "evidence_block_ids": {
                "type": "array",
                "items": {"type": "string", "enum": context_ids},
            },
        },
        "required": [
            "selected_role",
            "selected_scope",
            "confidence",
            "abstained",
            "reason",
            "evidence_block_ids",
        ],
        "additionalProperties": False,
    }


def _user_payload(packet: AiReviewPacket) -> str:
    payload = {
        "target_block_id": packet.target_block_id,
        "allowed_roles": [role.value for role in packet.allowed_roles],
        "allowed_scopes": [scope.value for scope in packet.allowed_scopes],
        "rules_only_suggestion": (
            {
                "role": packet.rules_only_role.value if packet.rules_only_role else None,
                "scope": packet.rules_only_scope.value if packet.rules_only_scope else None,
                "reasons": packet.rules_only_reasons,
            }
            if packet.rules_only_role is not None
            else None
        ),
        "context": [item.model_dump(mode="json") for item in packet.context],
        "task": packet.task_instruction,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _extract_output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    for item in response.get("output", []):
        if not isinstance(item, Mapping):
            continue
        for content in item.get("content", []):
            if not isinstance(content, Mapping):
                continue
            if content.get("type") == "refusal":
                raise AiProviderError("model_refusal", "Model refused this classification")
            text = content.get("text")
            if content.get("type") == "output_text" and isinstance(text, str):
                return text
    raise AiProviderError("missing_model_output", "Response did not contain output text")


class OpenAIResponsesProvider:
    provider_name: Literal["openai_responses", "deepseek_responses"] = "openai_responses"
    include_store_parameter = True
    include_strict_parameter = True
    reasoning_effort: Literal["none", "low", "high", "max"] | None = None

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30,
        max_output_tokens: int = 500,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("API key is required")
        if not model.strip():
            raise ValueError("Model is required")
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._input_cost = input_cost_per_million
        self._output_cost = output_cost_per_million
        self._client = client

    def _estimated_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if self._input_cost is None or self._output_cost is None:
            return None
        return (
            (input_tokens or 0) * self._input_cost + (output_tokens or 0) * self._output_cost
        ) / 1_000_000

    def review(self, packet: AiReviewPacket) -> AiReviewProposal:
        format_config: dict[str, Any] = {
            "type": "json_schema",
            "name": "paperalign_structure_decision",
            "schema": _decision_schema(packet),
        }
        if self.include_strict_parameter:
            format_config["strict"] = True
        body: dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": packet.system_instruction},
                {"role": "user", "content": _user_payload(packet)},
            ],
            "text": {"format": format_config},
            "max_output_tokens": self._max_output_tokens,
        }
        if self.include_store_parameter:
            body["store"] = False
        if self.reasoning_effort is not None:
            body["reasoning"] = {"effort": self.reasoning_effort}
        started = time.perf_counter()
        try:
            if self._client is None:
                response = httpx.post(
                    f"{self._base_url}/responses",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                    timeout=self._timeout,
                )
            else:
                response = self._client.post(
                    f"{self._base_url}/responses",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                    timeout=self._timeout,
                )
        except httpx.TimeoutException as exc:
            raise AiProviderError(
                "provider_timeout", "Cloud model request timed out", retryable=True
            ) from exc
        except httpx.RequestError as exc:
            raise AiProviderError(
                "provider_network", "Cloud model request failed", retryable=True
            ) from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise AiProviderError(
                f"provider_http_{response.status_code}",
                "Cloud model returned an HTTP error",
                retryable=retryable,
            )
        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AiProviderError(
                "invalid_provider_json", "Cloud model returned invalid JSON"
            ) from exc
        if not isinstance(response_payload, Mapping):
            raise AiProviderError(
                "invalid_provider_json", "Cloud model returned an unexpected JSON shape"
            )
        if response_payload.get("status") not in {None, "completed"}:
            raise AiProviderError("incomplete_response", "Cloud model response was incomplete")
        try:
            decision = AiModelDecision.model_validate_json(_extract_output_text(response_payload))
        except (ValidationError, ValueError) as exc:
            raise AiProviderError(
                "invalid_structured_output", "Cloud model output failed schema validation"
            ) from exc
        usage_payload = response_payload.get("usage") or {}
        if not isinstance(usage_payload, Mapping):
            raise AiProviderError(
                "invalid_provider_usage", "Cloud model returned invalid usage metadata"
            )
        input_tokens = usage_payload.get("input_tokens")
        output_tokens = usage_payload.get("output_tokens")
        total_tokens = usage_payload.get("total_tokens")
        cost = self._estimated_cost(input_tokens, output_tokens)
        try:
            proposal = AiReviewProposal(
                packet_id=packet.packet_id,
                target_block_id=packet.target_block_id,
                target_text_sha256=packet.target_text_sha256,
                selected_role=decision.selected_role,
                selected_scope=decision.selected_scope,
                confidence=decision.confidence,
                abstained=decision.abstained,
                reason=decision.reason,
                evidence_block_ids=decision.evidence_block_ids,
                usage=AiUsage(
                    provider=self.provider_name,
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    elapsed_ms=elapsed_ms,
                    estimated_cost=cost,
                    cost_currency="USD" if cost is not None else None,
                ),
            )
        except ValidationError as exc:
            raise AiProviderError(
                "invalid_provider_usage", "Cloud model returned invalid usage metadata"
            ) from exc
        validate_ai_proposal(packet, proposal)
        return proposal
