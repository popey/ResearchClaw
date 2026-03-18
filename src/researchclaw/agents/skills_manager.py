"""Skills manager – manage the lifecycle of research skills.

Three-tier skill system:
1. **builtin** — shipped with the package under ``agents/skills/``
2. **customized** — user's working dir ``custom_skills/``
3. **active** — actual skills loaded by the agent ``active_skills/``

Key improvements over CoPaw:
- SKILL.md frontmatter parsing (name, description, emoji, requires)
- Directory tree building / comparison for efficient sync
- Path traversal protection on ``load_skill_file``
- Selective sync with ``skill_names`` filter + ``force`` flag
- ``create_skill`` with nested references/scripts tree creation
"""

from __future__ import annotations

import filecmp
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
import yaml

from ..constant import ACTIVE_SKILLS_DIR, CUSTOMIZED_SKILLS_DIR

logger = logging.getLogger(__name__)

# Built-in skills directory (shipped with the package)
_BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"
_ACTIVE_SKILL_MANIFEST = ".researchclaw-skill.json"
_PROJECT_SKILL_SUBDIRS: tuple[tuple[str, str], ...] = (
    ("skills", "project-openclaw"),
    (".agents/skills", "project-standard"),
    (".researchclaw/skills", "project-native"),
)
_USER_SKILL_DIRS: tuple[tuple[Path, str], ...] = (
    (Path.home() / ".agents" / "skills", "user-standard"),
    (Path.home() / ".researchclaw" / "skills", "user-native"),
)


# ── Models ─────────────────────────────────────────────────────────


class SkillInfo(BaseModel):
    """Information about a skill."""

    id: str
    name: str
    description: str = ""
    emoji: str = ""
    source: str = "builtin"  # "builtin", "customized", "hub"
    path: str = ""
    location: str = ""
    enabled: bool = True
    version: str = "0.1.0"
    content: str = ""  # full SKILL.md text
    references: Dict[str, Any] = Field(default_factory=dict)  # nested tree
    scripts: Dict[str, Any] = Field(default_factory=dict)  # nested tree
    requires: Dict[str, Any] = Field(default_factory=dict)
    triggers: List[str] = Field(default_factory=list)
    scope: str = "builtin"
    format: str = "legacy"
    diagnostics: List[str] = Field(default_factory=list)


# ── Frontmatter parsing ───────────────────────────────────────────


def _parse_skill_md(text: str) -> Dict[str, Any]:
    """Parse SKILL.md header lines for metadata.

    Supports simple ``- key: value`` format at the top of the file
    (compatible with CoPaw's frontmatter convention).
    """
    meta: Dict[str, Any] = {}
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        fm_lines: list[str] = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            fm_lines.append(line)
        try:
            parsed = yaml.safe_load("\n".join(fm_lines))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            logger.debug("Failed to parse YAML frontmatter", exc_info=True)

    # Bullet-style fallback:
    # - name: xxx
    # - description: yyy
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:]
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip()
            continue
        if meta:
            break
    return meta


def _normalize_trigger_values(value: Any) -> List[str]:
    """Normalize trigger metadata to a compact list of strings."""
    values: list[str] = []
    if value is None:
        return values
    if isinstance(value, str):
        values.extend([v.strip() for v in value.split(",") if v.strip()])
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                values.append(item.strip())
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.strip():
                values.append(k.strip())
            if isinstance(v, str) and v.strip():
                values.append(v.strip())
    # Keep order, remove duplicates
    deduped: list[str] = []
    seen: set[str] = set()
    for v in values:
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)
    return deduped


# ── Directory tree helpers ─────────────────────────────────────────


def _build_directory_tree(directory: Path) -> Dict[str, Any]:
    """Recursively build ``{filename: None, dirname: {nested}}`` tree."""
    tree: Dict[str, Any] = {}
    if not directory.is_dir():
        return tree
    for entry in sorted(directory.iterdir()):
        if entry.name.startswith((".", "__pycache__")):
            continue
        if entry.is_file():
            tree[entry.name] = None
        elif entry.is_dir():
            tree[entry.name] = _build_directory_tree(entry)
    return tree


