from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from researchclaw.research import JsonResearchStore, ResearchService


def test_research_service_workflow_notes_and_claim_graph(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Project Alpha")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Robustness study",
            goal="Validate the main robustness hypothesis.",
        )

        assert workflow.status == "running"
        assert workflow.current_stage == "literature_search"
        assert len(workflow.tasks) == 1

        workflow = await service.update_workflow_task(
            workflow_id=workflow.id,
            task_id=workflow.tasks[0].id,
            status="completed",
            summary="Core papers shortlisted.",
        )

        assert workflow.current_stage == "paper_reading"
        assert workflow.status == "running"
        assert len(workflow.tasks) == 2

        note = await service.create_note(
            project_id=project.id,
            title="Reading note",
            content="The method reports stronger robustness under shift.",
            workflow_id=workflow.id,
            note_type="paper_note",
            paper_refs=["ArXiv:2501.00001"],
            tags=["reading", "robustness"],
        )

        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The method improves robustness under distribution shift.",
            note_ids=[note.id],
        )

        evidence = await service.attach_evidence(
            project_id=project.id,
            claim_ids=[claim.id],
            evidence_type="note",
            summary="Reading note captures the robustness result.",
            source_type="note",
            source_id=note.id,
            title=note.title,
            locator="summary",
            note_id=note.id,
            workflow_id=workflow.id,
        )

        graph = await service.get_claim_graph(claim.id)
        dashboard = await service.get_project_dashboard(project.id)

        assert graph["claim"].id == claim.id
        assert [item.id for item in graph["notes"]] == [note.id]
        assert [item.id for item in graph["evidences"]] == [evidence.id]
        assert dashboard["counts"]["workflows"] == 1
        assert dashboard["counts"]["notes"] == 1
        assert dashboard["counts"]["claims"] == 1
        assert dashboard["health"]["workflows"]["running"] == 1
        assert dashboard["health"]["experiments"]["contract_passed"] == 0
        assert dashboard["health"]["remediation"]["open_tasks"] == 0

    asyncio.run(_run())


def test_research_service_dashboard_surfaces_execution_health(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(
            name="Dashboard Health Project",
            result_bundle_schemas=[
                {
                    "name": "analysis_summary.v1",
                    "required_metrics": ["accuracy"],
                    "required_outputs": ["report.json"],
                    "required_artifact_types": ["analysis"],
                },
            ],
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Dashboard health workflow",
        )
        for _ in range(5):
            current_task = workflow.tasks[-1]
            workflow = await service.update_workflow_task(
                workflow_id=workflow.id,
                task_id=current_task.id,
                status="completed",
                summary="Advance to experiment_run for dashboard health coverage.",
            )
        assert workflow.current_stage == "experiment_run"

        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="health-run",
            status="planned",
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "result_bundle_schema": "analysis_summary.v1",
            },
        )
        run = await service.update_experiment(
            experiment_id=run.id,
            status="completed",
            metrics={"accuracy": 0.91},
            output_files=["outputs/report.json"],
            metadata={
                "result_bundle_validation": {
                    "enabled": True,
                    "schema_name": "analysis_summary.v1",
                    "schema_found": True,
                    "passed": False,
                    "missing_sections": ["artifacts"],
                    "missing_metrics": [],
                    "missing_outputs": [],
                    "missing_artifact_types": ["analysis"],
                },
            },
        )
        workflow = await service.add_workflow_task(
            workflow_id=workflow.id,
            title="Resolve experiment contract blockers",
            description="Follow up on missing bundle artifacts.",
            stage="experiment_run",
            assignee="agent",
            metadata={
                "task_kind": "experiment_contract_followup",
                "contract_failure_run_ids": [run.id],
            },
        )
        followup_task = workflow.tasks[-1]
        workflow = await service.update_workflow_task(
            workflow_id=workflow.id,
            task_id=followup_task.id,
            status="blocked",
            summary="Blocked until the missing analysis artifact is published.",
        )
        workflow = await service.add_workflow_task(
            workflow_id=workflow.id,
            title="Publish missing analysis artifact",
            description="Attach the missing analysis artifact back to the experiment.",
            stage="experiment_run",
            due_at="2000-01-01T00:00:00+00:00",
            assignee="agent",
            metadata={
                "task_kind": "experiment_contract_remediation",
                "remediation_key": f"{run.id}:artifact:analysis",
                "retry_policy": {"max_attempts": 2, "backoff_minutes": 30},
            },
        )
        remediation_task = workflow.tasks[-1]
        await service.record_workflow_task_dispatch(
            workflow_id=workflow.id,
            task_id=remediation_task.id,
            summary="Remediation dispatched to the agent.",
        )
        await service.record_workflow_task_execution(
            workflow_id=workflow.id,
            task_id=remediation_task.id,
            summary="Remediation execution attempted once.",
            error="Artifact not yet available.",
        )

        dashboard = await service.get_project_dashboard(project.id)

        assert dashboard["health"]["workflows"]["blocked"] == 1
        assert dashboard["health"]["experiments"]["completed"] == 1
        assert dashboard["health"]["experiments"]["contract_failed"] == 1
        assert dashboard["health"]["experiments"]["bundle_failed"] == 1
        assert dashboard["health"]["remediation"]["open_tasks"] == 1
        assert dashboard["health"]["remediation"]["due_tasks"] == 1
        assert dashboard["health"]["remediation"]["dispatch_attempts"] == 1
        assert dashboard["health"]["remediation"]["execution_attempts"] == 1
        assert dashboard["recent_blockers"][0]["workflow_id"] == workflow.id
        assert dashboard["recent_blockers"][0]["open_remediation_tasks"] == 1
        assert dashboard["recent_blockers"][0]["actionable_tasks"][0]["task_id"] == remediation_task.id
        assert dashboard["recent_blockers"][0]["actionable_tasks"][0]["action_type"] == ""
        assert dashboard["recent_blockers"][0]["actionable_tasks"][0]["can_dispatch"] is False
        assert dashboard["recent_blockers"][0]["actionable_tasks"][0]["can_execute"] is True

    asyncio.run(_run())


