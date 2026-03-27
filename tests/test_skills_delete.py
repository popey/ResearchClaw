from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from researchclaw.agents import skills_manager as sm
from researchclaw.app.routers import skills as skills_router


def _write_skill(skill_dir: Path, name: str, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "---\n\n"
            f"# {name}\n"
        ),
        encoding="utf-8",
    )


def test_delete_customized_skill_removes_custom_and_active(
    tmp_path,
    monkeypatch,
) -> None:
    active_dir = tmp_path / "active_skills"
    custom_dir = tmp_path / "customized_skills"
    builtin_dir = tmp_path / "builtin_skills"
    monkeypatch.setattr(sm, "ACTIVE_SKILLS_DIR", str(active_dir))
    monkeypatch.setattr(sm, "CUSTOMIZED_SKILLS_DIR", str(custom_dir))
    monkeypatch.setattr(sm, "_BUILTIN_SKILLS_DIR", builtin_dir)

    sm.create_skill(
        name="demo-skill",
        content=(
            "---\n"
            "name: demo-skill\n"
            "description: Demo custom skill\n"
            "---\n\n"
            "# Demo Skill\n"
        ),
    )

    result = sm.delete_skill_result("demo-skill")

    assert result["ok"] is True
    assert result["action"] == "deleted"
    assert not (custom_dir / "demo-skill").exists()
    assert not (active_dir / "demo-skill").exists()


def test_delete_builtin_skill_hides_from_catalog_and_active(
    tmp_path,
    monkeypatch,
) -> None:
    active_dir = tmp_path / "active_skills"
    custom_dir = tmp_path / "customized_skills"
    builtin_dir = tmp_path / "builtin_skills"
    monkeypatch.setattr(sm, "ACTIVE_SKILLS_DIR", str(active_dir))
    monkeypatch.setattr(sm, "CUSTOMIZED_SKILLS_DIR", str(custom_dir))
    monkeypatch.setattr(sm, "_BUILTIN_SKILLS_DIR", builtin_dir)

    _write_skill(builtin_dir / "builtin-demo", "builtin-demo", "Builtin demo")

    assert [skill.id for skill in sm.list_available_skills()] == ["builtin-demo"]
    assert sm.enable_skill("builtin-demo") is True
    assert (active_dir / "builtin-demo").exists()

    result = sm.delete_skill_result("builtin-demo")

    assert result["ok"] is True
    assert result["action"] == "hidden"
    assert not (active_dir / "builtin-demo").exists()
    assert sm.list_available_skills() == []

    sm.sync_skills_to_working_dir()
    assert not (active_dir / "builtin-demo").exists()


def test_skills_router_batch_delete_endpoint(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(skills_router.router, prefix="/api/skills")
    client = TestClient(app)

    class _FakeManager:
        def delete_skill_result(self, skill_name: str):
            if skill_name == "missing":
                return {"ok": False, "skill": skill_name}
            return {
                "ok": True,
                "skill": skill_name,
                "action": "deleted" if skill_name == "custom-demo" else "hidden",
            }

    monkeypatch.setattr(sm, "SkillsManager", _FakeManager)

    response = client.post(
        "/api/skills/batch-delete",
        json={
            "skill_names": [
                "custom-demo",
                "builtin-demo",
                "custom-demo",
                "missing",
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted_count"] == 2
    assert [item["skill"] for item in payload["deleted"]] == [
        "custom-demo",
        "builtin-demo",
    ]
    assert payload["not_found"] == ["missing"]
