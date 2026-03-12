"""Persisted environment variable store with process-environ sync.

Storage strategy:
1. ``envs.json`` in SECRET_DIR (canonical persisted store)
2. ``os.environ`` sync for immediate runtime availability

Backward compatibility:
- Supports legacy profile-list format used by ResearchClaw CLI/UI.
- Supports legacy flat dict format (treated as ``default`` profile vars).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_BOOTSTRAP_WORKING_DIR = (
    Path(os.environ.get("RESEARCHCLAW_WORKING_DIR", "~/.researchclaw"))
    .expanduser()
    .resolve()
)
_BOOTSTRAP_SECRET_DIR = (
    Path(
        os.environ.get(
            "RESEARCHCLAW_SECRET_DIR",
            f"{_BOOTSTRAP_WORKING_DIR}.secret",
        ),
    )
    .expanduser()
    .resolve()
)

_ENVS_JSON = _BOOTSTRAP_SECRET_DIR / "envs.json"
_LEGACY_ENVS_JSON_CANDIDATES = (
    Path(__file__).resolve().parent / "envs.json",
    _BOOTSTRAP_WORKING_DIR / "envs.json",
)
_DEFAULT_PROFILE = "default"

# Protected bootstrap keys are intentionally not injected from persisted envs.
_PROTECTED_BOOTSTRAP_KEYS = frozenset(
    {
        "RESEARCHCLAW_WORKING_DIR",
        "RESEARCHCLAW_SECRET_DIR",
    },
)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        # Some filesystems do not support POSIX chmod semantics.
        pass


def _prepare_secret_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(path.parent, 0o700)


def _resolve_store_path(
    file_path: str | None,
    *,
    default_path: Path,
) -> Path:
    return (
        Path(file_path).expanduser().resolve()
        if file_path
        else default_path
    )


def _ensure_store_parent(path: Path, *, secure: bool) -> None:
    if secure:
        _prepare_secret_parent(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)


def _load_store_json(path: Path) -> Any:
    if path.exists() and not path.is_file():
        logger.error(
            "envs.json path exists but is not a regular file: %s",
            path,
        )
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _migrate_legacy_envs_json(path: Path) -> None:
    """Copy old envs.json into secret dir once (best effort)."""
    if path.is_file():
        return
    if path.exists() and not path.is_file():
        logger.error(
            "envs.json path exists but is not a regular file: %s",
            path,
        )
        return

    for legacy in _LEGACY_ENVS_JSON_CANDIDATES:
        if not legacy.is_file() or _same_path(legacy, path):
            continue
        try:
            _prepare_secret_parent(path)
            shutil.copy2(legacy, path)
            _chmod_best_effort(path, 0o600)
            return
        except OSError as exc:
            logger.warning(
                "Failed to migrate legacy envs.json from %s: %s",
                legacy,
                exc,
            )


def get_envs_json_path() -> Path:
    """Return canonical envs.json path under SECRET_DIR."""
    return _ENVS_JSON


def _apply_to_environ(envs: dict[str, str], *, overwrite: bool = True) -> None:
    for key, value in envs.items():
        if not overwrite and key in os.environ:
            continue
        os.environ[key] = value


def _remove_from_environ(key: str) -> None:
    os.environ.pop(key, None)


def _sync_environ(old: dict[str, str], new: dict[str, str]) -> None:
    for key, old_value in old.items():
        if key not in new and os.environ.get(key) == old_value:
            _remove_from_environ(key)
    _apply_to_environ(new, overwrite=True)


def _normalize_profiles(raw: Any) -> list[dict[str, Any]]:
    """Normalize legacy/new payloads to profile-list format."""
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip() or _DEFAULT_PROFILE
            vars_map = (
                item.get("vars") if isinstance(item.get("vars"), dict) else {}
            )
            out.append(
                {
                    "name": name,
                    "vars": {str(k): str(v) for k, v in vars_map.items()},
                },
            )
        return out

    # Legacy flat dict => default profile vars.
    if isinstance(raw, dict):
        return [
            {
                "name": _DEFAULT_PROFILE,
                "vars": {str(k): str(v) for k, v in raw.items()},
            },
        ]

    return []


def _extract_default_vars(items: list[dict[str, Any]]) -> dict[str, str]:
    for item in items:
        if item.get("name") == _DEFAULT_PROFILE:
            vars_map = item.get("vars")
            if isinstance(vars_map, dict):
                return {str(k): str(v) for k, v in vars_map.items()}
    return {}


class EnvStore:
    """Stores named environment profiles in JSON."""

    def __init__(self, file_path: str | None = None):
        default_path = get_envs_json_path()
        self.file_path = _resolve_store_path(
            file_path,
            default_path=default_path,
        )
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def get(self, name: str) -> dict[str, Any] | None:
        for item in self._load():
            if item.get("name") == name:
                return item
        return None

    def save(self, profile: dict[str, Any]) -> None:
        items = self._load()
        old_default = _extract_default_vars(items)

        profile_name = str(profile.get("name", "")).strip() or _DEFAULT_PROFILE
        vars_map = (
            profile.get("vars")
            if isinstance(profile.get("vars"), dict)
            else {}
        )
        normalized = {
            "name": profile_name,
            "vars": {str(k): str(v) for k, v in vars_map.items()},
        }

        updated = False
        for idx, item in enumerate(items):
            if item.get("name") == profile_name:
                items[idx] = normalized
                updated = True
                break
        if not updated:
            items.append(normalized)

        self._save(items)

        new_default = _extract_default_vars(items)
        if profile_name == _DEFAULT_PROFILE:
            _sync_environ(old_default, new_default)

    def remove(self, name: str) -> None:
        items = self._load()
        old_default = _extract_default_vars(items)

        new_items = [item for item in items if item.get("name") != name]
        self._save(new_items)

        if name == _DEFAULT_PROFILE:
            _sync_environ(old_default, {})

    def _load(self) -> list[dict[str, Any]]:
        if self.file_path == get_envs_json_path():
            _migrate_legacy_envs_json(self.file_path)
        raw = _load_store_json(self.file_path)
        if raw is None:
            return []
        return _normalize_profiles(raw)

    def _save(self, items: list[dict[str, Any]]) -> None:
        if self.file_path.exists() and not self.file_path.is_file():
            raise IsADirectoryError(
                f"envs.json path exists but is not a regular file: {self.file_path}",
            )

        is_secure_path = self.file_path == get_envs_json_path()
        _ensure_store_parent(self.file_path, secure=is_secure_path)

        self.file_path.write_text(
            json.dumps(items, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if is_secure_path:
            _chmod_best_effort(self.file_path, 0o600)


# ------------------------------------------------------------------
# Convenience map APIs (default profile)
# ------------------------------------------------------------------


def load_envs(path: Optional[Path] = None) -> dict[str, str]:
    """Load default-profile env vars as a flat key-value mapping."""
    store = EnvStore(file_path=str(path) if path is not None else None)
    profile = store.get(_DEFAULT_PROFILE) or {
        "name": _DEFAULT_PROFILE,
        "vars": {},
    }
    vars_map = (
        profile.get("vars") if isinstance(profile.get("vars"), dict) else {}
    )
    return {str(k): str(v) for k, v in vars_map.items()}


def save_envs(envs: dict[str, str], path: Optional[Path] = None) -> None:
    """Persist default-profile env vars and sync to ``os.environ``."""
    store = EnvStore(file_path=str(path) if path is not None else None)
    store.save({"name": _DEFAULT_PROFILE, "vars": envs})


def set_env_var(key: str, value: str) -> dict[str, str]:
    """Set one env var in default profile. Returns updated mapping."""
    envs = load_envs()
    envs[key] = value
    save_envs(envs)
    return envs


def delete_env_var(key: str) -> dict[str, str]:
    """Delete one env var from default profile. Returns updated mapping."""
    envs = load_envs()
    envs.pop(key, None)
    save_envs(envs)
    return envs


def load_envs_into_environ() -> dict[str, str]:
    """Load persisted envs and inject bootstrap-safe keys into ``os.environ``.

    Existing process/system environment variables are preserved.
    """
    envs = load_envs()
    bootstrap_envs = {
        key: value
        for key, value in envs.items()
        if key not in _PROTECTED_BOOTSTRAP_KEYS
    }
    _apply_to_environ(bootstrap_envs, overwrite=False)
    return envs