def test_research_service_project_blocker_filters(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Project Blocker Filters")
        workflow_a = await service.create_workflow(
            project_id=project.id,
            title="Literature blocker workflow",
        )
        workflow_b = await service.create_workflow(
            project_id=project.id,
            title="Ready for retry workflow",
        )

        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow_b.id,
            name="retry-ready-run",
            status="completed",
            metrics={"accuracy": 0.91},
            output_files=["outputs/retry-ready.json"],
            metadata={"experiment_kind": "baseline"},
        )
        workflow_b = await service.add_workflow_task(
            workflow_id=workflow_b.id,
            title="Completed remediation task",
            description="This remediation task has already been resolved.",
            stage="experiment_run",
            assignee="agent",
            metadata={
                "task_kind": "experiment_contract_remediation",
                "experiment_id": run.id,
                "action_type": "record_metric",
                "target": "accuracy",
            },
        )
        remediation_task = workflow_b.tasks[-1]
        await service.update_workflow_task(
            workflow_id=workflow_b.id,
            task_id=remediation_task.id,
            status="completed",
            summary="Already resolved.",
        )

        state = await service.load_state()
        workflow_a_state = next(item for item in state.workflows if item.id == workflow_a.id)
        workflow_a_state.current_stage = "paper_reading"
        workflow_a_state.status = "blocked"
        workflow_a_state.error = "Literature screening is blocked."
        workflow_b_state = next(item for item in state.workflows if item.id == workflow_b.id)
        workflow_b_state.current_stage = "experiment_run"
        workflow_b_state.status = "blocked"
        workflow_b_state.error = "Experiment workflow is ready to resume."
        await service.save_state(state)

        ready_rows = await service.list_project_blockers(
            project.id,
            ready_for_retry=True,
            limit=10,
        )
        assert [item["workflow_id"] for item in ready_rows] == [workflow_b.id]
        assert ready_rows[0]["has_executable_tasks"] is False

        literature_rows = await service.list_project_blockers(
            project.id,
            query="literature",
            workflow_id=workflow_a.id,
            limit=10,
        )
        assert [item["workflow_id"] for item in literature_rows] == [workflow_a.id]
        assert literature_rows[0]["stage"] == "paper_reading"

    asyncio.run(_run())


def test_research_service_p0_state_assets_and_provenance(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )
        workdir = tmp_path / "p0-runtime"
        workdir.mkdir()
        dataset_file = workdir / "train.jsonl"
        dataset_file.write_text('{"text":"sample"}\n', encoding="utf-8")
        validation_file = workdir / "dev.jsonl"
        validation_file.write_text('{"text":"validation"}\n', encoding="utf-8")

        project = await service.create_project(name="P0 Core Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="P0 core workflow",
        )
        initial_checkpoints = await service.list_workflow_checkpoints(
            workflow_id=workflow.id,
            limit=10,
        )
        assert initial_checkpoints
        oldest_checkpoint = initial_checkpoints[-1]

        decision_note = await service.create_note(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Decision",
            content="Use the benchmark dataset v1 for the first pass.",
            note_type="decision_log",
            tags=["decision"],
        )
        memory_entries = await service.list_project_memory(project_id=project.id)
        assert any(entry.note_ids == [decision_note.id] for entry in memory_entries)
        memory_entry = await service.create_project_memory(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Benchmark decision",
            content="Track the benchmark choice at the project layer.",
            entry_kind="decision",
            stage="experiment_plan",
            tags=["benchmark"],
            metadata={"source": "service-test"},
        )
        updated_memory = await service.update_project_memory(
            project_id=project.id,
            memory_id=memory_entry.id,
            title="Benchmark dataset decision",
            content="The benchmark choice is now locked for the first experiment wave.",
            stage="experiment_run",
            tags=["benchmark", "locked"],
            metadata={"source": "console", "owner": "researcher"},
        )
        assert updated_memory.title == "Benchmark dataset decision"
        assert updated_memory.stage == "experiment_run"
        assert updated_memory.tags == ["benchmark", "locked"]
        assert updated_memory.metadata["owner"] == "researcher"

        dataset_version = await service.create_dataset_version(
            project_id=project.id,
            workflow_id=workflow.id,
            name="benchmark",
            version_label="v1",
            source_paths=[str(dataset_file)],
            split_spec={"train": "train.jsonl"},
            metadata={"primary_metric": "accuracy"},
        )
        assert Path(dataset_version.manifest_path).exists()
        original_manifest_path = Path(dataset_version.manifest_path)
        updated_dataset_version = await service.update_dataset_version(
            dataset_version_id=dataset_version.id,
            version_label="v2",
            description="Add a validation split for the revised benchmark version.",
            source_paths=[str(dataset_file), str(validation_file)],
            split_spec={
                "train": "train.jsonl",
                "validation": "dev.jsonl",
            },
            tags=["benchmark", "validated"],
            metadata={"primary_metric": "f1"},
        )
        assert updated_dataset_version.version_label == "v2"
        assert updated_dataset_version.metadata["primary_metric"] == "f1"
        assert "validation" in updated_dataset_version.split_spec
        assert str(validation_file) in updated_dataset_version.file_hashes
        assert Path(updated_dataset_version.manifest_path).exists()
        assert updated_dataset_version.manifest_path != str(original_manifest_path)
        assert not original_manifest_path.exists()
        state = await service.load_state()
        dataset_artifact = next(
            item
            for item in state.artifacts
            if item.id == updated_dataset_version.artifact_id
        )
        assert dataset_artifact.title.endswith("v2")
        assert dataset_artifact.path == updated_dataset_version.manifest_path

        paper_artifact = await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Seed paper",
            artifact_type="paper",
            source_type="semantic_scholar",
            source_id="paper-1",
        )
        synthesis_artifact = await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Synthesis",
            artifact_type="analysis",
            source_type="workflow_stage",
            source_id=f"{workflow.id}:note_synthesis",
        )
        relation = await service.create_artifact_relation(
            project_id=project.id,
            source_artifact_id=synthesis_artifact.id,
            target_artifact_id=paper_artifact.id,
            relation_type="derived_from",
            workflow_id=workflow.id,
        )
        lineage = await service.get_artifact_lineage(synthesis_artifact.id)
        assert relation.id in [item.id for item in lineage["relations"]]

        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The seed paper establishes the baseline claim.",
            artifact_ids=[paper_artifact.id],
        )
        await service.attach_evidence(
            project_id=project.id,
            claim_ids=[claim.id],
            evidence_type="paper",
            summary="The seed paper reports the baseline result directly.",
            source_type="paper",
            source_id=paper_artifact.id,
            title=paper_artifact.title,
            locator="p.1",
            artifact_id=paper_artifact.id,
            workflow_id=workflow.id,
        )
        validation = await service.validate_claim(claim.id, apply_status=True)
        updated_claim = await service.get_claim_graph(claim.id)
        assert validation["status"] == "supported"
        assert updated_claim["claim"].status == "supported"

        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="P0 provenance run",
            status="completed",
            claim_ids=[claim.id],
            dataset_version_ids=[dataset_version.id],
            metrics={"accuracy": 0.91},
            output_files=[str(dataset_file)],
            metadata={"stage": "experiment_plan"},
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "command": [sys.executable, "-V"],
                "working_dir": str(workdir),
                "environment": {"RC_FLAG": "1"},
            },
        )
        run = await service.capture_experiment_provenance(
            experiment_id=run.id,
            command=[sys.executable, "-V"],
            working_dir=str(workdir),
            environment_keys=["RC_FLAG"],
        )
        replay_plan = await service.get_experiment_replay_plan(run.id)
        assert replay_plan["command"] == [sys.executable, "-V"]
        assert replay_plan["dataset_versions"][0].id == dataset_version.id
        assert run.provenance.replayable is True

        workflow = await service.update_workflow_task(
            workflow_id=workflow.id,
            task_id=workflow.tasks[0].id,
            status="completed",
            summary="Advance once for checkpoint restore coverage.",
        )
        assert workflow.current_stage == "paper_reading"
        restored = await service.restore_workflow_checkpoint(
            workflow_id=workflow.id,
            checkpoint_id=oldest_checkpoint.id,
        )
        assert restored.current_stage == "literature_search"

        audit_events = await service.list_audit_events(
            project_id=project.id,
            limit=100,
        )
        actions = {(item.entity_type, item.action) for item in audit_events}
        assert ("memory", "update") in actions
        assert ("dataset_version", "create") in actions
        assert ("dataset_version", "update") in actions
        assert ("relation", "create") in actions
        assert ("experiment", "capture_provenance") in actions
        assert ("workflow", "restore_checkpoint") in actions

    asyncio.run(_run())


