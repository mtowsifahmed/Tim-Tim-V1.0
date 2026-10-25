import os
from app.providers.registry import load_registry


def test_registry_loads_and_custom_gateway_reads_env(monkeypatch):
    monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "http://localhost:1234/v1/")
    monkeypatch.setenv("CUSTOM_LLM_API_KEY", "k" * 10)
    monkeypatch.setenv("CUSTOM_LLM_MODEL", "my-model")
    monkeypatch.setenv("GROQ_API_KEY", "g" * 10)
    reg = load_registry()
    assert set(reg) == {"llm", "stt", "tts", "embed"}
    custom = next(s for s in reg["llm"] if s.name == "custom")
    assert custom.configured and custom.base_url == "http://localhost:1234/v1" and custom.model == "my-model"
    assert next(s for s in reg["llm"] if s.name == "groq").configured
    assert not next(s for s in reg["llm"] if s.name == "mistral").configured   # no key set
