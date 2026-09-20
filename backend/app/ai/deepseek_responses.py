"""DeepSeek Responses API adapter using its native stateless endpoint."""

from typing import Literal

import httpx

from app.ai.openai_responses import OpenAIResponsesProvider


class DeepSeekResponsesProvider(OpenAIResponsesProvider):
    provider_name: Literal["openai_responses", "deepseek_responses"] = "deepseek_responses"
    include_store_parameter = False
    include_strict_parameter = False
    reasoning_effort = "none"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 30,
        max_output_tokens: int = 500,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            client=client,
        )