def test_research_service_memory_and_dataset_filters_and_bulk_updates(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Filtered Assets Project")
        workflow_a = await service.create_workflow(
            project_id=project.id,
            title="Workflow A",
        )
        workflow_b = await service.create_workflow(
            project_id=project.id,
            title="Workflow B",
        )

        memory_a = await service.create_project_memory(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Baseline risk",
            content="Baseline variance is still unresolved.",
            entry_kind="open_question",
            stage="paper_reading",
            status="active",
            tags=["todo", "baseline"],
        )
        memory_b = await service.create_project_memory(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Decision lock",
            content="Lock the benchmark protocol before running experiments.",
            entry_kind="decision",
            stage="experiment_plan",
            status="active",
            tags=["todo", "benchmark"],
        )
        await service.create_project_memory(
            project_id=project.id,
            workflow_id=workflow_b.id,
            title="Archived note",
            content="This issue is already resolved.",
            entry_kind="fact",
            stage="result_analysis",
            status="archived",
            tags=["done"],
        )

        filtered_memory = await service.list_project_memory(
            project_id=project.id,
            status="active",
            tag="todo",
            query="baseline",
            limit=10,
        )
        assert [item.id for item in filtered_memory] == [memory_a.id]

        bulk_memory = await service.bulk_update_project_memory(
            project_id=project.id,
            memory_ids=[memory_a.id, memory_b.id],
            status="resolved",
            workflow_id=workflow_b.id,
            add_tags=["triaged"],
            remove_tags=["todo"],
            metadata_patch={"owner": "console"},
        )
        assert bulk_memory["updated_count"] == 2

        resolved_memory = await service.list_project_memory(
            project_id=project.id,
            workflow_id=workflow_b.id,
            status="resolved",
            tag="triaged",
            limit=10,
        )
        assert {item.id for item in resolved_memory} >= {memory_a.id, memory_b.id}
        assert all("todo" not in item.tags for item in resolved_memory if item.id in {memory_a.id, memory_b.id})

        dataset_a = await service.create_dataset_version(
            project_id=project.id,
            workflow_id=workflow_a.id,
            name="benchmark",
            version_label="v1",
            description="Raw benchmark corpus.",
            tags=["raw"],
            metadata={"owner": "seed"},
        )
        dataset_b = await service.create_dataset_version(
            project_id=project.id,
            workflow_id=workflow_a.id,
            name="benchmark",
            version_label="v2",
            description="Normalized benchmark corpus.",
            parent_version_id=dataset_a.id,
            tags=["derived"],
        )
        await service.create_dataset_version(
            project_id=project.id,
            workflow_id=workflow_b.id,
            name="auxiliary",
            version_label="v1",
            description="Control dataset.",
            tags=["control"],
        )

        filtered_datasets = await service.list_dataset_versions(
            project_id=project.id,
            name_query="bench",
            tag="derived",
            parent_version_id=dataset_a.id,
            limit=10,
        )
        assert [item.id for item in filtered_datasets] == [dataset_b.id]

        bulk_datasets = await service.bulk_update_dataset_versions(
            project_id=project.id,
            dataset_version_ids=[dataset_a.id, dataset_b.id],
            workflow_id=workflow_b.id,
            add_tags=["reviewed"],
            remove_tags=["raw"],
            metadata_patch={"owner": "console"},
        )
        assert bulk_datasets["updated_count"] == 2

        updated_dataset_rows = await service.list_dataset_versions(
            project_id=project.id,
            workflow_id=workflow_b.id,
            tag="reviewed",
            name_query="bench",
            limit=10,
        )
        assert {item.id for item in updated_dataset_rows} >= {dataset_a.id, dataset_b.id}
        dataset_a_after = next(item for item in updated_dataset_rows if item.id == dataset_a.id)
        assert "raw" not in dataset_a_after.tags
        assert dataset_a_after.metadata["owner"] == "console"

    asyncio.run(_run())


def test_research_service_claim_and_artifact_filters_and_bulk_updates(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Claim Artifact Project")
        workflow_a = await service.create_workflow(
            project_id=project.id,
            title="Workflow A",
        )
        workflow_b = await service.create_workflow(
            project_id=project.id,
            title="Workflow B",
        )

        artifact_a = await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Seed paper",
            artifact_type="paper",
            source_type="semantic_scholar",
            source_id="paper-1",
        )
        artifact_b = await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Failure analysis memo",
            artifact_type="analysis",
            description="Detailed benchmark review.",
            source_type="generated",
            source_id="analysis-1",
        )
        await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow_b.id,
            title="Draft appendix",
            artifact_type="draft",
            source_type="manual",
            source_id="draft-1",
        )

        claim_a = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow_a.id,
            text="The method improves F1 on the benchmark.",
            status="draft",
            artifact_ids=[artifact_a.id],
        )
        claim_b = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow_a.id,
            text="The error analysis still needs follow-up.",
            status="needs_review",
            artifact_ids=[artifact_b.id],
        )
        await service.attach_evidence(
            project_id=project.id,
            claim_ids=[claim_a.id],
            workflow_id=workflow_a.id,
            artifact_id=artifact_a.id,
            evidence_type="paper",
            summary="Reported benchmark gains in the seed paper.",
            source_type="paper",
            source_id="paper-1",
            title="Seed paper",
            locator="p.4",
        )

        filtered_claims = await service.list_claims(
            project_id=project.id,
            status="draft",
            query="benchmark",
            has_evidence=True,
            limit=10,
        )
        assert [item.id for item in filtered_claims] == [claim_a.id]

        updated_claim = await service.update_claim(
            claim_id=claim_b.id,
            workflow_id=workflow_b.id,
            status="disputed",
            metadata={"reviewer": "console"},
        )
        assert updated_claim.workflow_id == workflow_b.id
        assert updated_claim.status == "disputed"
        assert updated_claim.metadata["reviewer"] == "console"

        bulk_claims = await service.bulk_update_claims(
            project_id=project.id,
            claim_ids=[claim_a.id, claim_b.id],
            status="supported",
            workflow_id=workflow_b.id,
            metadata_patch={"owner": "console"},
        )
        assert bulk_claims["updated_count"] == 2

        supported_claims = await service.list_claims(
            project_id=project.id,
            workflow_id=workflow_b.id,
            status="supported",
            limit=10,
        )
        assert {item.id for item in supported_claims} >= {claim_a.id, claim_b.id}
        assert all(item.metadata["owner"] == "console" for item in supported_claims)

        filtered_artifacts = await service.list_artifacts(
            project_id=project.id,
            artifact_type="analysis",
            source_type="generated",
            query="memo",
            limit=10,
        )
        assert [item.id for item in filtered_artifacts] == [artifact_b.id]

        updated_artifact = await service.update_artifact(
            artifact_id=artifact_a.id,
            workflow_id=workflow_b.id,
            source_type="cataloged",
            metadata={"owner": "console"},
        )
        assert updated_artifact.workflow_id == workflow_b.id
        assert updated_artifact.source_type == "cataloged"
        assert updated_artifact.metadata["owner"] == "console"

        bulk_artifacts = await service.bulk_update_artifacts(
            project_id=project.id,
            artifact_ids=[artifact_a.id, artifact_b.id],
            workflow_id=workflow_b.id,
            source_type="cataloged",
            metadata_patch={"reviewed": True},
        )
        assert bulk_artifacts["updated_count"] == 2

        cataloged_artifacts = await service.list_artifacts(
            project_id=project.id,
            workflow_id=workflow_b.id,
            source_type="cataloged",
            limit=10,
        )
        assert {item.id for item in cataloged_artifacts} >= {
            artifact_a.id,
            artifact_b.id,
        }
        assert all(item.metadata["reviewed"] is True for item in cataloged_artifacts)

    asyncio.run(_run())


