from pathlib import Path

from researchclaw.providers.store import ProviderStore


def test_provider_store_save_list_remove(tmp_path: Path):
    store = ProviderStore(file_path=str(tmp_path / "providers.json"))

    store.save_provider(
        {
            "name": "openai-main",
            "provider_type": "openai",
            "model_name": "gpt-4o",
            "model_names": ["gpt-4o"],
            "api_key": "sk-test",
            "base_url": "",
            "extra": {},
        },
    )

    items = store.list_providers()
    assert len(items) == 1
    assert items[0]["name"] == "openai-main"

    store.remove_provider("openai-main")
    assert store.list_providers() == []


def test_provider_store_ollama_base_url_normalized(tmp_path: Path):
    store = ProviderStore(file_path=str(tmp_path / "providers.json"))
    store.save_provider(
        {
            "name": "ollama-local",
            "provider_type": "ollama",
            "model_name": "llama3",
            "model_names": ["llama3"],
            "api_key": "",
            "base_url": "http://localhost:11434",
            "extra": {},
        },
    )
    item = store.get_provider("ollama-local")
    assert item is not None
    assert item.base_url == "http://localhost:11434/v1"


def test_provider_store_set_enabled_is_exclusive(tmp_path: Path):
    store = ProviderStore(file_path=str(tmp_path / "providers.json"))
    store.save_provider({"name": "a", "provider_type": "openai"})
    store.save_provider({"name": "b", "provider_type": "anthropic"})

    store.set_enabled("a")
    assert store.get_provider("a").enabled is True
    assert store.get_provider("b").enabled is False

    store.set_enabled("b")
    assert store.get_provider("a").enabled is False
    assert store.get_provider("b").enabled is True


def test_provider_store_multiple_models_round_trip(tmp_path: Path):
    store = ProviderStore(file_path=str(tmp_path / "providers.json"))

    store.save_provider(
        {
            "name": "openrouter-main",
            "provider_type": "openai",
            "model_names": ["openai/gpt-5.1", "anthropic/claude-sonnet-4"],
            "api_key": "sk-test",
            "base_url": "https://openrouter.ai/api/v1",
            "extra": {},
        },
    )

    item = store.get_provider("openrouter-main")
    assert item is not None
    assert item.model_name == "openai/gpt-5.1"
    assert item.model_names == ["openai/gpt-5.1", "anthropic/claude-sonnet-4"]


def test_provider_store_legacy_single_model_populates_model_names(
    tmp_path: Path,
):
    store = ProviderStore(file_path=str(tmp_path / "providers.json"))

    store.save_provider(
        {
            "name": "legacy-openai",
            "provider_type": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test",
        },
    )

    item = store.get_provider("legacy-openai")
    assert item is not None
    assert item.model_name == "gpt-4o"
    assert item.model_names == ["gpt-4o"]