def _create_files_from_tree(
    base_dir: Path,
    tree: Dict[str, Any],
    contents: Optional[Dict[str, str]] = None,
) -> None:
    """Create files/directories from a nested tree structure.

    ``contents`` maps relative path → file content (text).
    Files not in ``contents`` are created empty.
    """
    contents = contents or {}
    for name, subtree in tree.items():
        path = base_dir / name
        if subtree is None:
            # File
            rel = (
                str(path.relative_to(base_dir))
                if base_dir != path.parent
                else name
            )
            text = contents.get(rel, "")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        else:
            # Directory
            path.mkdir(parents=True, exist_ok=True)
            sub_contents = {
                k[len(name) + 1 :]: v
                for k, v in contents.items()
                if k.startswith(name + "/")
            }
            _create_files_from_tree(path, subtree, sub_contents)


def _is_directory_same(dir1: Path, dir2: Path) -> bool:
    """Recursively compare two directories for identical content."""
    if not dir1.is_dir() or not dir2.is_dir():
        return False
    cmp = filecmp.dircmp(str(dir1), str(dir2))
    return _compare_dircmp(cmp)


def _compare_dircmp(cmp: filecmp.dircmp) -> bool:  # type: ignore[type-arg]
    """Helper: check dircmp result recursively."""
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    for sub_cmp in cmp.subdirs.values():
        if not _compare_dircmp(sub_cmp):
            return False
    return True


# ── Safe path helpers ──────────────────────────────────────────────


def _safe_path_parts(rel_path: str) -> Optional[List[str]]:
    """Validate a relative path: no ``..``, no absolute, no \\."""
    if not rel_path:
        return None
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in (".", "..", "") or "/" in p or "\\" in p:
            return None
    return parts


def _iter_project_roots(start: Optional[Path] = None) -> List[Path]:
    """Return current directory and parents up to the git root/filesystem root."""
    root = (start or Path.cwd()).resolve()
    roots: List[Path] = []
    seen: set[Path] = set()
    while root not in seen:
        roots.append(root)
        seen.add(root)
        if (root / ".git").exists():
            break
        parent = root.parent
        if parent == root:
            break
        root = parent
    return roots