def test_research_service_note_and_evidence_filters_and_bulk_updates(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Note Evidence Project")
        workflow_a = await service.create_workflow(
            project_id=project.id,
            title="Workflow A",
        )
        workflow_b = await service.create_workflow(
            project_id=project.id,
            title="Workflow B",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow_a.id,
            text="The benchmark improves under the new setup.",
            status="draft",
        )

        note_a = await service.create_note(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Benchmark reading",
            content="The seed paper reports benchmark gains.",
            note_type="paper_note",
            claim_ids=[claim.id],
            paper_refs=["Paper:seed-1"],
            tags=["seed", "important"],
        )
        note_b = await service.create_note(
            project_id=project.id,
            workflow_id=workflow_a.id,
            title="Run log",
            content="Need to convert this into a writing-ready note.",
            note_type="experiment_note",
            tags=["todo"],
        )

        filtered_notes = await service.list_notes(
            project_id=project.id,
            note_type="paper_note",
            tags=["seed"],
            query="benchmark",
            limit=10,
        )
        assert [item.id for item in filtered_notes] == [note_a.id]

        updated_note = await service.update_note(
            note_id=note_b.id,
            workflow_id=workflow_b.id,
            note_type="writing_note",
            tags=["draft", "todo"],
            metadata={"owner": "console"},
        )
        assert updated_note.workflow_id == workflow_b.id
        assert updated_note.note_type == "writing_note"
        assert updated_note.metadata["owner"] == "console"

        bulk_notes = await service.bulk_update_notes(
            project_id=project.id,
            note_ids=[note_a.id, note_b.id],
            workflow_id=workflow_b.id,
            note_type="writing_note",
            add_tags=["reviewed"],
            remove_tags=["todo"],
            metadata_patch={"source": "console"},
        )
        assert bulk_notes["updated_count"] == 2

        reviewed_notes = await service.list_notes(
            project_id=project.id,
            workflow_id=workflow_b.id,
            note_type="writing_note",
            tags=["reviewed"],
            limit=10,
        )
        assert {item.id for item in reviewed_notes} >= {note_a.id, note_b.id}
        assert all("todo" not in item.tags for item in reviewed_notes if item.id in {note_a.id, note_b.id})

        evidence_a = await service.attach_evidence(
            project_id=project.id,
            claim_ids=[claim.id],
            workflow_id=workflow_a.id,
            note_id=note_a.id,
            evidence_type="paper",
            summary="Benchmark gains are reported in the seed paper.",
            source_type="paper",
            source_id="paper-1",
            title="Seed paper",
            locator="p.3",
        )
        evidence_b = await service.attach_evidence(
            project_id=project.id,
            claim_ids=[claim.id],
            workflow_id=workflow_a.id,
            note_id=note_b.id,
            evidence_type="note",
            summary="Internal note captures the experimental caveat.",
            source_type="note",
            source_id=note_b.id,
            title="Run log",
        )

        filtered_evidences = await service.list_evidences(
            project_id=project.id,
            claim_id=claim.id,
            evidence_type="paper",
            source_type="paper",
            query="benchmark",
            limit=10,
        )
        assert [item.id for item in filtered_evidences] == [evidence_a.id]

        updated_evidence = await service.update_evidence(
            evidence_id=evidence_b.id,
            workflow_id=workflow_b.id,
            evidence_type="artifact",
            source_type="artifact",
            metadata={"owner": "console"},
        )
        assert updated_evidence.workflow_id == workflow_b.id
        assert updated_evidence.evidence_type == "artifact"
        assert updated_evidence.source.source_type == "artifact"
        assert updated_evidence.metadata["owner"] == "console"

        bulk_evidences = await service.bulk_update_evidences(
            project_id=project.id,
            evidence_ids=[evidence_a.id, evidence_b.id],
            workflow_id=workflow_b.id,
            evidence_type="note",
            source_type="note",
            metadata_patch={"reviewed": True},
        )
        assert bulk_evidences["updated_count"] == 2

        reviewed_evidences = await service.list_evidences(
            project_id=project.id,
            workflow_id=workflow_b.id,
            evidence_type="note",
            source_type="note",
            limit=10,
        )
        assert {item.id for item in reviewed_evidences} >= {evidence_a.id, evidence_b.id}
        assert all(item.metadata["reviewed"] is True for item in reviewed_evidences)

    asyncio.run(_run())


def test_research_service_experiment_filters_and_bulk_updates(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Experiment Control Project")
        workflow_a = await service.create_workflow(
            project_id=project.id,
            title="Workflow A",
        )
        workflow_b = await service.create_workflow(
            project_id=project.id,
            title="Workflow B",
        )
        dataset = await service.create_dataset_version(
            project_id=project.id,
            workflow_id=workflow_a.id,
            name="benchmark",
            version_label="v1",
        )

        experiment_a = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow_a.id,
            name="baseline sweep",
            status="planned",
            comparison_group="baseline",
            dataset_version_ids=[dataset.id],
        )
        experiment_b = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow_a.id,
            name="benchmark replay run",
            status="completed",
            comparison_group="ablation",
            dataset_version_ids=[dataset.id],
            metrics={"accuracy": 0.93},
            notes="benchmark contract rehearsal",
        )
        await service.configure_experiment_execution(
            experiment_id=experiment_b.id,
            patch={
                "mode": "command",
                "result_bundle_schema": "paper_bundle.v1",
            },
        )

        filtered_experiments = await service.list_experiments(
            project_id=project.id,
            status="completed",
            execution_mode="command",
            replayable=True,
            query="benchmark",
            limit=10,
        )
        assert [item.id for item in filtered_experiments] == [experiment_b.id]

        updated_experiment = await service.update_experiment(
            experiment_id=experiment_a.id,
            workflow_id=workflow_b.id,
            status="running",
            comparison_group="pilot",
            metadata={"owner": "console"},
        )
        assert updated_experiment.workflow_id == workflow_b.id
        assert updated_experiment.status == "running"
        assert updated_experiment.comparison_group == "pilot"
        assert updated_experiment.metadata["owner"] == "console"

        bulk_experiments = await service.bulk_update_experiments(
            project_id=project.id,
            experiment_ids=[experiment_a.id, experiment_b.id],
            workflow_id=workflow_b.id,
            status="completed",
            comparison_group="primary",
            metadata_patch={"reviewed": True},
        )
        assert bulk_experiments["updated_count"] == 2

        reviewed_experiments = await service.list_experiments(
            project_id=project.id,
            workflow_id=workflow_b.id,
            status="completed",
            query="primary",
            limit=10,
        )
        assert {item.id for item in reviewed_experiments} >= {
            experiment_a.id,
            experiment_b.id,
        }
        assert all(item.comparison_group == "primary" for item in reviewed_experiments)
        assert all(item.metadata["reviewed"] is True for item in reviewed_experiments)

    asyncio.run(_run())


