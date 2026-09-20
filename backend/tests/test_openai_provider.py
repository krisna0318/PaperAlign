import json
from pathlib import Path

import httpx
import pytest

from app.ai.deepseek_responses import DeepSeekResponsesProvider
from app.ai.openai_responses import OpenAIResponsesProvider
from app.parsers.errors import DocxAnalysisError
from app.services.ai_review import prepare_ai_review, write_ai_review_plan
from app.services.ai_runner import run_ai_review, write_ai_review_run
from tests.support.structure_factory import paragraph, structured_docx


def _source_and_plan(tmp_path: Path):
    source = structured_docx(tmp_path / "cloud.docx", [paragraph("1 可能是列表")])
    return source, prepare_ai_review(source)


def _success_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "output_text": json.dumps(
            {
                "selected_role": "heading_1",
                "selected_scope": "heading_1",
                "confidence": 0.78,
                "abstained": False,
                "reason": "编号与标题候选一致，但仍建议人工抽查。",
                "evidence_block_ids": ["p-0000"],
            },
            ensure_ascii=False,
        ),
        "usage": {"input_tokens": 120, "output_tokens": 35, "total_tokens": 155},
    }


def test_responses_provider_uses_stateless_strict_schema_and_usage(tmp_path: Path) -> None:
    _, plan = _source_and_plan(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer synthetic-secret"
        assert body["store"] is False
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        return httpx.Response(200, json=_success_payload())

    provider = OpenAIResponsesProvider(
        api_key="synthetic-secret",
        model="synthetic-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        input_cost_per_million=1,
        output_cost_per_million=2,
    )
    proposal = provider.review(plan.packets[0])
    assert proposal.selected_role == "heading_1"
    assert proposal.usage.total_tokens == 155
    assert proposal.usage.estimated_cost == pytest.approx(0.00019)


def test_deepseek_provider_uses_native_stateless_responses_contract(tmp_path: Path) -> None:
    _, plan = _source_and_plan(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == httpx.URL("https://api.deepseek.com/responses")
        assert "store" not in body
        assert body["reasoning"] == {"effort": "none"}
        assert body["text"]["format"]["type"] == "json_schema"
        assert "strict" not in body["text"]["format"]
        output = _success_payload()
        output.pop("output_text")
        output["output"] = [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "selected_role": "heading_1",
                                "selected_scope": "heading_1",
                                "confidence": 0.78,
                                "abstained": False,
                                "reason": "编号与标题候选一致。",
                                "evidence_block_ids": ["p-0000"],
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
        ]
        return httpx.Response(200, json=output)

    provider = DeepSeekResponsesProvider(
        api_key="synthetic-secret",
        model="deepseek-flash",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = run_ai_review(plan, provider)
    assert result.status == "completed"
    assert result.provider == "deepseek_responses"
    assert result.model == "deepseek-flash"


def test_runner_retries_transient_failure_without_logging_content(tmp_path: Path) -> None:
    _, plan = _source_and_plan(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"message": "synthetic"}})
        return httpx.Response(200, json=_success_payload())

    provider = OpenAIResponsesProvider(
        api_key="synthetic-secret",
        model="synthetic-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = run_ai_review(plan, provider, max_retries=1)
    assert calls == 2
    assert result.status == "completed"
    assert result.completed_count == 1 and result.failed_count == 0
    assert result.response_store_requested is False and result.raw_prompts_logged is False


def test_runner_records_failure_and_keeps_rules_only_fallback(tmp_path: Path) -> None:
    _, plan = _source_and_plan(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "must not be copied"}})

    provider = OpenAIResponsesProvider(
        api_key="synthetic-secret",
        model="synthetic-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = run_ai_review(plan, provider)
    assert result.status == "failed" and result.failed_count == 1
    assert result.rules_only_fallback_available is True
    assert "must not be copied" not in result.failures[0].message


def test_cloud_send_requires_explicit_confirmation(tmp_path: Path) -> None:
    source, _ = _source_and_plan(tmp_path)
    repo = Path(__file__).resolve().parents[2]
    plan_dir = repo / ".paperalign/test-runs/cloud-plan"
    write_ai_review_plan(source, plan_dir)
    provider = OpenAIResponsesProvider(api_key="synthetic-secret", model="synthetic-model")
    with pytest.raises(DocxAnalysisError, match="confirm"):
        write_ai_review_run(
            plan_dir / "ai_review_plan.json",
            repo / ".paperalign/test-runs/cloud-result",
            provider,
            confirmed_cloud_send=False,
        )
