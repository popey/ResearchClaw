"""Skill management API routes."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import logging
from contextlib import suppress

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class SkillToggleRequest(BaseModel):
    """Request to enable or disable a skill."""

    skill_name: str


class SkillBatchDeleteRequest(BaseModel):
    """Request to delete or hide multiple skills."""

    skill_names: list[str]


class SkillInstallRequest(BaseModel):
    """Request to install a skill from hub."""

    skill_id: str = ""
    bundle_url: str | None = None
    hub_url: str | None = None
    version: str | None = None
    enable: bool = True
    overwrite: bool = False
    rewrite_paths: bool = True
    rewrite_with_model: bool = True


class SkillRepositoryImportRequest(BaseModel):
    """Request to import one or more skills from a GitHub repository."""

    repo_url: str
    ref: str | None = None
    enable: bool = True
    overwrite: bool = False
    rewrite_paths: bool = True
    rewrite_with_model: bool = True


@router.get("")
async def list_skills():
    """List all available skills."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        skills = manager.list_available_skills()
        return {"skills": skills}
    except Exception as e:
        logger.exception("Failed to list skills")
        return {"skills": [], "error": str(e)}


@router.get("/active")
async def list_active_skills():
    """List currently active (enabled) skills."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        active = manager.list_active_skills()
        return {"active_skills": active}
    except Exception as e:
        return {"active_skills": [], "error": str(e)}


@router.post("/enable")
async def enable_skill(request: SkillToggleRequest):
    """Enable a skill."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        manager.enable_skill(request.skill_name)
        return {"status": "enabled", "skill": request.skill_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_skill(request: SkillToggleRequest):
    """Disable a skill."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        manager.disable_skill(request.skill_name)
        return {"status": "disabled", "skill": request.skill_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
async def delete_skill(request: SkillToggleRequest):
    """Delete a skill or hide it if the source is builtin/project/user scoped."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        result = manager.delete_skill_result(request.skill_name)
        if not result.get("ok", False):
            raise HTTPException(
                status_code=404,
                detail=f"Skill '{request.skill_name}' not found",
            )
        return {
            "status": result.get("action", "deleted"),
            "skill": result.get("skill", request.skill_name),
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-delete")
async def batch_delete_skills(request: SkillBatchDeleteRequest):
    """Delete or hide multiple skills in one request."""
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        manager = SkillsManager()
        deleted: list[dict] = []
        not_found: list[str] = []
        seen: set[str] = set()

        for raw_name in request.skill_names:
            skill_name = str(raw_name or "").strip()
            if not skill_name or skill_name in seen:
                continue
            seen.add(skill_name)
            result = manager.delete_skill_result(skill_name)
            if result.get("ok", False):
                deleted.append(result)
            else:
                not_found.append(skill_name)

        return {
            "deleted": deleted,
            "deleted_count": len(deleted),
            "not_found": not_found,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install")
async def install_skill(request: SkillInstallRequest):
    """Install a skill from the skills hub."""
    try:
        from researchclaw.agents.skills_hub import (
            SkillsHubClient,
            install_skill_from_hub,
        )

        if request.bundle_url:
            result = install_skill_from_hub(
                bundle_url=request.bundle_url,
                version=request.version or "",
                enable=request.enable,
                overwrite=request.overwrite,
                rewrite_paths=request.rewrite_paths,
                rewrite_with_model=request.rewrite_with_model,
            )
            return {
                "status": "installed",
                "skill": result.name,
                "result": asdict(result),
            }

        client = (
            SkillsHubClient(base_url=request.hub_url)
            if request.hub_url
            else SkillsHubClient()
        )
        result = client.install(
            request.skill_id,
            version=request.version or "latest",
        )
        return {
            "status": "installed",
            "skill": request.skill_id or (result.name if result else ""),
            "result": asdict(result) if result is not None else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-repo")
async def import_skills_from_repo(request: SkillRepositoryImportRequest):
    """Import all discoverable skills from a GitHub repository."""
    try:
        from researchclaw.agents.skills_hub import install_skill_repository

        result = install_skill_repository(
            repo_url=request.repo_url,
            version=request.ref or "",
            enable=request.enable,
            overwrite=request.overwrite,
            rewrite_paths=request.rewrite_paths,
            rewrite_with_model=request.rewrite_with_model,
        )
        return {
            "status": "imported",
            "repo_url": request.repo_url,
            "result": asdict(result),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-repo/stream")
async def import_skills_from_repo_stream(request: SkillRepositoryImportRequest):
    """Stream GitHub repository skill import progress via SSE."""

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def generate():
        from researchclaw.agents.skills_hub import install_skill_repository

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def emit(event: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run_import() -> None:
            try:
                result = await asyncio.to_thread(
                    install_skill_repository,
                    repo_url=request.repo_url,
                    version=request.ref or "",
                    enable=request.enable,
                    overwrite=request.overwrite,
                    rewrite_paths=request.rewrite_paths,
                    rewrite_with_model=request.rewrite_with_model,
                    progress_callback=emit,
                )
                emit(
                    {
                        "type": "done",
                        "message": f"已导入 {result.count} 个技能",
                        "result": asdict(result),
                    },
                )
            except Exception as exc:
                emit({"type": "error", "message": str(exc)})
            finally:
                emit(None)

        producer = asyncio.create_task(run_import())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse(event)
        finally:
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/hub/search")
async def search_hub(q: str = "", tags: str = ""):
    """Search skills in the hub."""
    try:
        from researchclaw.agents.skills_hub import SkillsHubClient

        client = SkillsHubClient()
        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        )
        results = client.search(query=q, tags=tag_list)
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}