def test_research_service_closure_action_filters_and_batch_apply(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Closure Batch Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Closure Workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The approach improves benchmark accuracy.",
            status="supported",
        )

        writing_actions = await service.list_project_closure_actions(
            project.id,
            kind="claim_writing_gap",
            workflow_id=workflow.id,
            auto_executable=True,
            limit=10,
        )
        assert [item["target_id"] for item in writing_actions] == [claim.id]

        evidence_actions = await service.list_project_closure_actions(
            project.id,
            kind="claim_evidence_gap",
            severity="high",
            query="evidence",
            limit=10,
        )
        assert [item["target_id"] for item in evidence_actions] == [claim.id]

        batch_result = await service.apply_project_closure_actions(
            project.id,
            closure_keys=[
                writing_actions[0]["closure_key"],
                evidence_actions[0]["closure_key"],
            ],
            mode="execute",
        )
        assert batch_result["executed_count"] == 1
        assert batch_result["materialized_count"] == 1
        assert batch_result["skipped_count"] == 0

        refreshed_actions = await service.list_project_closure_actions(
            project.id,
            kind="claim_writing_gap",
            limit=10,
        )
        assert refreshed_actions == []

        state = await service.load_state()
        assert any(
            task.metadata.get("closure_kind") == "claim_evidence_gap"
            for workflow_row in state.workflows
            for task in workflow_row.tasks
        )

    asyncio.run(_run())


def test_research_service_closure_report_surfaces_loop_gaps(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(
            name="Closure Report Project",
            result_bundle_schemas=[
                {
                    "name": "paper_bundle.v1",
                    "required_metrics": ["accuracy"],
                    "required_outputs": ["report.json"],
                    "required_artifact_types": ["analysis"],
                },
            ],
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Closure workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The new training recipe improves accuracy.",
            status="supported",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="closure-run",
            status="completed",
            metrics={"accuracy": 0.94},
            output_files=["report.json"],
            claim_ids=[claim.id],
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "result_bundle_schema": "paper_bundle.v1",
            },
        )

        report = await service.get_project_closure_report(project.id)

        assert report["readiness"]["overall_status"] == "blocked"
        assert report["summary"]["supported_claims"] == 1
        assert report["summary"]["contract_failed_experiments"] == 1
        assert report["summary"]["drafts"] == 0
        assert "missing_writing_artifact" in report["claim_matrix"][0]["gaps"]
        assert "artifact_contract_failed" in report["experiment_matrix"][0]["gaps"]
        assert "draft" in report["artifact_coverage"]["missing_expected_types"]
        assert any(
            item["kind"] == "claim_writing_gap"
            for item in report["action_items"]
        )
        assert any(
            item["kind"] == "experiment_contract"
            for item in report["action_items"]
        )

    asyncio.run(_run())


def test_research_service_executes_closure_actions_and_packages_project(
    tmp_path,
) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research" / "state.json"),
        )

        project = await service.create_project(
            name="Closure Automation Project",
            result_bundle_schemas=[
                {
                    "name": "paper_bundle.v1",
                    "required_metrics": ["accuracy"],
                    "required_artifact_types": ["analysis"],
                },
            ],
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Automation workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The approach improves accuracy.",
            status="supported",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="automation-run",
            status="completed",
            metrics={"accuracy": 0.95},
            claim_ids=[claim.id],
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "result_bundle_schema": "paper_bundle.v1",
            },
        )

        execute_result = await service.execute_project_closure_action(
            project.id,
            action_kind="claim_writing_gap",
            target_id=claim.id,
        )
        materialized = await service.materialize_project_closure_actions(
            project.id,
            limit=3,
        )
        package_result = await service.create_project_submission_package(project.id)
        closure = await service.get_project_closure_report(project.id)

        assert execute_result["executed"] is True
        assert Path(execute_result["written_path"]).exists()
        assert closure["summary"]["analysis_artifacts"] >= 1
        assert materialized["created_count"] >= 1
        assert Path(package_result["archive_path"]).exists()
        assert Path(package_result["manifest_path"]).exists()
        assert package_result["included_file_count"] >= 1

    asyncio.run(_run())


