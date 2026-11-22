from __future__ import annotations

from pathlib import Path

from hachi.core.llm import AnthropicClient, create_llm_client


def test_create_llm_client_reads_api_key_from_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=test-dotenv-key\n",
        encoding="utf-8",
    )

    client = create_llm_client(
        {
            "kind": "anthropic",
            "model": "claude-haiku-4-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    )

    assert isinstance(client, AnthropicClient)
    assert client.api_key == "test-dotenv-key"
