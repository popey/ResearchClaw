"""Skills hub client – search and install skills from the remote hub.

Multi-source skill installation support:
- **ResearchClawHub** — hosted hub API (clawhub-compatible)
- **skills.sh** — skill marketplace via GitHub repos
- **GitHub** — direct repo URLs with SKILL.md auto-discovery
- **SkillsMP** — slug-based GitHub repo resolution

Zero-dependency HTTP via ``urllib`` with exponential backoff retries.
GitHub token authentication via ``GITHUB_TOKEN`` / ``GH_TOKEN``.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse, unquote
from urllib.request import Request, urlopen
import zipfile

from .skills_manager import create_skill, enable_skill

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]


# ── Data classes ───────────────────────────────────────────────────


@dataclass
class HubSkillResult:
    """A skill found on the hub."""

    slug: str
    name: str
    description: str = ""
    version: str = ""
    source_url: str = ""


@dataclass
class HubInstallResult:
    """Result of installing a skill from the hub."""

    name: str
    enabled: bool
    source_url: str


@dataclass
class SkillRewriteSummary:
    """Summary of import-time path adaptation for an imported skill."""

    mirrored_files: int = 0
    path_updates: int = 0
    model_used: bool = False
    model_name: str = ""
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class RepoSkillInstallResult:
    """Result for one skill imported from a GitHub repository."""

    name: str
    enabled: bool
    source_url: str
    skill_root: str = ""
    rewrite: SkillRewriteSummary = field(default_factory=SkillRewriteSummary)


@dataclass
class RepoInstallResult:
    """Aggregate result for a GitHub repository import."""

    repo_url: str
    source_url: str
    ref: str
    count: int
    imported: list[RepoSkillInstallResult] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


# ── Retryable HTTP status codes ───────────────────────────────────

RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".mdx",
    ".txt",
    ".rst",
    ".adoc",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
    ".tsv",
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".r",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".swift",
    ".ipynb",
    ".sql",
    ".xml",
    ".html",
    ".css",
    ".scss",
}
_REFERENCE_EXTENSIONS = {
    ".md",
    ".markdown",
    ".mdx",
    ".txt",
    ".rst",
    ".adoc",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
    ".tsv",
    ".xml",
    ".html",
}
_SCRIPT_EXTENSIONS = {
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".r",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".swift",
    ".sql",
}
_TEXT_FILENAMES = {
    "SKILL.md",
    "README.md",
    "LICENSE",
    "Makefile",
    "Dockerfile",
}
_REFERENCE_DIR_HINTS = {
    "docs",
    "doc",
    "reference",
    "references",
    "prompt",
    "prompts",
    "examples",
    "samples",
    "templates",
    "assets",
    "config",
    "configs",
}
_SCRIPT_DIR_HINTS = {
    "bin",
    "tool",
    "tools",
    "script",
    "scripts",
    "src",
    "lib",
    "utils",
}


# ── Environment helpers ───────────────────────────────────────────


def _hub_http_timeout() -> float:
    raw = os.environ.get("RESEARCHCLAW_SKILLS_HUB_HTTP_TIMEOUT", "15")
    try:
        return max(3.0, float(raw))
    except Exception:
        return 15.0


def _hub_http_retries() -> int:
    raw = os.environ.get("RESEARCHCLAW_SKILLS_HUB_HTTP_RETRIES", "3")
    try:
        return max(0, int(raw))
    except Exception:
        return 3


def _hub_http_backoff_base() -> float:
    raw = os.environ.get("RESEARCHCLAW_SKILLS_HUB_HTTP_BACKOFF_BASE", "0.8")
    try:
        return max(0.1, float(raw))
    except Exception:
        return 0.8


def _hub_http_backoff_cap() -> float:
    raw = os.environ.get("RESEARCHCLAW_SKILLS_HUB_HTTP_BACKOFF_CAP", "6")
    try:
        return max(0.5, float(raw))
    except Exception:
        return 6.0


def _compute_backoff_seconds(attempt: int) -> float:
    base = _hub_http_backoff_base()
    cap = _hub_http_backoff_cap()
    return min(cap, base * (2 ** max(0, attempt - 1)))


def _hub_base_url() -> str:
    return os.environ.get(
        "RESEARCHCLAW_SKILLS_HUB_BASE_URL",
        "https://hub.researchclaw.com",
    )


def _hub_search_path() -> str:
    return os.environ.get(
        "RESEARCHCLAW_SKILLS_HUB_SEARCH_PATH",
        "/api/v1/search",
    )


def _hub_version_path() -> str:
    return os.environ.get(
        "RESEARCHCLAW_SKILLS_HUB_VERSION_PATH",
        "/api/v1/skills/{slug}/versions/{version}",
    )


def _hub_detail_path() -> str:
    return os.environ.get(
        "RESEARCHCLAW_SKILLS_HUB_DETAIL_PATH",
        "/api/v1/skills/{slug}",
    )


def _hub_file_path() -> str:
    return os.environ.get(
        "RESEARCHCLAW_SKILLS_HUB_FILE_PATH",
        "/api/v1/skills/{slug}/file",
    )


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


# ── Zero-dep HTTP with retries ─────────────────────────────────────


def _http_get(
    url: str,
    params: dict[str, Any] | None = None,
    accept: str = "application/json",
) -> str:
    """HTTP GET with exponential backoff, zero external dependencies."""
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    req = Request(
        full_url,
        headers={
            "Accept": accept,
            "User-Agent": "researchclaw-skills-hub/1.0",
        },
    )
    # GitHub token auth
    parsed = urlparse(full_url)
    host = (parsed.netloc or "").lower()
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token and "api.github.com" in host:
        req.add_header("Authorization", f"Bearer {github_token}")

    retries = _hub_http_retries()
    timeout = _hub_http_timeout()
    attempts = retries + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except HTTPError as e:
            last_error = e
            status = getattr(e, "code", 0) or 0
            if status == 403 and "api.github.com" in host:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                if (
                    "rate limit" in body.lower()
                    or "rate limit" in str(e).lower()
                ):
                    raise RuntimeError(
                        "GitHub API rate limit exceeded. Set GITHUB_TOKEN "
                        "(or GH_TOKEN) to increase the limit, then retry.",
                    ) from e
            if attempt < attempts and status in RETRYABLE_HTTP_STATUS:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub HTTP %s on %s (attempt %d/%d), retrying in %.2fs",
                    status,
                    full_url,
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise
        except URLError as e:
            last_error = e
            if attempt < attempts:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub URL error on %s (attempt %d/%d), retrying in %.2fs: %s",
                    full_url,
                    attempt,
                    attempts,
                    delay,
                    e,
                )
                time.sleep(delay)
                continue
            raise
        except TimeoutError as e:
            last_error = e
            if attempt < attempts:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub timeout on %s (attempt %d/%d), retrying in %.2fs",
                    full_url,
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to request hub URL: {full_url}")


def _http_bytes_get(
    url: str,
    params: dict[str, Any] | None = None,
    accept: str = "application/octet-stream, */*",
) -> bytes:
    """HTTP GET bytes with exponential backoff, zero external dependencies."""
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    req = Request(
        full_url,
        headers={
            "Accept": accept,
            "User-Agent": "researchclaw-skills-hub/1.0",
        },
    )

    retries = _hub_http_retries()
    timeout = _hub_http_timeout()
    attempts = retries + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as e:
            last_error = e
            status = getattr(e, "code", 0) or 0
            if attempt < attempts and status in RETRYABLE_HTTP_STATUS:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub HTTP %s on %s (attempt %d/%d), retrying in %.2fs",
                    status,
                    full_url,
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise
        except URLError as e:
            last_error = e
            if attempt < attempts:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub URL error on %s (attempt %d/%d), retrying in %.2fs: %s",
                    full_url,
                    attempt,
                    attempts,
                    delay,
                    e,
                )
                time.sleep(delay)
                continue
            raise
        except TimeoutError as e:
            last_error = e
            if attempt < attempts:
                delay = _compute_backoff_seconds(attempt)
                logger.warning(
                    "Hub timeout on %s (attempt %d/%d), retrying in %.2fs",
                    full_url,
                    attempt,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to request hub URL: {full_url}")


def _http_json_get(url: str, params: dict[str, Any] | None = None) -> Any:
    body = _http_get(url, params=params, accept="application/json")
    return json.loads(body)


def _http_text_get(url: str, params: dict[str, Any] | None = None) -> str:
    return _http_get(
        url,
        params=params,
        accept="text/plain, text/markdown, */*",
    )


# ── Search result normalization ────────────────────────────────────


def _norm_search_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "skills", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        if all(k in data for k in ("name", "slug")):
            return [data]
    return []


# ── Path safety ────────────────────────────────────────────────────


def _safe_path_parts(path: str) -> list[str] | None:
    if not path or path.startswith("/"):
        return None
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    for part in parts:
        if part in (".", ".."):
            return None
    return parts


# ── Tree helpers ───────────────────────────────────────────────────


def _tree_insert(tree: dict[str, Any], parts: list[str], content: str) -> None:
    node = tree
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = content


def _files_to_tree(
    files: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    references: dict[str, Any] = {}
    scripts: dict[str, Any] = {}
    for rel, content in files.items():
        if not isinstance(rel, str) or not isinstance(content, str):
            continue
        parts = _safe_path_parts(rel)
        if not parts:
            continue
        if parts[0] == "references" and len(parts) > 1:
            _tree_insert(references, parts[1:], content)
        elif parts[0] == "scripts" and len(parts) > 1:
            _tree_insert(scripts, parts[1:], content)
    return references, scripts


def _sanitize_tree(tree: Any) -> dict[str, Any]:
    if not isinstance(tree, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in tree.items():
        if not isinstance(key, str):
            continue
        if key in (".", "..") or "/" in key or "\\" in key:
            continue
        if isinstance(value, dict):
            out[key] = _sanitize_tree(value)
        elif isinstance(value, str):
            out[key] = value
    return out


# ── Bundle validation ─────────────────────────────────────────────


def _bundle_has_content(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    content = (
        payload.get("content")
        or payload.get("skill_md")
        or payload.get("skillMd")
    )
    if isinstance(content, str) and content.strip():
        return True
    files = payload.get("files")
    if isinstance(files, dict) and isinstance(files.get("SKILL.md"), str):
        return True
    return False


def _extract_version_hint(
    detail: dict[str, Any],
    requested_version: str,
) -> str:
    if requested_version:
        return requested_version
    latest = detail.get("latestVersion")
    if isinstance(latest, dict):
        ver = latest.get("version")
        if isinstance(ver, str) and ver:
            return ver
    skill = detail.get("skill")
    if isinstance(skill, dict):
        tags = skill.get("tags")
        if isinstance(tags, dict):
            latest_tag = tags.get("latest")
            if isinstance(latest_tag, str) and latest_tag:
                return latest_tag
    return ""


def _hydrate_hub_payload(
    data: Any,
    *,
    slug: str,
    requested_version: str,
) -> Any:
    """Convert hub metadata into bundle-like payload with file contents."""
    if _bundle_has_content(data):
        return data
    if not isinstance(data, dict):
        return data

    skill = data.get("skill")
    if not isinstance(skill, dict):
        return data

    skill_slug = str(skill.get("slug") or slug or "").strip()
    if not skill_slug:
        return data

    version_obj = data.get("version")
    if not isinstance(version_obj, dict) or not isinstance(
        version_obj.get("files"),
        list,
    ):
        version_hint = _extract_version_hint(data, requested_version)
        if not version_hint:
            return data
        base = _hub_base_url()
        version_url = _join_url(
            base,
            _hub_version_path().format(slug=skill_slug, version=version_hint),
        )
        version_data = _http_json_get(version_url)
        version_obj = (
            version_data.get("version")
            if isinstance(version_data, dict)
            else None
        )

    if not isinstance(version_obj, dict):
        return data
    files_meta = version_obj.get("files")
    if not isinstance(files_meta, list):
        return data

    version_str = str(
        version_obj.get("version") or requested_version or "",
    ).strip()
    base = _hub_base_url()
    file_url = _join_url(base, _hub_file_path().format(slug=skill_slug))
    files: dict[str, str] = {}
    for item in files_meta:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        params: dict[str, str] = {"path": path}
        if version_str:
            params["version"] = version_str
        try:
            files[path] = _http_text_get(file_url, params=params)
        except Exception as e:
            logger.warning("Failed to fetch hub file %s: %s", path, e)

    if not files.get("SKILL.md"):
        return data

    return {"name": skill.get("displayName") or skill_slug, "files": files}


# ── Bundle normalization ───────────────────────────────────────────


def _normalize_bundle(
    data: Any,
) -> tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Normalize a hub bundle into (name, content, references, scripts, extra_files)."""
    payload = data
    if isinstance(data, dict) and isinstance(data.get("skill"), dict):
        payload = data["skill"]
    if not isinstance(payload, dict):
        raise ValueError("Hub bundle is not a valid JSON object")

    content = (
        payload.get("content")
        or payload.get("skill_md")
        or payload.get("skillMd")
        or ""
    )
    if not isinstance(content, str):
        content = ""

    references = _sanitize_tree(payload.get("references"))
    scripts = _sanitize_tree(payload.get("scripts"))
    extra_files: dict[str, str] = {}

    # Fallback: parse from a flat files mapping
    files = payload.get("files")
    if isinstance(files, dict):
        ref2, scr2 = _files_to_tree(files)
        if not references:
            references = ref2
        if not scripts:
            scripts = scr2
        for rel, file_content in files.items():
            if not isinstance(rel, str) or not isinstance(file_content, str):
                continue
            if rel == "SKILL.md":
                continue
            parts = _safe_path_parts(rel)
            if not parts:
                continue
            if parts[0] in ("references", "scripts"):
                continue
            extra_files["/".join(parts)] = file_content
        if not content and isinstance(files.get("SKILL.md"), str):
            content = files["SKILL.md"]

    if not content:
        raise ValueError("Hub bundle missing SKILL.md content")

    name = payload.get("name", "")
    if not isinstance(name, str):
        name = ""
    if not name:
        # Try extracting from SKILL.md header
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- name:"):
                name = line[7:].strip()
                break
    if not name:
        raise ValueError("Hub bundle missing skill name")

    return name, content, references, scripts, extra_files