def test_research_service_experiments_and_proactive_reminders(
    tmp_path,
    monkeypatch,
) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Project Beta")
        await service.add_project_paper_watch(
            project_id=project.id,
            query="distribution shift robustness",
            max_results=5,
            check_every_hours=1,
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Long-running workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="Ablation confirms the contribution of the regularizer.",
        )

        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="ablation-1",
            status="completed",
            parameters={"lr": 0.001},
            metrics={"accuracy": 0.91, "f1": 0.88},
            output_files=["results.csv", "figure.png"],
            claim_ids=[claim.id],
        )

        compare = await service.compare_experiments([run.id])
        graph = await service.get_claim_graph(claim.id)

        assert compare["runs"][0]["metrics"]["accuracy"] == 0.91
        assert len(run.artifact_ids) == 2
        assert any(item.experiment_id == run.id for item in graph["evidences"])
        assert any(item.id == run.id for item in graph["experiments"])

        state = await service.load_state()
        state.workflows[0].last_run_at = "2000-01-01T00:00:00+00:00"
        await service.save_state(state)

        monkeypatch.setattr(
            service,
            "_search_papers",
            lambda **_: [
                {"title": "Paper A", "arxiv_id": "2501.00001"},
                {"title": "Paper B", "arxiv_id": "2501.00002"},
            ],
        )

        reminders = await service.generate_proactive_reminders(stale_hours=1)
        reminder_types = {item.reminder_type for item in reminders}

        assert "workflow_timeout" in reminder_types
        assert "experiment_complete" in reminder_types
        assert "new_paper_tracking" in reminder_types

    asyncio.run(_run())


def test_research_service_execution_policy_updates(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Policy Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Policy workflow",
        )

        workflow = await service.update_workflow_execution_policy(
            workflow_id=workflow.id,
            patch={
                "enabled": True,
                "mode": "stale_or_blocked",
                "stale_hours": 6,
                "cooldown_minutes": 30,
                "max_auto_runs_per_day": 3,
                "allowed_stages": ["literature_search", "paper_reading"],
                "notify_after_execution": False,
            },
        )

        assert workflow.execution_policy.enabled is True
        assert workflow.execution_policy.mode == "stale_or_blocked"
        assert workflow.execution_policy.stale_hours == 6
        assert workflow.execution_policy.cooldown_minutes == 30
        assert workflow.execution_policy.max_auto_runs_per_day == 3
        assert workflow.execution_policy.allowed_stages == [
            "literature_search",
            "paper_reading",
        ]
        assert workflow.execution_policy.notify_after_execution is False

    asyncio.run(_run())


def test_research_service_note_artifact_linking(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Artifact Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Artifact workflow",
        )
        artifact = await service.upsert_artifact(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Sample paper",
            artifact_type="paper",
            source_type="semantic_scholar",
            source_id="paper-1",
            metadata={"abstract": "A useful paper."},
        )
        note = await service.create_note(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Paper note",
            content="This note is linked to the paper artifact.",
            note_type="paper_note",
            artifact_ids=[artifact.id],
            paper_refs=["SemanticScholar:paper-1"],
        )

        artifacts = await service.list_artifacts(
            project_id=project.id,
            workflow_id=workflow.id,
            artifact_type="paper",
        )

        assert artifacts[0].id == artifact.id
        assert note.id in artifacts[0].note_ids
        assert artifact.id in note.artifact_ids

    asyncio.run(_run())


def test_research_service_updates_claims_and_experiments(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Mutable Research Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Mutable workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The ablation should weaken robustness under shift.",
        )
        note = await service.create_note(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Experiment observation",
            content="The completed run weakens robust accuracy.",
            note_type="experiment_note",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="ablation-plan",
            status="planned",
            claim_ids=[claim.id],
            metadata={"experiment_kind": "ablation"},
        )

        run = await service.update_experiment(
            experiment_id=run.id,
            status="completed",
            metrics={"accuracy": 0.77, "robust_accuracy": 0.68},
            notes="Completed by the structured worker.",
            output_files=["runs/ablation-metrics.json", "runs/ablation-curve.png"],
            note_ids=[note.id],
            metadata={"stage": "experiment_run"},
        )
        claim = await service.update_claim(
            claim_id=claim.id,
            status="supported",
            confidence=0.83,
            note_ids=[note.id],
            artifact_ids=run.artifact_ids,
            metadata={"stage": "result_analysis"},
        )
        graph = await service.get_claim_graph(claim.id)

        assert run.status == "completed"
        assert note.id in run.note_ids
        assert len(run.artifact_ids) == 2
        assert claim.status == "supported"
        assert claim.confidence == 0.83
        assert note.id in claim.note_ids
        assert any(item.experiment_id == run.id for item in graph["evidences"])
        assert any(item.id == run.id for item in graph["experiments"])
        assert any(item.id in run.artifact_ids for item in graph["artifacts"])

    asyncio.run(_run())


def test_research_service_external_experiment_execution_timeline(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="External Execution Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="External execution workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The external run should write results back into the graph.",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="external-run",
            status="planned",
            claim_ids=[claim.id],
        )

        configured = await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "external",
                "external_run_id": "job-123",
                "requested_by": "ci",
                "instructions": "Report heartbeats every few minutes.",
            },
        )
        heartbeat = await service.record_experiment_heartbeat(
            experiment_id=run.id,
            summary="The external run has started.",
            metrics={"step": 10},
        )
        result = await service.record_experiment_result(
            experiment_id=run.id,
            summary="The external run completed successfully.",
            status="completed",
            metrics={"accuracy": 0.92, "robust_accuracy": 0.88},
            output_files=["outputs/external-metrics.json"],
            notes="External executor uploaded the final metrics.",
        )
        events = await service.list_experiment_events(
            experiment_id=run.id,
            limit=10,
        )

        assert configured["experiment"].execution.mode == "external"
        assert configured["event"].event_type == "binding"
        assert heartbeat["experiment"].status == "running"
        assert heartbeat["event"].event_type == "heartbeat"
        assert result["experiment"].status == "completed"
        assert result["event"].event_type == "completion"
        assert result["experiment"].execution.last_heartbeat_at is not None
        assert result["experiment"].artifact_ids
        assert [item.event_type for item in events[:3]] == [
            "completion",
            "heartbeat",
            "binding",
        ]

    asyncio.run(_run())