def _iter_skill_dirs(base_dir: Path, *, require_skill_md: bool) -> List[Path]:
    """Return valid skill directories under a root."""
    if not base_dir.is_dir():
        return []

    skill_dirs: List[Path] = []
    for skill_dir in sorted(base_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        has_skill_md = (skill_dir / "SKILL.md").is_file()
        has_entrypoint = (skill_dir / "__init__.py").is_file() or (
            skill_dir / "main.py"
        ).is_file()
        if require_skill_md and not has_skill_md:
            continue
        if not has_skill_md and not has_entrypoint:
            continue
        skill_dirs.append(skill_dir)
    return skill_dirs


def _discover_skill_sources(
    *,
    skill_names: Optional[List[str]] = None,
) -> Dict[str, tuple[Path, str, str]]:
    """Discover skills from builtin, user, and project-standard locations.

    Returns a mapping of canonical skill name -> (skill_dir, source, scope).
    Later entries override earlier ones to preserve precedence.
    """
    requested = set(skill_names or [])
    discovered: Dict[str, tuple[Path, str, str]] = {}

    def _record(skill_dir: Path, source: str, scope: str) -> None:
        if requested and skill_dir.name not in requested:
            return
        discovered[skill_dir.name] = (skill_dir, source, scope)

    if _BUILTIN_SKILLS_DIR.is_dir():
        for skill_dir in _iter_skill_dirs(
            _BUILTIN_SKILLS_DIR,
            require_skill_md=False,
        ):
            _record(skill_dir, "builtin", "builtin")

    custom_dir = Path(CUSTOMIZED_SKILLS_DIR)
    if custom_dir.is_dir():
        for skill_dir in _iter_skill_dirs(custom_dir, require_skill_md=False):
            _record(skill_dir, "customized", "user-native")

    for root_dir, scope in _USER_SKILL_DIRS:
        for skill_dir in _iter_skill_dirs(root_dir, require_skill_md=True):
            _record(skill_dir, scope, scope)

    project_roots = list(reversed(_iter_project_roots()))
    for project_root in project_roots:
        for subdir, scope in _PROJECT_SKILL_SUBDIRS:
            skill_root = project_root / subdir
            for skill_dir in _iter_skill_dirs(
                skill_root,
                require_skill_md=True,
            ):
                _record(skill_dir, scope, scope)

    return discovered


def _write_active_skill_manifest(
    skill_dir: Path,
    *,
    source_name: str,
    source_path: Path,
    scope: str,
) -> None:
    """Persist source metadata for an active skill copy."""
    payload = {
        "source": source_name,
        "scope": scope,
        "origin_path": str(source_path),
    }
    (skill_dir / _ACTIVE_SKILL_MANIFEST).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_active_skill_manifest(skill_dir: Path) -> Dict[str, Any]:
    """Read active-skill manifest metadata if present."""
    manifest_path = skill_dir / _ACTIVE_SKILL_MANIFEST
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(
            manifest_path.read_text(encoding="utf-8", errors="replace"),
        )
        if isinstance(data, dict):
            return data
    except Exception:
        logger.debug("Failed to read skill manifest: %s", manifest_path)
    return {}


def _copy_skill_to_active(
    source_dir: Path,
    dest_dir: Path,
    *,
    source_name: str,
    scope: str,
) -> None:
    """Copy a skill into active storage and record its origin metadata."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(source_dir, dest_dir)
    _write_active_skill_manifest(
        dest_dir,
        source_name=source_name,
        source_path=source_dir,
        scope=scope,
    )


def _resolve_skill_dir_by_name(
    name: str,
    *,
    source: str = "auto",
) -> Optional[tuple[str, Path, str, str]]:
    """Resolve a skill by id or display name across known sources."""
    requested = name.strip().lower()
    if not requested:
        return None

    def _matches(info: SkillInfo) -> bool:
        return info.id.lower() == requested or info.name.lower() == requested

    candidates: List[tuple[Path, str, str]] = []
    if source == "active":
        candidates = (
            [
                (
                    Path(ACTIVE_SKILLS_DIR) / child.name,
                    "active",
                    "active",
                )
                for child in sorted(Path(ACTIVE_SKILLS_DIR).iterdir())
                if child.is_dir() and not child.name.startswith((".", "_"))
            ]
            if Path(ACTIVE_SKILLS_DIR).is_dir()
            else []
        )
    elif source == "customized":
        base = Path(CUSTOMIZED_SKILLS_DIR)
        candidates = (
            [
                (child, "customized", "user-native")
                for child in sorted(base.iterdir())
            ]
            if base.is_dir()
            else []
        )
    elif source == "builtin":
        base = _BUILTIN_SKILLS_DIR
        candidates = (
            [(child, "builtin", "builtin") for child in sorted(base.iterdir())]
            if base.is_dir()
            else []
        )
    else:
        candidates = list(_discover_skill_sources().values())

    for skill_dir, source_name, scope in candidates:
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        info = _read_skill_info(skill_dir, source=source_name, scope=scope)
        if _matches(info):
            return info.id, skill_dir, source_name, scope
    return None


def _flatten_tree(tree: Dict[str, Any], prefix: str = "") -> List[str]:
    """Flatten a nested file tree into relative paths."""
    items: List[str] = []
    for name, subtree in sorted(tree.items()):
        rel = f"{prefix}/{name}" if prefix else name
        if subtree is None:
            items.append(rel)
        elif isinstance(subtree, dict):
            items.extend(_flatten_tree(subtree, rel))
    return items


def _is_disclosable_skill(info: SkillInfo) -> bool:
    """Whether a skill is valid for catalog disclosure and activation."""
    if info.format == "standard" and not info.description.strip():
        logger.warning(
            "Skipping standard skill without description: %s (%s)",
            info.name,
            info.path,
        )
        return False
    return True


# ── Core functions ─────────────────────────────────────────────────


def list_available_skills() -> List[SkillInfo]:
    """List all available skills (builtin + customised + active status)."""
    skills: Dict[str, SkillInfo] = {}
    discovered = _discover_skill_sources()
    for skill_dir, source, scope in discovered.values():
        info = _read_skill_info(skill_dir, source=source, scope=scope)
        if not _is_disclosable_skill(info):
            continue
        skills[info.id] = info

    # Mark active skills
    active_dir = Path(ACTIVE_SKILLS_DIR)
    if active_dir.is_dir():
        active_names = {
            d.name
            for d in active_dir.iterdir()
            if d.is_dir() and not d.name.startswith((".", "_"))
        }
        for skill_id in skills:
            skills[skill_id].enabled = skill_id in active_names

    return sorted(skills.values(), key=lambda s: s.name)


def list_active_skills() -> List[str]:
    """Return names of currently active (enabled) skills."""
    active_dir = Path(ACTIVE_SKILLS_DIR)
    if not active_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in active_dir.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_"))
    )


def sync_skills_to_working_dir(
    skill_names: Optional[List[str]] = None,
    force: bool = False,
) -> int:
    """Synchronise builtin and customised skills to the active directory.

    Parameters
    ----------
    skill_names:
        If provided, only sync these skills. Otherwise sync all.
    force:
        If True, overwrite even if destination already exists and is identical.

    Returns
    -------
    int
        Number of skills synced.
    """
    active_dir = Path(ACTIVE_SKILLS_DIR)
    active_dir.mkdir(parents=True, exist_ok=True)

    synced = 0

    sources = _discover_skill_sources(skill_names=skill_names)
    for name, (src, source, scope) in sources.items():
        info = _read_skill_info(src, source=source, scope=scope)
        if not _is_disclosable_skill(info):
            continue
        dest = active_dir / name
        if dest.exists() and not force:
            manifest = _read_active_skill_manifest(dest)
            if (
                _is_directory_same(src, dest)
                and manifest.get("source") == source
            ):
                continue  # skip unchanged
        _copy_skill_to_active(
            src,
            dest,
            source_name=source,
            scope=scope,
        )
        synced += 1

    logger.info("Synced %d skills to active directory", synced)
    return synced


def sync_skills_from_active_to_customized(
    skill_names: Optional[List[str]] = None,
) -> int:
    """Save modified active skills back to the customised directory.

    Skips skills whose active copy is identical to the builtin version.
    """
    active_dir = Path(ACTIVE_SKILLS_DIR)
    custom_dir = Path(CUSTOMIZED_SKILLS_DIR)
    custom_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    if not active_dir.is_dir():
        return saved

    for skill_dir in active_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        if skill_names and skill_dir.name not in skill_names:
            continue

        manifest = _read_active_skill_manifest(skill_dir)
        manifest_source = str(manifest.get("source", "")).strip().lower()
        if manifest_source and manifest_source not in {
            "builtin",
            "customized",
        }:
            continue

        # Skip if identical to builtin (no user modifications)
        builtin_src = _BUILTIN_SKILLS_DIR / skill_dir.name
        if builtin_src.is_dir() and _is_directory_same(skill_dir, builtin_src):
            continue

        dest = custom_dir / skill_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        saved += 1

    return saved


def create_skill(
    name: str,
    content: str,
    *,
    overwrite: bool = False,
    references: Optional[Dict[str, Any]] = None,
    scripts: Optional[Dict[str, Any]] = None,
    extra_files: Optional[Dict[str, str]] = None,
) -> SkillInfo:
    """Create a new skill in the customized directory.

    Parameters
    ----------
    name:
        Skill name (directory name).
    content:
        SKILL.md content (must include name + description in header).
    overwrite:
        If True, replace existing skill.
    references:
        Nested tree for ``references/`` subdirectory.
    scripts:
        Nested tree for ``scripts/`` subdirectory.
    extra_files:
        Flat ``{relative_path: file_content}`` for additional files.
    """
    custom_dir = Path(CUSTOMIZED_SKILLS_DIR)
    dest = custom_dir / name

    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Skill '{name}' already exists. Use overwrite=True to replace.",
        )

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # Write SKILL.md
    (dest / "SKILL.md").write_text(content, encoding="utf-8")

    # Create references tree
    if references:
        refs_dir = dest / "references"
        refs_dir.mkdir(exist_ok=True)
        _create_files_from_tree(refs_dir, references, extra_files)

    # Create scripts tree
    if scripts:
        scripts_dir = dest / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        _create_files_from_tree(scripts_dir, scripts, extra_files)

    # Extra files (flat paths)
    if extra_files:
        for rel_path, file_content in extra_files.items():
            parts = _safe_path_parts(rel_path)
            if not parts:
                logger.warning("Skipping unsafe path: %s", rel_path)
                continue
            fpath = dest / rel_path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(file_content, encoding="utf-8")

    # Auto-sync to active
    active_dest = Path(ACTIVE_SKILLS_DIR) / name
    if active_dest.exists():
        shutil.rmtree(active_dest)
    shutil.copytree(dest, active_dest)

    return _read_skill_info(dest, source="customized")


def load_skill_file(
    skill_name: str,
    file_path: str,
    source: str = "active",
) -> Optional[str]:
    """Load a single file from a skill directory.

    Only allows files under ``references/`` or ``scripts/`` subdirectories,
    with path traversal protection.

    Parameters
    ----------
    skill_name:
        Name of the skill.
    file_path:
        Relative path within the skill (e.g. ``references/config.md``).
    source:
        One of ``"active"``, ``"customized"``, ``"builtin"``.
    """
    parts = _safe_path_parts(file_path)
    if not parts:
        logger.warning("Invalid file path: %s", file_path)
        return None

    # Must start with references/ or scripts/ or be SKILL.md
    allowed_prefixes = ("references", "scripts")
    if parts[0] not in allowed_prefixes and file_path != "SKILL.md":
        logger.warning(
            "Path not allowed: %s (must be under %s)",
            file_path,
            allowed_prefixes,
        )
        return None

    resolved = _resolve_skill_dir_by_name(skill_name, source=source)
    if resolved is None:
        return None
    _, base, _, _ = resolved

    fpath = base / file_path
    # Resolve and verify still under base
    try:
        resolved = fpath.resolve()
        base_resolved = base.resolve()
        if not str(resolved).startswith(str(base_resolved)):
            logger.warning("Path traversal detected: %s", file_path)
            return None
    except Exception:
        return None

    if not fpath.is_file():
        return None

    return fpath.read_text(encoding="utf-8", errors="replace")


def ensure_skills_initialized() -> None:
    """Ensure the skill directories exist and are populated."""
    Path(ACTIVE_SKILLS_DIR).mkdir(parents=True, exist_ok=True)
    Path(CUSTOMIZED_SKILLS_DIR).mkdir(parents=True, exist_ok=True)
    sync_skills_to_working_dir()


def enable_skill(name: str) -> bool:
    """Enable a skill by copying it to the active directory."""
    resolved = _resolve_skill_dir_by_name(name, source="auto")
    if resolved is None:
        return False
    skill_id, source_dir, source_name, scope = resolved
    info = _read_skill_info(source_dir, source=source_name, scope=scope)
    if not _is_disclosable_skill(info):
        return False
    dest = Path(ACTIVE_SKILLS_DIR) / skill_id
    _copy_skill_to_active(
        source_dir,
        dest,
        source_name=source_name,
        scope=scope,
    )
    return True


def activate_skill(
    name: str,
    source: str = "active",
) -> Optional[Dict[str, Any]]:
    """Return standard activation payload for a skill."""
    if source not in {"active", "customized", "builtin", "auto"}:
        return None
    resolved = _resolve_skill_dir_by_name(name, source=source)
    if resolved is None:
        return None
    _, skill_dir, source_name, scope = resolved
    if source == "active":
        manifest = _read_active_skill_manifest(skill_dir)
        source_name = str(manifest.get("source") or source_name)
        scope = str(manifest.get("scope") or scope)
    skill_info = _read_skill_info(
        skill_dir,
        source=source_name,
        scope=scope,
    )

    if skill_info is None:
        return None
    if not _is_disclosable_skill(skill_info):
        return None

    skill_dir = Path(skill_info.path)
    if not skill_dir.is_dir():
        return None

    return {
        "id": skill_info.id,
        "name": skill_info.name,
        "description": skill_info.description,
        "source": skill_info.source,
        "scope": skill_info.scope,
        "path": skill_info.path,
        "location": skill_info.location,
        "format": skill_info.format,
        "diagnostics": list(skill_info.diagnostics),
        "has_entrypoint": (
            (skill_dir / "__init__.py").is_file()
            or (skill_dir / "main.py").is_file()
        ),
        "skill_md": skill_info.content,
        "references": _flatten_tree(skill_info.references),
        "scripts": _flatten_tree(skill_info.scripts),
    }


def disable_skill(name: str) -> bool:
    """Disable a skill by removing it from the active directory."""
    resolved = _resolve_skill_dir_by_name(name, source="active")
    if resolved is None:
        return False
    skill_id, _, _, _ = resolved
    dest = Path(ACTIVE_SKILLS_DIR) / skill_id
    if dest.exists():
        shutil.rmtree(dest)
        return True
    return False


def delete_skill(name: str) -> bool:
    """Permanently delete a skill from the customized directory.

    Does NOT delete builtin skills. Also removes from active if present.
    """
    resolved_custom = _resolve_skill_dir_by_name(name, source="customized")
    resolved_active = _resolve_skill_dir_by_name(name, source="active")
    custom = (
        Path(CUSTOMIZED_SKILLS_DIR) / resolved_custom[0]
        if resolved_custom is not None
        else Path(CUSTOMIZED_SKILLS_DIR) / name
    )
    active = (
        Path(ACTIVE_SKILLS_DIR) / resolved_active[0]
        if resolved_active is not None
        else Path(ACTIVE_SKILLS_DIR) / name
    )

    deleted = False
    if custom.exists():
        shutil.rmtree(custom)
        deleted = True
    if active.exists():
        shutil.rmtree(active)
        deleted = True

    return deleted


class SkillsManager:
    """Class-based interface for managing skills."""

    def list_all_skills(self) -> List[SkillInfo]:
        """List all skills (builtin + customized), syncing active→customized first."""
        sync_skills_from_active_to_customized()
        return list_available_skills()

    def list_available_skills(self) -> List[SkillInfo]:
        return list_available_skills()

    def list_active_skills(self) -> List[str]:
        return list_active_skills()

    def enable_skill(self, name: str) -> bool:
        return enable_skill(name)

    def disable_skill(self, name: str) -> bool:
        return disable_skill(name)

    def delete_skill(self, name: str) -> bool:
        return delete_skill(name)

    def create_skill(
        self,
        name: str,
        content: str,
        overwrite: bool = False,
        references: Optional[Dict[str, Any]] = None,
        scripts: Optional[Dict[str, Any]] = None,
        extra_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        info = create_skill(
            name,
            content,
            overwrite=overwrite,
            references=references,
            scripts=scripts,
            extra_files=extra_files,
        )
        return info.model_dump()

    def load_skill_file(
        self,
        skill_name: str,
        file_path: str,
        source: str = "active",
    ) -> Optional[str]:
        return load_skill_file(skill_name, file_path, source)

    def activate_skill(
        self,
        skill_name: str,
        source: str = "active",
    ) -> Optional[Dict[str, Any]]:
        return activate_skill(skill_name, source)


def _read_skill_info(
    skill_dir: Path,
    source: str = "builtin",
    scope: str = "builtin",
) -> SkillInfo:
    """Read skill metadata from its directory."""
    name = skill_dir.name
    description = ""
    emoji = ""
    content = ""
    requires: Dict[str, Any] = {}
    triggers: List[str] = []
    diagnostics: List[str] = []
    skill_format = (
        "standard" if (skill_dir / "SKILL.md").exists() else "legacy"
    )

    # Try SKILL.md first (primary metadata source)
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        meta = _parse_skill_md(content)
        description = meta.get("description", "")
        emoji = meta.get("emoji", "")
        if "requires" in meta:
            req = meta["requires"]
            if isinstance(req, dict):
                requires = req
            else:
                requires = {"raw": req}
        trigger_values: list[str] = []
        trigger_values.extend(_normalize_trigger_values(meta.get("triggers")))
        trigger_values.extend(_normalize_trigger_values(meta.get("trigger")))
        trigger_values.extend(_normalize_trigger_values(meta.get("keywords")))
        trigger_values.extend(_normalize_trigger_values(meta.get("aliases")))
        triggers = _normalize_trigger_values(trigger_values)
        # Override name from frontmatter if present
        if meta.get("name"):
            name = meta["name"]
        if not description:
            diagnostics.append("missing_description")
    else:
        diagnostics.append("missing_skill_md")

    if not description:
        readme = skill_dir / "README.md"
        if readme.exists():
            readme_text = readme.read_text(encoding="utf-8", errors="replace")
            for line in readme_text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]
                    break

    if not description:
        init_file = skill_dir / "__init__.py"
        if init_file.exists():
            init_text = init_file.read_text(encoding="utf-8", errors="replace")
            if '"""' in init_text:
                start = init_text.index('"""') + 3
                end = init_text.index('"""', start)
                description = init_text[start:end].strip()[:200]

    # Build references and scripts trees
    refs_dir = skill_dir / "references"
    scripts_dir = skill_dir / "scripts"
    references = _build_directory_tree(refs_dir) if refs_dir.is_dir() else {}
    scripts = (
        _build_directory_tree(scripts_dir) if scripts_dir.is_dir() else {}
    )

    return SkillInfo(
        id=skill_dir.name,
        name=name,
        description=description,
        emoji=emoji,
        source=source,
        path=str(skill_dir),
        location=str(skill_md.resolve()) if skill_md.exists() else "",
        content=content,
        references=references,
        scripts=scripts,
        requires=requires,
        triggers=triggers,
        scope=scope,
        format=skill_format,
        diagnostics=diagnostics,
    )
