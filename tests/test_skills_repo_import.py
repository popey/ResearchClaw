from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from researchclaw.agents import skills_hub
from researchclaw.agents import skills_manager as sm
from researchclaw.app.routers import skills as skills_router


def test_install_skill_repository_rewrites_imported_paths(
    tmp_path,
    monkeypatch,
) -> None:
    active_dir = tmp_path / "active_skills"
    custom_dir = tmp_path / "customized_skills"
    monkeypatch.setattr(sm, "ACTIVE_SKILLS_DIR", str(active_dir))
    monkeypatch.setattr(sm, "CUSTOMIZED_SKILLS_DIR", str(custom_dir))

    monkeypatch.setattr(
        skills_hub,
        "_github_download_archive",
        lambda owner, repo, requested_ref: (b"fake-archive", "main"),
    )
    monkeypatch.setattr(
        skills_hub,
        "_github_archive_text_files",
        lambda archive_bytes: {
            "skills/demo-skill/SKILL.md": (
                "---\n"
                "name: demo-skill\n"
                "description: Demo imported skill\n"
                "---\n\n"
                "# Demo Skill\n\n"
                "- `docs/setup.md`\n"
                "- `tools/runner.py`\n"
            ),
            "skills/demo-skill/docs/setup.md": "See `config/default.yml` for defaults.\n",
            "skills/demo-skill/tools/runner.py": "print('hello from imported script')\n",
            "skills/demo-skill/config/default.yml": "mode: demo\n",
        },
    )

    result = skills_hub.install_skill_repository(
        repo_url="https://github.com/acme/demo-repo",
        rewrite_with_model=False,
    )

    assert result.count == 1
    assert result.imported[0].name == "demo-skill"
    assert result.imported[0].rewrite.model_used is False
    assert result.imported[0].rewrite.mirrored_files == 3

    skill_dir = custom_dir / "demo-skill"
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "references/imported/docs/setup.md" in skill_md
    assert "scripts/imported/tools/runner.py" in skill_md

    mirrored_doc = skill_dir / "references" / "imported" / "docs" / "setup.md"
    assert mirrored_doc.read_text(encoding="utf-8").strip() == (
        "See `references/imported/config/default.yml` for defaults."
    )

    assert (skill_dir / "scripts" / "imported" / "tools" / "runner.py").is_file()
    assert (skill_dir / "docs" / "setup.md").is_file()
    assert (skill_dir / "config" / "default.yml").is_file()


def test_skills_router_import_repo_endpoint(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(skills_router.router, prefix="/api/skills")
    client = TestClient(app)

    def _fake_install_skill_repository(**kwargs):
        assert kwargs["repo_url"] == "https://github.com/acme/demo-repo"
        return skills_hub.RepoInstallResult(
            repo_url=kwargs["repo_url"],
            source_url="https://github.com/acme/demo-repo",
            ref="main",
            count=1,
            imported=[
                skills_hub.RepoSkillInstallResult(
                    name="demo-skill",
                    enabled=True,
                    source_url="https://github.com/acme/demo-repo/tree/main/skills/demo-skill",
                    skill_root="skills/demo-skill",
                    rewrite=skills_hub.SkillRewriteSummary(
                        mirrored_files=2,
                        path_updates=4,
                    ),
                ),
            ],
        )

    monkeypatch.setattr(
        skills_hub,
        "install_skill_repository",
        _fake_install_skill_repository,
    )

    response = client.post(
        "/api/skills/import-repo",
        json={
            "repo_url": "https://github.com/acme/demo-repo",
            "ref": "main",
            "overwrite": True,
            "rewrite_with_model": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "imported"
    assert payload["result"]["count"] == 1
    assert payload["result"]["imported"][0]["name"] == "demo-skill"


def test_skills_router_import_repo_stream_endpoint(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(skills_router.router, prefix="/api/skills")
    client = TestClient(app)

    def _fake_install_skill_repository(**kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            progress_callback(
                {
                    "type": "start",
                    "message": "解析 GitHub 仓库地址",
                },
            )
            progress_callback(
                {
                    "type": "discovered",
                    "message": "发现 1 个 skill",
                    "count": 1,
                    "roots": ["skills/demo-skill"],
                },
            )
            progress_callback(
                {
                    "type": "skill_done",
                    "message": "已导入 demo-skill",
                    "index": 1,
                    "total": 1,
                    "skill": {
                        "name": "demo-skill",
                        "enabled": True,
                        "source_url": "https://github.com/acme/demo-repo/tree/main/skills/demo-skill",
                        "skill_root": "skills/demo-skill",
                        "rewrite": {
                            "mirrored_files": 2,
                            "path_updates": 4,
                            "model_used": False,
                            "model_name": "",
                            "diagnostics": [],
                        },
                    },
                },
            )
        return skills_hub.RepoInstallResult(
            repo_url="https://github.com/acme/demo-repo",
            source_url="https://github.com/acme/demo-repo",
            ref="main",
            count=1,
            imported=[
                skills_hub.RepoSkillInstallResult(
                    name="demo-skill",
                    enabled=True,
                    source_url="https://github.com/acme/demo-repo/tree/main/skills/demo-skill",
                    skill_root="skills/demo-skill",
                    rewrite=skills_hub.SkillRewriteSummary(
                        mirrored_files=2,
                        path_updates=4,
                    ),
                ),
            ],
        )

    monkeypatch.setattr(
        skills_hub,
        "install_skill_repository",
        _fake_install_skill_repository,
    )

    with client.stream(
        "POST",
        "/api/skills/import-repo/stream",
        json={
            "repo_url": "https://github.com/acme/demo-repo",
            "ref": "main",
            "overwrite": True,
            "rewrite_with_model": False,
        },
    ) as response:
        body = "".join(
            line.decode("utf-8") if isinstance(line, bytes) else line
            for line in response.iter_lines()
        )

    assert response.status_code == 200
    assert '"type": "start"' in body
    assert '"type": "skill_done"' in body
    assert '"type": "done"' in body