def test_research_service_runner_profiles_seed_workflow_defaults(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(
            name="Runner Profile Project",
            execution_catalog=[
                {
                    "name": "local-benchmark",
                    "template": {
                        "mode": "command",
                        "command": ["python", "scripts/run.py", "--kind", "{experiment_kind}"],
                        "working_dir": "{output_dir}",
                        "environment": {
                            "RC_EXPERIMENT_KIND": "{experiment_kind}",
                        },
                        "parameter_overrides": {
                            "dataset": "{experiment_kind}_suite",
                        },
                        "input_data_overrides": {
                            "planned_stage": "{current_stage}",
                        },
                        "metadata": {
                            "metrics_file": "metrics.json",
                            "output_files": ["metrics.json"],
                        },
                    },
                    "artifact_contract": {
                        "required_metrics": ["accuracy", "robust_accuracy"],
                    },
                },
            ],
            default_experiment_runner={
                "enabled": True,
                "default": {
                    "catalog_entry": "local-benchmark",
                },
                "kind_overrides": {
                    "ablation": {
                        "instructions": "Use the ablation-specific command profile.",
                    },
                },
            },
        )
        project = await service.update_project(
            project_id=project.id,
            execution_catalog=[
                *[item.model_dump(mode="json") for item in project.execution_catalog],
                {
                    "name": "remote-stress",
                    "template": {
                        "mode": "external",
                        "instructions": "Dispatch stress tests to the remote queue.",
                    },
                    "artifact_contract": {
                        "required_outputs": ["stress-report.json"],
                    },
                },
            ],
            default_experiment_runner={
                "kind_overrides": {
                    "stress_test": {
                        "catalog_entry": "remote-stress",
                    },
                },
                "rules": [
                    {
                        "name": "failure-mode-remote",
                        "stages": ["experiment_plan"],
                        "hypothesis_kinds": ["failure_mode_probe"],
                        "template": {
                            "environment": {
                                "RC_QUEUE": "remote-shift",
                            },
                        },
                    },
                ],
            },
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Runner profile workflow",
        )
        workflow = await service.update_workflow_experiment_runner(
            workflow_id=workflow.id,
            patch={
                "kind_overrides": {
                    "baseline": {
                        "metadata": {
                            "profile_name": "baseline-default",
                        },
                    },
                },
            },
        )

        assert project.default_experiment_runner.enabled is True
        assert project.execution_catalog[0].name == "local-benchmark"
        assert (
            project.execution_catalog[0].artifact_contract["required_metrics"]
            == ["accuracy", "robust_accuracy"]
        )
        assert project.default_experiment_runner.default.catalog_entry == "local-benchmark"
        assert (
            project.default_experiment_runner.kind_overrides["stress_test"]["catalog_entry"]
            == "remote-stress"
        )
        assert workflow.experiment_runner.enabled is True
        assert workflow.experiment_runner.default.catalog_entry == "local-benchmark"
        assert (
            project.execution_catalog[1].artifact_contract["required_outputs"]
            == ["stress-report.json"]
        )
        assert (
            workflow.experiment_runner.kind_overrides["ablation"]["instructions"]
            == "Use the ablation-specific command profile."
        )
        assert (
            workflow.experiment_runner.kind_overrides["baseline"]["metadata"]["profile_name"]
            == "baseline-default"
        )
        assert workflow.experiment_runner.rules[0].name == "failure-mode-remote"
        assert workflow.experiment_runner.rules[0].hypothesis_kinds == [
            "failure_mode_probe",
        ]

    asyncio.run(_run())


def test_research_service_validates_experiment_artifact_contract(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Contract Validation Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Contract validation workflow",
        )
        claim = await service.create_claim(
            project_id=project.id,
            workflow_id=workflow.id,
            text="The contract validator should report missing metrics and outputs.",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="contract-run",
            status="planned",
            claim_ids=[claim.id],
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "metadata": {
                    "artifact_contract": {
                        "required_metrics": ["accuracy", "calibration_error"],
                        "required_outputs": ["metrics.json", "report.json"],
                        "required_artifact_types": [
                            "generated_table",
                            "generated_figure",
                        ],
                    },
                },
            },
        )
        run = await service.update_experiment(
            experiment_id=run.id,
            status="completed",
            metrics={"accuracy": 0.91},
            output_files=["outputs/metrics.json"],
            notes="Only partial outputs were recorded.",
        )
        validation = await service.get_experiment_artifact_contract_validation(run.id)
        remediation = await service.get_experiment_contract_remediation(run.id)
        persisted = await service.get_experiment(run.id)

        assert validation["enabled"] is True
        assert validation["passed"] is False
        assert validation["missing_metrics"] == ["calibration_error"]
        assert validation["missing_outputs"] == ["report.json"]
        assert validation["missing_artifact_types"] == ["generated_figure"]
        assert remediation["required"] is True
        assert remediation["action_count"] == 3
        assert [item["action_type"] for item in remediation["actions"]] == [
            "record_metric",
            "archive_output",
            "publish_artifact",
        ]
        assert remediation["actions"][0]["action_key"].endswith(":metric:calibration_error")
        assert remediation["actions"][0]["assignee"] == "analyst"
        assert remediation["actions"][2]["assignee"] == "agent"
        assert remediation["actions"][2]["retry_policy"]["max_attempts"] == 2
        assert remediation["actions"][2]["suggested_tool"] == "research_artifact_upsert"
        assert persisted.metadata["contract_validation"]["passed"] is False
        assert persisted.metadata["contract_validation"]["remediation"]["action_count"] == 3

    asyncio.run(_run())


def test_research_service_derives_contract_from_result_bundle_schema(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(
            name="Schema Contract Project",
            result_bundle_schemas=[
                {
                    "name": "analysis_summary.v1",
                    "description": "Baseline analysis summary bundle",
                    "required_sections": ["metrics", "outputs", "artifacts"],
                    "required_metrics": ["accuracy", "calibration_error"],
                    "required_outputs": ["report.json"],
                    "required_artifact_types": ["analysis"],
                },
            ],
        )
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Schema-derived contract workflow",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="schema-derived-run",
            status="planned",
        )
        configured = await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "command",
                "result_bundle_schema": "analysis_summary.v1",
            },
        )
        run = await service.update_experiment(
            experiment_id=run.id,
            status="completed",
            metrics={"accuracy": 0.93},
            output_files=["outputs/raw-metrics.json"],
            notes="Schema contract should drive remediation.",
        )
        validation = await service.get_experiment_artifact_contract_validation(run.id)

        assert (
            configured["experiment"].execution.metadata["artifact_contract"]["required_metrics"]
            == ["accuracy", "calibration_error"]
        )
        assert validation["enabled"] is True
        assert validation["passed"] is False
        assert validation["missing_metrics"] == ["calibration_error"]
        assert validation["missing_outputs"] == ["report.json"]
        assert validation["missing_artifact_types"] == ["analysis"]

    asyncio.run(_run())


