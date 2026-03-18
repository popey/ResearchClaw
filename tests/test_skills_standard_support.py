import json
from pathlib import Path

from researchclaw.agents import skills_manager as sm


def _configure_skill_env(
    monkeypatch,
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()

    active = tmp_path / "active_skills"
    customized = tmp_path / "customized_skills"
    builtin = tmp_path / "builtin_skills"
    active.mkdir()
    customized.mkdir()
    builtin.mkdir()

    monkeypatch.chdir(project)
    monkeypatch.setattr(sm, "ACTIVE_SKILLS_DIR", str(active))
    monkeypatch.setattr(sm, "CUSTOMIZED_SKILLS_DIR", str(customized))
    monkeypatch.setattr(sm, "_BUILTIN_SKILLS_DIR", builtin)
    monkeypatch.setattr(sm, "_USER_SKILL_DIRS", ())
    return project, active, customized


def _write_standard_skill(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Demo standard skill\n"
        "triggers:\n"
        "  - demo\n"
        "---\n\n"
        "# Demo Skill\n"
        "Use this skill for testing.\n",
        encoding="utf-8",
    )
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("guide", encoding="utf-8")
    scripts = skill_dir / "scripts"
    scripts.mkdir()
    (scripts / "run.sh").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")


def test_list_available_skills_discovers_project_standard_skill(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _configure_skill_env(monkeypatch, tmp_path)
    _write_standard_skill(project / ".agents" / "skills" / "demo-skill")

    skills = sm.list_available_skills()

    assert [skill.name for skill in skills] == ["demo-skill"]
    assert skills[0].id == "demo-skill"
    assert skills[0].source == "project-standard"
    assert skills[0].scope == "project-standard"
    assert skills[0].format == "standard"
    assert skills[0].location.endswith("/SKILL.md")


def test_sync_project_standard_skill_to_active_writes_manifest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project, active, _ = _configure_skill_env(monkeypatch, tmp_path)
    _write_standard_skill(project / ".agents" / "skills" / "demo-skill")

    synced = sm.sync_skills_to_working_dir()

    assert synced == 1
    copied = active / "demo-skill"
    assert (copied / "SKILL.md").is_file()
    manifest = json.loads((copied / sm._ACTIVE_SKILL_MANIFEST).read_text())
    assert manifest["source"] == "project-standard"
    assert manifest["scope"] == "project-standard"


def test_activate_skill_returns_standard_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _configure_skill_env(monkeypatch, tmp_path)
    _write_standard_skill(project / ".agents" / "skills" / "demo-skill")
    sm.sync_skills_to_working_dir()

    payload = sm.activate_skill("demo-skill")

    assert payload is not None
    assert payload["id"] == "demo-skill"
    assert payload["name"] == "demo-skill"
    assert "Demo standard skill" in payload["skill_md"]
    assert payload["location"].endswith("/SKILL.md")
    assert payload["references"] == ["guide.md"]
    assert payload["scripts"] == ["run.sh"]
    assert payload["format"] == "standard"


def test_sync_active_to_customized_skips_external_standard_sources(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project, _, customized = _configure_skill_env(monkeypatch, tmp_path)
    _write_standard_skill(project / "skills" / "demo-skill")
    sm.sync_skills_to_working_dir()

    saved = sm.sync_skills_from_active_to_customized()

    assert saved == 0
    assert not list(customized.iterdir())


def test_enable_and_disable_skill_accept_display_name(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project, _, _ = _configure_skill_env(monkeypatch, tmp_path)
    skill_dir = project / ".agents" / "skills" / "citation_network"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: citation-network\n"
        "description: Demo citation skill\n"
        "---\n",
        encoding="utf-8",
    )

    assert sm.enable_skill("citation-network") is True
    assert "citation_network" in sm.list_active_skills()

    skills = sm.list_available_skills()
    matched = next(skill for skill in skills if skill.id == "citation_network")
    assert matched.enabled is True

    assert sm.disable_skill("citation-network") is True
    assert "citation_network" not in sm.list_active_skills()