def _safe_fallback_name(raw: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_-]", "-", raw).strip("-_")
    return out or "imported-skill"


def _is_http_url(text: str) -> bool:
    parsed = urlparse(text.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_textual_path(rel_path: str) -> bool:
    name = Path(rel_path).name
    if name in _TEXT_FILENAMES:
        return True
    return Path(rel_path).suffix.lower() in _TEXT_EXTENSIONS


def _classify_import_path(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    parts = [part.lower() for part in Path(rel_path).parts[:-1]]
    if suffix in _SCRIPT_EXTENSIONS or any(
        part in _SCRIPT_DIR_HINTS for part in parts
    ):
        return "script"
    if suffix in _REFERENCE_EXTENSIONS or any(
        part in _REFERENCE_DIR_HINTS for part in parts
    ):
        return "reference"
    return "reference"


def _mirror_import_path(rel_path: str) -> str:
    bucket = "scripts" if _classify_import_path(rel_path) == "script" else "references"
    return f"{bucket}/imported/{rel_path.lstrip('/')}"


def _insert_tree_content(
    tree: dict[str, Any],
    rel_path: str,
    content: str,
) -> None:
    parts = _safe_path_parts(rel_path)
    if not parts:
        return
    _tree_insert(tree, parts, content)


def _path_aliases(rel_path: str) -> list[str]:
    aliases = [rel_path]
    if not rel_path.startswith("./"):
        aliases.append(f"./{rel_path}")
    return aliases


def _rewrite_text_paths(
    content: str,
    path_map: dict[str, str],
) -> tuple[str, int]:
    updated = content
    updates = 0
    ordered = sorted(path_map.items(), key=lambda item: len(item[0]), reverse=True)
    for old, new in ordered:
        if not old or old == new:
            continue
        pattern = re.compile(
            rf"(^|[^A-Za-z0-9_./-])({re.escape(old)})(?=$|[^A-Za-z0-9_./-])",
            re.MULTILINE,
        )
        updated, count = pattern.subn(lambda m: f"{m.group(1)}{new}", updated)
        updates += count
    return updated, updates


def _is_model_rewrite_candidate(rel_path: str) -> bool:
    if rel_path == "SKILL.md":
        return True
    return Path(rel_path).suffix.lower() in {
        ".md",
        ".markdown",
        ".mdx",
        ".txt",
        ".rst",
        ".adoc",
    }


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    match = re.match(r"^```[A-Za-z0-9_-]*\n(.*)\n```$", stripped, re.DOTALL)
    if match:
        return match.group(1)
    return stripped


def _load_active_provider_llm_cfg() -> dict[str, Any]:
    try:
        from researchclaw.providers.store import ProviderStore

        provider = ProviderStore().get_active_provider()
    except Exception:
        provider = None

    if provider is None:
        return {}

    data = provider.to_dict() if hasattr(provider, "to_dict") else {}
    if not isinstance(data, dict):
        return {}

    return {
        "provider": data.get("provider_type", ""),
        "provider_type": data.get("provider_type", ""),
        "model_name": data.get("model_name", ""),
        "api_key": data.get("api_key", ""),
        "api_url": data.get("base_url", ""),
    }


def _rewrite_with_active_model(
    *,
    rel_path: str,
    content: str,
    path_map: dict[str, str],
) -> tuple[str, str]:
    llm_cfg = _load_active_provider_llm_cfg()
    provider_name = str(llm_cfg.get("provider") or "").strip()
    model_name = str(llm_cfg.get("model_name") or "").strip()
    if not provider_name or not model_name:
        raise RuntimeError("No active provider/model configured for skill rewrite")

    from researchclaw.agents.model_factory import create_model_and_formatter

    model, _ = create_model_and_formatter(llm_cfg)
    mapping_lines = "\n".join(
        f"- {old} -> {new}"
        for old, new in sorted(
            path_map.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )[:80]
    )
    system_prompt = (
        "You are adapting an imported ResearchClaw skill file. "
        "Rewrite only file-path references so they match the provided mapping. "
        "Preserve markdown structure, code fences, bullets, and all non-path text. "
        "Return only the rewritten file content."
    )
    user_prompt = (
        f"File path: {rel_path}\n"
        f"Path mapping:\n{mapping_lines}\n\n"
        f"Current content:\n```text\n{content}\n```"
    )
    response = model(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    text = getattr(response, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Model rewrite returned empty content")
    return _strip_code_fences(text), model_name


def _adapt_bundle_for_researchclaw(
    *,
    content: str,
    references: dict[str, Any],
    scripts: dict[str, Any],
    extra_files: dict[str, str],
    rewrite_paths: bool,
    rewrite_with_model: bool,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, str], SkillRewriteSummary]:
    summary = SkillRewriteSummary()
    if not rewrite_paths or not extra_files:
        return content, references, scripts, extra_files, summary

    references_tree = _sanitize_tree(references)
    scripts_tree = _sanitize_tree(scripts)
    original_extra_files = dict(extra_files)
    mirror_contents: dict[str, str] = {}
    path_map: dict[str, str] = {}

    for rel_path, file_content in sorted(original_extra_files.items()):
        if not _looks_textual_path(rel_path):
            continue
        mirror_path = _mirror_import_path(rel_path)
        mirror_contents[mirror_path] = file_content
        summary.mirrored_files += 1
        for alias in _path_aliases(rel_path):
            path_map[alias] = mirror_path

    if not path_map:
        return content, references_tree, scripts_tree, original_extra_files, summary

    content, updates = _rewrite_text_paths(content, path_map)
    summary.path_updates += updates

    for rel_path in list(mirror_contents):
        rewritten, file_updates = _rewrite_text_paths(mirror_contents[rel_path], path_map)
        mirror_contents[rel_path] = rewritten
        summary.path_updates += file_updates

    def _rewrite_tree(tree: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        rewritten_tree: dict[str, Any] = {}
        for name, value in tree.items():
            rel = f"{prefix}/{name}" if prefix else name
            if isinstance(value, dict):
                rewritten_tree[name] = _rewrite_tree(value, rel)
                continue
            if isinstance(value, str):
                rewritten, count = _rewrite_text_paths(value, path_map)
                rewritten_tree[name] = rewritten
                summary.path_updates += count
            else:
                rewritten_tree[name] = value
        return rewritten_tree

    references_tree = _rewrite_tree(references_tree)
    scripts_tree = _rewrite_tree(scripts_tree)

    if rewrite_with_model:
        try:
            content, model_name = _rewrite_with_active_model(
                rel_path="SKILL.md",
                content=content,
                path_map=path_map,
            )
            summary.model_used = True
            summary.model_name = model_name
        except Exception as exc:
            summary.diagnostics.append(f"model_rewrite: {exc}")

        for rel_path in list(mirror_contents):
            if not _is_model_rewrite_candidate(rel_path):
                continue
            try:
                rewritten, model_name = _rewrite_with_active_model(
                    rel_path=rel_path,
                    content=mirror_contents[rel_path],
                    path_map=path_map,
                )
                mirror_contents[rel_path] = rewritten
                if not summary.model_name:
                    summary.model_name = model_name
                    summary.model_used = True
            except Exception as exc:
                summary.diagnostics.append(f"{rel_path}: {exc}")

    for rel_path, file_content in mirror_contents.items():
        if rel_path.startswith("references/"):
            _insert_tree_content(
                references_tree,
                rel_path[len("references/") :],
                file_content,
            )
        elif rel_path.startswith("scripts/"):
            _insert_tree_content(
                scripts_tree,
                rel_path[len("scripts/") :],
                file_content,
            )

    return content, references_tree, scripts_tree, original_extra_files, summary


# ── URL source detection ──────────────────────────────────────────


def _extract_hub_slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "researchclaw" not in host and "clawhub" not in host:
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return ""
    return parts[-1].strip()


def _extract_skills_sh_spec(url: str) -> tuple[str, str, str] | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host not in {"skills.sh", "www.skills.sh"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 3:
        return None
    owner, repo, skill = parts[0], parts[1], parts[2]
    if not owner or not repo or not skill:
        return None
    return owner, repo, skill


def _extract_skillsmp_slug(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host not in {"skillsmp.com", "www.skillsmp.com"}:
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return ""
    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 1 < len(parts):
            return parts[idx + 1].strip()
    return ""


def _extract_github_spec(url: str) -> tuple[str, str, str, str] | None:
    """Parse GitHub repo/tree/blob URL into (owner, repo, branch, path_hint)."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return None
    parts = [unquote(p) for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    branch = ""
    path_hint = ""
    if len(parts) >= 4 and parts[2] in {"tree", "blob"}:
        branch = parts[3]
        if len(parts) > 4:
            path_hint = "/".join(parts[4:])
    elif len(parts) > 2:
        path_hint = "/".join(parts[2:])
    return owner, repo, branch, path_hint


def _extract_skillsmp_spec(url: str) -> tuple[str, str, str] | None:
    """Parse SkillsMP slug into (owner, repo, skill_hint)."""
    slug = _extract_skillsmp_slug(url)
    if not slug:
        return None
    if slug.endswith("-skill-md"):
        slug = slug[: -len("-skill-md")]
    tokens = [t for t in slug.split("-") if t]
    if len(tokens) < 3:
        return None

    owner = tokens[0]
    tail_tokens = tokens[1:]
    max_split = min(len(tail_tokens), 6)
    for i in range(max_split, 0, -1):
        repo = "-".join(tail_tokens[:i]).strip()
        if not repo:
            continue
        if not _github_repo_exists(owner, repo):
            continue
        remainder = tail_tokens[i:]
        skill_hint = "-".join(remainder).strip() if remainder else ""
        return owner, repo, skill_hint

    repo = tail_tokens[0]
    skill_hint = "-".join(tail_tokens[1:]).strip()
    return owner, repo, skill_hint


# ── GitHub API helpers ─────────────────────────────────────────────


def _github_api_url(owner: str, repo: str, suffix: str) -> str:
    base = f"https://api.github.com/repos/{owner}/{repo}"
    cleaned = suffix.lstrip("/")
    return f"{base}/{cleaned}" if cleaned else base


def _github_repo_exists(owner: str, repo: str) -> bool:
    if not owner or not repo:
        return False
    try:
        data = _http_json_get(_github_api_url(owner, repo, ""))
        return isinstance(data, dict) and data.get("full_name") is not None
    except Exception:
        return False


def _github_get_default_branch(owner: str, repo: str) -> str:
    repo_meta = _http_json_get(_github_api_url(owner, repo, ""))
    if isinstance(repo_meta, dict):
        branch = repo_meta.get("default_branch")
        if isinstance(branch, str) and branch.strip():
            return branch.strip()
    return "main"


def _github_get_default_branch_via_html(owner: str, repo: str) -> str:
    repo_url = f"https://github.com/{owner}/{repo}"
    html = _http_text_get(repo_url)
    patterns = (
        r'"defaultBranch":"([^"]+)"',
        r'"defaultBranchRef"\s*:\s*\{"name":"([^"]+)"',
        r'data-default-branch="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            branch = match.group(1).strip()
            if branch:
                return branch
    return "main"


def _github_ref_candidates(
    owner: str,
    repo: str,
    requested_ref: str,
) -> list[str]:
    candidates: list[str] = []

    def _add(value: str) -> None:
        branch = value.strip()
        if branch and branch not in candidates:
            candidates.append(branch)

    _add(requested_ref)
    if not candidates:
        try:
            _add(_github_get_default_branch_via_html(owner, repo))
        except Exception:
            logger.debug(
                "Failed to discover GitHub default branch via HTML for %s/%s",
                owner,
                repo,
                exc_info=True,
            )
    _add("main")
    _add("master")
    return candidates


def _github_archive_urls(owner: str, repo: str, ref: str) -> list[str]:
    encoded = quote(ref, safe="/")
    return [
        f"https://github.com/{owner}/{repo}/archive/refs/heads/{encoded}.zip",
        f"https://github.com/{owner}/{repo}/archive/refs/tags/{encoded}.zip",
        f"https://github.com/{owner}/{repo}/archive/{encoded}.zip",
    ]


def _github_download_archive(
    owner: str,
    repo: str,
    requested_ref: str,
) -> tuple[bytes, str]:
    errors: list[str] = []
    for ref in _github_ref_candidates(owner, repo, requested_ref):
        for url in _github_archive_urls(owner, repo, ref):
            try:
                return (
                    _http_bytes_get(
                        url,
                        accept="application/zip, application/octet-stream, */*",
                    ),
                    ref,
                )
            except HTTPError as exc:
                if getattr(exc, "code", 0) == 404:
                    continue
                errors.append(f"{url}: {exc}")
            except Exception as exc:
                errors.append(f"{url}: {exc}")
    raise RuntimeError(
        "Unable to download GitHub repository archive: " + "; ".join(errors)
    )


def _decode_archive_text(blob: bytes, rel_path: str) -> str:
    if rel_path.endswith(".ipynb"):
        return blob.decode("utf-8", errors="replace")
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return blob.decode("utf-8", errors="replace")


def _github_archive_text_files(
    archive_bytes: bytes,
) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        members = [info for info in zf.infolist() if not info.is_dir()]
        top_parts = {
            info.filename.strip("/").split("/", 1)[0]
            for info in members
            if info.filename.strip("/")
        }
        prefix = next(iter(top_parts)) if len(top_parts) == 1 else ""

        files: dict[str, str] = {}
        for info in members:
            raw_name = info.filename.strip("/")
            if not raw_name:
                continue
            rel_path = raw_name
            if prefix and raw_name.startswith(prefix + "/"):
                rel_path = raw_name[len(prefix) + 1 :]
            if not rel_path or not _looks_textual_path(rel_path):
                continue
            try:
                files[rel_path] = _decode_archive_text(zf.read(info), rel_path)
            except Exception as exc:
                logger.warning("Failed to decode archive file %s: %s", rel_path, exc)
        return files


def _github_archive_skill_md_roots(files: dict[str, str]) -> list[str]:
    roots: list[str] = []
    for path in sorted(files):
        if path == "SKILL.md":
            roots.append("")
        elif path.endswith("/SKILL.md"):
            roots.append(path[: -len("/SKILL.md")])
    seen: set[str] = set()
    ordered: list[str] = []
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        ordered.append(root)
    return ordered


def _github_archive_collect_skill_files(
    files: dict[str, str],
    root: str,
) -> dict[str, str]:
    if not root:
        return dict(files)
    prefix = root.rstrip("/") + "/"
    collected: dict[str, str] = {}
    skill_md_path = prefix + "SKILL.md"
    if skill_md_path in files:
        collected["SKILL.md"] = files[skill_md_path]
    for path, content in files.items():
        if path == skill_md_path:
            continue
        if path.startswith(prefix):
            collected[path[len(prefix) :]] = content
    return collected


def _normalize_skill_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _github_list_skill_md_roots(
    owner: str,
    repo: str,
    ref: str,
) -> list[str]:
    """Find all directories containing SKILL.md in a GitHub repo."""
    tree_url = _github_api_url(owner, repo, f"git/trees/{ref}")
    data = _http_json_get(tree_url, {"recursive": "1"})
    if not isinstance(data, dict):
        return []
    tree = data.get("tree")
    if not isinstance(tree, list):
        return []
    roots: list[str] = []
    for item in tree:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str):
            continue
        if path == "SKILL.md":
            roots.append("")
        elif path.endswith("/SKILL.md"):
            roots.append(path[: -len("/SKILL.md")])
    seen: set[str] = set()
    unique: list[str] = []
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        unique.append(root)
    return unique


def _github_get_content_entry(
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> dict[str, Any]:
    content_url = _github_api_url(owner, repo, f"contents/{path}")
    data = _http_json_get(content_url, {"ref": ref})
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected GitHub response for path: {path}")
    return data


def _github_get_dir_entries(
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> list[dict[str, Any]]:
    content_url = _github_api_url(owner, repo, f"contents/{path}")
    data = _http_json_get(content_url, {"ref": ref})
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _github_read_file(entry: dict[str, Any]) -> str:
    download_url = entry.get("download_url")
    if isinstance(download_url, str) and download_url:
        return _http_text_get(download_url)
    content = entry.get("content")
    if isinstance(content, str) and content:
        try:
            normalized = content.replace("\n", "")
            return base64.b64decode(normalized).decode("utf-8")
        except Exception:
            pass
    raise ValueError("Unable to read file content from GitHub entry")


def _join_repo_path(root: str, leaf: str) -> str:
    if not root:
        return leaf
    return f"{root.rstrip('/')}/{leaf.lstrip('/')}"


def _relative_from_root(full_path: str, root: str) -> str:
    if not root:
        return full_path.lstrip("/")
    prefix = f"{root.rstrip('/')}/"
    if full_path.startswith(prefix):
        return full_path[len(prefix) :]
    return full_path


def _github_collect_tree_files(
    owner: str,
    repo: str,
    ref: str,
    root: str,
    subdir: str,
    max_files: int = 200,
) -> dict[str, str]:
    """Recursively collect files under a skill's references/ or scripts/ dir."""
    files: dict[str, str] = {}
    pending = [_join_repo_path(root, subdir)]
    visited = 0
    while pending:
        current_dir = pending.pop()
        entries = _github_get_dir_entries(owner, repo, current_dir, ref)
        for entry in entries:
            entry_type = str(entry.get("type") or "")
            entry_path = str(entry.get("path") or "")
            if not entry_path:
                continue
            if entry_type == "dir":
                pending.append(entry_path)
                continue
            if entry_type != "file":
                continue
            rel = _relative_from_root(entry_path, root)
            if not (
                rel.startswith("references/") or rel.startswith("scripts/")
            ):
                continue
            files[rel] = _github_read_file(entry)
            visited += 1
            if visited >= max_files:
                logger.warning(
                    "Hub file collection capped at %d files",
                    max_files,
                )
                return files
    return files


def _github_collect_all_files(
    owner: str,
    repo: str,
    ref: str,
    root: str,
    max_files: int = 300,
) -> dict[str, str]:
    """Recursively collect textual files under a skill root."""
    files: dict[str, str] = {}
    pending = [root]
    visited = 0
    while pending:
        current_dir = pending.pop()
        entries = _github_get_dir_entries(owner, repo, current_dir, ref)
        for entry in entries:
            entry_type = str(entry.get("type") or "")
            entry_path = str(entry.get("path") or "")
            if not entry_path:
                continue
            if entry_type == "dir":
                pending.append(entry_path)
                continue
            if entry_type != "file":
                continue
            rel = _relative_from_root(entry_path, root)
            if not _looks_textual_path(rel):
                continue
            try:
                files[rel] = _github_read_file(entry)
            except Exception as exc:
                logger.warning("Failed to fetch GitHub file %s: %s", entry_path, exc)
                continue
            visited += 1
            if visited >= max_files:
                logger.warning(
                    "GitHub skill file collection capped at %d files",
                    max_files,
                )
                return files
    return files


# ── Source-specific fetchers ───────────────────────────────────────


def _fetch_bundle_from_skills_sh_url(
    bundle_url: str,
    requested_version: str,
) -> tuple[Any, str]:
    spec = _extract_skills_sh_spec(bundle_url)
    if spec is None:
        raise ValueError("Invalid skills.sh URL format")
    owner, repo, skill = spec
    archive_bytes, branch = _github_download_archive(owner, repo, requested_version)
    archive_files = _github_archive_text_files(archive_bytes)
    roots = _github_archive_skill_md_roots(archive_files)
    selected_candidates = _filter_skill_roots_by_hint(
        roots,
        _join_repo_path("skills", skill),
    )
    if selected_candidates == roots:
        selected_candidates = _filter_skill_roots_by_hint(roots, skill)
    if not selected_candidates:
        raise ValueError(
            "Could not find SKILL.md from skills.sh source. "
            "This skill may not expose SKILL.md in the repository.",
        )
    selected_root = selected_candidates[0]
    files = _github_archive_collect_skill_files(archive_files, selected_root)
    if "SKILL.md" not in files:
        raise ValueError("Could not find SKILL.md from skills.sh source archive")

    source_url = f"https://github.com/{owner}/{repo}"
    return {"name": skill, "files": files}, source_url


def _fetch_bundle_from_repo_and_skill_hint(
    *,
    owner: str,
    repo: str,
    skill_hint: str,
    requested_version: str,
) -> tuple[Any, str]:
    skill = skill_hint.strip()
    archive_bytes, branch = _github_download_archive(owner, repo, requested_version)
    archive_files = _github_archive_text_files(archive_bytes)
    roots = _github_archive_skill_md_roots(archive_files)
    selected_candidates = (
        _filter_skill_roots_by_hint(roots, skill) if skill else roots
    )
    if not selected_candidates:
        raise ValueError("Could not find SKILL.md in source repository")
    selected_root = selected_candidates[0]
    files = _github_archive_collect_skill_files(archive_files, selected_root)
    if "SKILL.md" not in files:
        raise ValueError("Could not find SKILL.md in source repository archive")
    source_url = f"https://github.com/{owner}/{repo}"
    skill_name = skill.split("/")[-1].strip() if skill else repo
    return {"name": skill_name or repo, "files": files}, source_url


def _fetch_bundle_from_github_url(
    bundle_url: str,
    requested_version: str,
) -> tuple[Any, str]:
    spec = _extract_github_spec(bundle_url)
    if spec is None:
        raise ValueError("Invalid GitHub URL format")
    owner, repo, branch_in_url, path_hint = spec
    path_hint = path_hint.strip("/")
    if path_hint.endswith("/SKILL.md"):
        path_hint = path_hint[: -len("/SKILL.md")]
    elif path_hint == "SKILL.md":
        path_hint = ""
    branch = requested_version.strip() or branch_in_url.strip()
    return _fetch_bundle_from_repo_and_skill_hint(
        owner=owner,
        repo=repo,
        skill_hint=path_hint,
        requested_version=branch,
    )


def _fetch_bundle_from_skillsmp_url(
    bundle_url: str,
    requested_version: str,
) -> tuple[Any, str]:
    spec = _extract_skillsmp_spec(bundle_url)
    if spec is None:
        raise ValueError("Invalid SkillsMP URL format")
    owner, repo, skill_hint = spec
    return _fetch_bundle_from_repo_and_skill_hint(
        owner=owner,
        repo=repo,
        skill_hint=skill_hint,
        requested_version=requested_version,
    )


def _fetch_bundle_from_hub_slug(
    slug: str,
    version: str,
    *,
    base_url: str | None = None,
) -> tuple[Any, str]:
    if not slug:
        raise ValueError("slug is required for hub install")
    base = (base_url or "").strip() or _hub_base_url()
    candidates = [_join_url(base, _hub_detail_path().format(slug=slug))]
    errors: list[str] = []
    data: Any = None
    source_url = ""
    for candidate in candidates:
        try:
            data = _http_json_get(candidate)
            source_url = candidate
            break
        except Exception as e:
            errors.append(f"{candidate}: {e}")
    if data is None:
        raise RuntimeError(
            "Unable to fetch skill from hub endpoints: " + "; ".join(errors),
        )
    return (
        _hydrate_hub_payload(data, slug=slug, requested_version=version),
        source_url,
    )


# ── Public API ─────────────────────────────────────────────────────


def search_hub_skills(
    query: str,
    limit: int = 20,
    *,
    base_url: str | None = None,
) -> list[HubSkillResult]:
    """Search the ResearchClaw Skills Hub."""
    base = (base_url or "").strip() or _hub_base_url()
    search_url = _join_url(base, _hub_search_path())
    data = _http_json_get(search_url, {"q": query, "limit": limit})
    items = _norm_search_items(data)
    results: list[HubSkillResult] = []
    for item in items:
        slug = str(item.get("slug") or item.get("name") or "").strip()
        if not slug:
            continue
        results.append(
            HubSkillResult(
                slug=slug,
                name=str(item.get("name") or item.get("displayName") or slug),
                description=str(
                    item.get("description") or item.get("summary") or "",
                ),
                version=str(item.get("version") or ""),
                source_url=str(item.get("url") or ""),
            ),
        )
    return results


def install_skill_from_hub(
    *,
    bundle_url: str,
    version: str = "",
    enable: bool = True,
    overwrite: bool = False,
    rewrite_paths: bool = True,
    rewrite_with_model: bool = True,
) -> HubInstallResult:
    """Install a skill from any supported source URL.

    Supports: ResearchClawHub, skills.sh, GitHub direct, SkillsMP.
    """
    source_url = bundle_url
    data: Any

    if not bundle_url or not _is_http_url(bundle_url):
        raise ValueError("bundle_url must be a valid http(s) URL")

    skills_spec = _extract_skills_sh_spec(bundle_url)
    if skills_spec is not None:
        data, source_url = _fetch_bundle_from_skills_sh_url(
            bundle_url,
            requested_version=version,
        )
    else:
        github_spec = _extract_github_spec(bundle_url)
        if github_spec is not None:
            data, source_url = _fetch_bundle_from_github_url(
                bundle_url,
                requested_version=version,
            )
        else:
            skillsmp_slug = _extract_skillsmp_slug(bundle_url)
            if skillsmp_slug:
                data, source_url = _fetch_bundle_from_skillsmp_url(
                    bundle_url,
                    requested_version=version,
                )
            else:
                hub_slug = _extract_hub_slug_from_url(bundle_url)
                if hub_slug:
                    data, source_url = _fetch_bundle_from_hub_slug(
                        hub_slug,
                        version,
                    )
                else:
                    # Fallback: direct bundle JSON URL
                    data = _http_json_get(bundle_url)

    name, content, references, scripts, extra_files = _normalize_bundle(data)
    (
        content,
        references,
        scripts,
        extra_files,
        _rewrite_summary,
    ) = _adapt_bundle_for_researchclaw(
        content=content,
        references=references,
        scripts=scripts,
        extra_files=extra_files,
        rewrite_paths=rewrite_paths,
        rewrite_with_model=rewrite_with_model,
    )
    if not name:
        fallback = urlparse(bundle_url).path.strip("/").split("/")[-1]
        name = _safe_fallback_name(fallback)

    created = create_skill(
        name=name,
        content=content,
        overwrite=overwrite,
        references=references,
        scripts=scripts,
        extra_files=extra_files,
    )
    if not created:
        raise RuntimeError(
            f"Failed to create skill '{name}'. "
            "Try overwrite=true if it already exists.",
        )

    enabled = False
    if enable:
        enabled = enable_skill(name)
        if not enabled:
            logger.warning("Skill '%s' imported but enable failed", name)

    return HubInstallResult(name=name, enabled=enabled, source_url=source_url)


def _filter_skill_roots_by_hint(
    roots: list[str],
    path_hint: str,
) -> list[str]:
    hint = path_hint.strip("/")
    if not hint:
        return roots

    matches = [
        root
        for root in roots
        if root == hint
        or root.startswith(hint + "/")
        or hint.startswith(root + "/")
    ]
    if matches:
        return matches

    hint_leaf = hint.split("/")[-1].strip().lower()
    fuzzy = [
        root
        for root in roots
        if root.split("/")[-1].strip().lower() == hint_leaf
    ]
    return fuzzy or roots


def _emit_repo_import_progress(
    callback: ProgressCallback | None,
    event: dict[str, Any],
) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        logger.debug("Repo import progress callback failed", exc_info=True)


def install_skill_repository(
    *,
    repo_url: str,
    version: str = "",
    enable: bool = True,
    overwrite: bool = False,
    rewrite_paths: bool = True,
    rewrite_with_model: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> RepoInstallResult:
    """Import every discoverable skill from a GitHub repository URL."""
    _emit_repo_import_progress(
        progress_callback,
        {
            "type": "start",
            "message": "解析 GitHub 仓库地址",
            "repo_url": repo_url,
            "requested_ref": version.strip(),
        },
    )
    spec = _extract_github_spec(repo_url)
    if spec is None:
        raise ValueError("repo_url must be a valid GitHub repository URL")

    owner, repo, branch_in_url, path_hint = spec
    requested_ref = version.strip() or branch_in_url.strip()
    _emit_repo_import_progress(
        progress_callback,
        {
            "type": "stage",
            "phase": "download",
            "message": f"下载仓库归档 {owner}/{repo}",
            "repo_url": repo_url,
            "requested_ref": requested_ref,
        },
    )
    archive_bytes, ref = _github_download_archive(owner, repo, requested_ref)
    _emit_repo_import_progress(
        progress_callback,
        {
            "type": "stage",
            "phase": "scan",
            "message": "扫描仓库中的 SKILL.md",
            "repo_url": repo_url,
            "ref": ref,
        },
    )
    archive_files = _github_archive_text_files(archive_bytes)
    roots = _github_archive_skill_md_roots(archive_files)
    roots = _filter_skill_roots_by_hint(roots, path_hint)
    if not roots:
        raise ValueError("No SKILL.md files found in the repository")
    _emit_repo_import_progress(
        progress_callback,
        {
            "type": "discovered",
            "message": f"发现 {len(roots)} 个 skill",
            "count": len(roots),
            "roots": roots,
            "ref": ref,
        },
    )

    imported: list[RepoSkillInstallResult] = []
    diagnostics: list[str] = []
    source_root = f"https://github.com/{owner}/{repo}"

    for idx, root in enumerate(roots, start=1):
        skill_hint = root.split("/")[-1].strip() if root else repo
        _emit_repo_import_progress(
            progress_callback,
            {
                "type": "skill_start",
                "message": f"正在导入 {skill_hint}",
                "index": idx,
                "total": len(roots),
                "skill_root": root,
                "skill_name": skill_hint,
            },
        )
        try:
            files = _github_archive_collect_skill_files(archive_files, root)
            if "SKILL.md" not in files:
                raise ValueError("SKILL.md missing from repository archive")

            name, content, references, scripts, extra_files = _normalize_bundle(
                {
                    "name": root.split("/")[-1].strip() if root else repo,
                    "files": files,
                },
            )
            (
                content,
                references,
                scripts,
                extra_files,
                rewrite_summary,
            ) = _adapt_bundle_for_researchclaw(
                content=content,
                references=references,
                scripts=scripts,
                extra_files=extra_files,
                rewrite_paths=rewrite_paths,
                rewrite_with_model=rewrite_with_model,
            )

            create_skill(
                name=name,
                content=content,
                overwrite=overwrite,
                references=references,
                scripts=scripts,
                extra_files=extra_files,
            )
            enabled = False
            if enable:
                enabled = enable_skill(name)

            imported_skill = RepoSkillInstallResult(
                name=name,
                enabled=enabled,
                source_url=(
                    source_root
                    if not root
                    else f"{source_root}/tree/{ref}/{root}"
                ),
                skill_root=root,
                rewrite=rewrite_summary,
            )
            imported.append(imported_skill)
            _emit_repo_import_progress(
                progress_callback,
                {
                    "type": "skill_done",
                    "message": f"已导入 {name}",
                    "index": idx,
                    "total": len(roots),
                    "skill": {
                        "name": imported_skill.name,
                        "enabled": imported_skill.enabled,
                        "source_url": imported_skill.source_url,
                        "skill_root": imported_skill.skill_root,
                        "rewrite": {
                            "mirrored_files": imported_skill.rewrite.mirrored_files,
                            "path_updates": imported_skill.rewrite.path_updates,
                            "model_used": imported_skill.rewrite.model_used,
                            "model_name": imported_skill.rewrite.model_name,
                            "diagnostics": imported_skill.rewrite.diagnostics,
                        },
                    },
                },
            )
        except Exception as exc:
            root_label = root or "."
            diagnostics.append(f"{root_label}: {exc}")
            _emit_repo_import_progress(
                progress_callback,
                {
                    "type": "warning",
                    "message": f"{root_label}: {exc}",
                    "index": idx,
                    "total": len(roots),
                    "skill_root": root,
                    "skill_name": skill_hint,
                },
            )

    if not imported:
        raise RuntimeError(
            "No skills were imported from the repository. "
            + "; ".join(diagnostics)
        )

    return RepoInstallResult(
        repo_url=repo_url,
        source_url=source_root,
        ref=ref,
        count=len(imported),
        imported=imported,
        diagnostics=diagnostics,
    )


# ── Backward-compatible class interface ────────────────────────────


class SkillsHubClient:
    """Class-based interface for the skills hub (backward compatible)."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or "").strip()

    def search(
        self,
        query: str = "",
        category: str = "research",
        max_results: int = 20,
    ) -> list[HubSkillResult]:
        del category
        return search_hub_skills(
            query,
            limit=max_results,
            base_url=self.base_url or None,
        )

    def install(
        self,
        slug: str,
        version: str = "latest",
    ) -> Optional[HubInstallResult]:
        try:
            url = slug
            if not _is_http_url(slug):
                base = self.base_url or _hub_base_url()
                url = _join_url(base, f"skills/{slug}")
            return install_skill_from_hub(
                bundle_url=url,
                version=version if version != "latest" else "",
            )
        except Exception:
            logger.exception("Hub install failed for %s", slug)
            return None