def test_research_service_blocked_workflow_reminder_includes_remediation(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Reminder Contract Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Reminder remediation workflow",
        )
        run = await service.log_experiment(
            project_id=project.id,
            workflow_id=workflow.id,
            name="blocked-contract-run",
            status="planned",
            metadata={"experiment_kind": "baseline"},
        )
        await service.configure_experiment_execution(
            experiment_id=run.id,
            patch={
                "mode": "external",
                "metadata": {
                    "artifact_contract": {
                        "required_metrics": ["accuracy"],
                        "required_outputs": ["report.json"],
                        "required_artifact_types": ["analysis"],
                    },
                },
            },
        )
        await service.update_experiment(
            experiment_id=run.id,
            status="completed",
            metrics={},
            output_files=[],
            notes="The experiment completed without the required contract outputs.",
        )

        state = await service.load_state()
        workflow_state = state.workflows[0]
        workflow_state.current_stage = "experiment_run"
        workflow_state.status = "blocked"
        workflow_state.error = "Artifact contract failed."
        experiment_stage = next(
            stage for stage in workflow_state.stages if stage.name == "experiment_run"
        )
        experiment_stage.status = "blocked"
        experiment_stage.blocked_reason = workflow_state.error
        await service.save_state(state)

        workflow = await service.add_workflow_task(
            workflow_id=workflow.id,
            stage="experiment_run",
            title="Resolve experiment contract gaps",
            description="Backfill missing metrics, outputs, or artifact types.",
            metadata={
                "task_kind": "experiment_contract_followup",
                "contract_failure_run_ids": [run.id],
            },
        )
        reminders = await service.preview_due_reminders(project_id=project.id, stale_hours=1)

        assert reminders
        reminder = reminders[0]
        assert reminder.reminder_type == "stage_stuck_followup"
        assert "1 run(s) need remediation" in reminder.summary
        assert reminder.context["blocked_task_title"] == "Resolve experiment contract gaps"
        assert len(reminder.context["contract_failures"]) == 1
        assert len(reminder.context["remediation_actions"]) == 3
        assert reminder.context["remediation_actions"][2]["suggested_tool"] == (
            "research_artifact_upsert"
        )
        assert workflow.tasks[-1].metadata["task_kind"] == "experiment_contract_followup"

    asyncio.run(_run())


def test_research_service_generates_task_level_remediation_reminders(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Task Reminder Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Task reminder workflow",
        )
        workflow = await service.add_workflow_task(
            workflow_id=workflow.id,
            stage="experiment_run",
            title="Backfill robustness metric",
            description="Record the missing robustness metric before analysis.",
            assignee="analyst",
            metadata={
                "task_kind": "experiment_contract_remediation",
                "remediation_key": "run-1:metric:robust_accuracy",
                "suggested_tool": "research_experiment_update",
                "retry_policy": {
                    "max_attempts": 2,
                    "backoff_minutes": 30,
                },
            },
        )

        state = await service.load_state()
        workflow_state = state.workflows[0]
        workflow_state.current_stage = "experiment_run"
        workflow_state.status = "blocked"
        workflow_state.error = "Artifact contract failed."
        workflow_state.tasks[0].status = "blocked"
        await service.save_state(state)

        reminders = await service.generate_proactive_reminders(
            project_id=project.id,
            stale_hours=1,
        )
        state = await service.load_state()
        task = next(
            item
            for item in state.workflows[0].tasks
            if item.metadata.get("task_kind") == "experiment_contract_remediation"
        )
        task_reminders = [
            item for item in reminders if item.reminder_type == "remediation_task_followup"
        ]

        assert task_reminders
        assert task_reminders[0].task_id == task.id
        assert task_reminders[0].context["task_assignee"] == "analyst"
        assert task.dispatch_count == 1
        assert task.last_dispatch_at is not None

        second = await service.preview_due_reminders(
            project_id=project.id,
            stale_hours=1,
        )
        assert not any(item.reminder_type == "remediation_task_followup" for item in second)

        state = await service.load_state()
        task = next(
            item
            for item in state.workflows[0].tasks
            if item.metadata.get("task_kind") == "experiment_contract_remediation"
        )
        task.dispatch_count = 2
        task.last_dispatch_at = "2000-01-01T00:00:00+00:00"
        await service.save_state(state)

        third = await service.preview_due_reminders(
            project_id=project.id,
            stale_hours=1,
        )
        blocked = next(
            item for item in third if item.reminder_type == "stage_stuck_followup"
        )
        assert blocked.context["retry_exhausted_count"] == 1
        assert "exhausted retry budget" in blocked.summary

    asyncio.run(_run())


def test_research_service_records_manual_task_dispatch(tmp_path) -> None:
    async def _run() -> None:
        service = ResearchService(
            store=JsonResearchStore(tmp_path / "research-state.json"),
        )

        project = await service.create_project(name="Manual Dispatch Project")
        workflow = await service.create_workflow(
            project_id=project.id,
            title="Manual dispatch workflow",
        )
        workflow = await service.add_workflow_task(
            workflow_id=workflow.id,
            title="Follow up with the analyst",
            description="Send a direct reminder about the missing artifact.",
            assignee="analyst",
            metadata={
                "task_kind": "experiment_contract_remediation",
                "suggested_tool": "research_artifact_upsert",
            },
        )
        task_id = workflow.tasks[-1].id

        task = await service.get_workflow_task(
            workflow_id=workflow.id,
            task_id=task_id,
        )
        updated = await service.record_workflow_task_dispatch(
            workflow_id=workflow.id,
            task_id=task_id,
            summary="Manual follow-up dispatched.",
        )
        executed = await service.record_workflow_task_execution(
            workflow_id=workflow.id,
            task_id=task_id,
            summary="Manual remediation execution attempted.",
        )

        assert task.id == task_id
        assert updated.dispatch_count == 1
        assert updated.last_dispatch_at is not None
        assert updated.last_dispatch_summary == "Manual follow-up dispatched."
        assert updated.last_dispatch_error == ""
        assert executed.execution_count == 1
        assert executed.last_execution_at is not None
        assert executed.last_execution_summary == "Manual remediation execution attempted."
        assert executed.last_execution_error == ""

    asyncio.run(_run())
