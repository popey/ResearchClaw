from pathlib import Path

from researchclaw.agents.skills.experiment_tracker import register


def test_log_experiment_accepts_status_and_experiment_id_aliases(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        "researchclaw.agents.skills.experiment_tracker.EXPERIMENTS_DIR",
        str(tmp_path),
    )
    tools = register()

    result = tools["log_experiment"](
        metrics={"acc": 0.99},
        notes="CPU run",
        status="completed",
        Experiment_id="exp_manual_001",
    )

    assert result["experiment_id"] == "exp_manual_001"
    assert result["status"] == "completed"
    assert result["name"] == "exp_manual_001"
    assert result["parameters"] == {}
    assert result["metrics"] == {"acc": 0.99}


def test_log_experiment_preserves_extra_kwargs(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        "researchclaw.agents.skills.experiment_tracker.EXPERIMENTS_DIR",
        str(tmp_path),
    )
    tools = register()

    result = tools["log_experiment"](
        name="cnn-run",
        parameters={"epochs": 5},
        metrics={"acc": 0.95},
        device="cpu",
        framework="pytorch",
    )

    assert result["name"] == "cnn-run"
    assert result["extra"] == {"device": "cpu", "framework": "pytorch"}
