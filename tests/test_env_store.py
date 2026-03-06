from pathlib import Path

from researchclaw.envs.store import EnvStore, load_envs


def test_env_store_save_get_remove(tmp_path: Path):
    store = EnvStore(file_path=str(tmp_path / "envs.json"))

    store.save({"name": "lab", "vars": {"OPENAI_API_KEY": "abc"}})

    loaded = store.get("lab")
    assert loaded is not None
    assert loaded["vars"]["OPENAI_API_KEY"] == "abc"

    store.remove("lab")
    assert store.get("lab") is None


def test_env_store_default_profile_map_api(tmp_path: Path):
    path = tmp_path / "envs.json"
    store = EnvStore(file_path=str(path))
    store.save({"name": "default", "vars": {"OPENAI_API_KEY": "abc"}})

    envs = load_envs(path=path)
    assert envs["OPENAI_API_KEY"] == "abc"


def test_env_store_default_profile_syncs_environ(monkeypatch, tmp_path: Path):
    path = tmp_path / "envs.json"
    store = EnvStore(file_path=str(path))
    monkeypatch.setenv("MY_ENV", "runtime")
    store.save({"name": "default", "vars": {"MY_ENV": "from_store"}})
    assert store.get("default")["vars"]["MY_ENV"] == "from_store"
