from pathlib import Path

from researchclaw.envs.store import EnvStore


def test_env_store_save_get_remove(tmp_path: Path):
    store = EnvStore(file_path=str(tmp_path / "envs.json"))

    store.save({"name": "lab", "vars": {"OPENAI_API_KEY": "abc"}})

    loaded = store.get("lab")
    assert loaded is not None
    assert loaded["vars"]["OPENAI_API_KEY"] == "abc"

    store.remove("lab")
    assert store.get("lab") is None
