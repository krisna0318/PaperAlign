from pathlib import Path

from app.settings import Settings


def test_optional_blank_dotenv_values_use_defaults(tmp_path: Path, monkeypatch) -> None:
    for name in (
        "PAPERALIGN_AI_INPUT_COST_PER_MILLION",
        "PAPERALIGN_AI_OUTPUT_COST_PER_MILLION",
        "PAPERALIGN_AI_API_KEY",
        "PAPERALIGN_AI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    config = tmp_path / ".env"
    config.write_text(
        "PAPERALIGN_AI_INPUT_COST_PER_MILLION=\n"
        "PAPERALIGN_AI_OUTPUT_COST_PER_MILLION=\n"
        "PAPERALIGN_AI_API_KEY=\n"
        "PAPERALIGN_AI_MODEL=\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=config)
    assert settings.ai_input_cost_per_million is None
    assert settings.ai_output_cost_per_million is None
    assert settings.ai_api_key is None
    assert settings.ai_model is None
