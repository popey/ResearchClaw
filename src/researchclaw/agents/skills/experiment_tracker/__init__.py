"""Experiment tracker skill – log and track research experiments."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ....constant import EXPERIMENTS_DIR


def register():
    """Register experiment tracking tools."""

    def _normalize_key(value: str) -> str:
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    def _pop_alias(
        data: dict[str, Any],
        *aliases: str,
    ) -> Any:
        wanted = {_normalize_key(alias) for alias in aliases}
        for key in list(data.keys()):
            if _normalize_key(key) in wanted:
                return data.pop(key)
        return None

    def log_experiment(
        name: str = "",
        parameters: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        notes: str = "",
        tags: Optional[list[str]] = None,
        experiment_id: str = "",
        status: str = "",
        **kwargs: Any,
    ) -> dict:
        """Log a research experiment.

        Parameters
        ----------
        name:
            Experiment name.
        parameters:
            Experiment parameters/hyperparameters.
        metrics:
            Experiment results/metrics.
        notes:
            Additional notes.
        tags:
            Experiment tags for categorisation.
        experiment_id:
            Optional explicit experiment ID.
        status:
            Optional explicit experiment status.
        **kwargs:
            Extra compatibility fields from the model/tool call.

        Returns
        -------
        dict
            Logged experiment record.
        """
        extra = dict(kwargs)

        alias_name = _pop_alias(extra, "experiment_name", "title")
        alias_parameters = _pop_alias(
            extra,
            "params",
            "config",
            "hyperparameters",
            "settings",
        )
        alias_metrics = _pop_alias(extra, "results", "metric_values")
        alias_tags = _pop_alias(extra, "labels")
        alias_notes = _pop_alias(extra, "description", "comment")
        alias_experiment_id = _pop_alias(extra, "experiment_id", "id")
        alias_status = _pop_alias(extra, "status", "state")

        if not name and isinstance(alias_name, str):
            name = alias_name.strip()
        if parameters is None and isinstance(alias_parameters, dict):
            parameters = alias_parameters
        if metrics is None and isinstance(alias_metrics, dict):
            metrics = alias_metrics
        if not notes and isinstance(alias_notes, str):
            notes = alias_notes
        if not tags and isinstance(alias_tags, list):
            tags = [str(item).strip() for item in alias_tags if str(item).strip()]
        if not experiment_id and isinstance(alias_experiment_id, str):
            experiment_id = alias_experiment_id.strip()
        if not status and isinstance(alias_status, str):
            status = alias_status.strip()

        exp_dir = Path(EXPERIMENTS_DIR)
        exp_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat()
        experiment_id = experiment_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        name = name.strip() or experiment_id
        parameters = parameters if isinstance(parameters, dict) else {}
        metrics = metrics if isinstance(metrics, dict) else {}
        status = status.strip() or ("completed" if metrics else "running")

        record = {
            "experiment_id": experiment_id,
            "name": name,
            "parameters": parameters,
            "metrics": metrics,
            "notes": notes,
            "tags": tags or [],
            "timestamp": timestamp,
            "status": status,
        }
        if extra:
            record["extra"] = extra

        # Save to experiments log
        log_file = exp_dir / "experiments.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def list_experiments(
        tag: Optional[str] = None,
        name_filter: Optional[str] = None,
        max_results: int = 50,
    ) -> list[dict]:
        """List logged experiments.

        Parameters
        ----------
        tag:
            Filter by tag.
        name_filter:
            Filter by name (substring match).
        max_results:
            Maximum results.

        Returns
        -------
        list[dict]
            Matching experiments.
        """
        log_file = Path(EXPERIMENTS_DIR) / "experiments.jsonl"
        if not log_file.exists():
            return []

        experiments = []
        for line in log_file.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                exp = json.loads(line)
                if tag and tag not in exp.get("tags", []):
                    continue
                if name_filter and name_filter.lower() not in exp.get("name", "").lower():
                    continue
                experiments.append(exp)
            except json.JSONDecodeError:
                continue

        return experiments[-max_results:]

    def compare_experiments(
        experiment_ids: list[str],
    ) -> dict:
        """Compare multiple experiments side by side.

        Parameters
        ----------
        experiment_ids:
            List of experiment IDs to compare.

        Returns
        -------
        dict
            Comparison table with parameters and metrics.
        """
        all_exps = list_experiments(max_results=10000)
        selected = [e for e in all_exps if e["experiment_id"] in experiment_ids]

        if not selected:
            return {"error": "No matching experiments found"}

        # Collect all parameter and metric keys
        all_params = set()
        all_metrics = set()
        for exp in selected:
            all_params.update(exp.get("parameters", {}).keys())
            all_metrics.update(exp.get("metrics", {}).keys())

        comparison = {
            "experiments": [],
            "parameter_keys": sorted(all_params),
            "metric_keys": sorted(all_metrics),
        }

        for exp in selected:
            row = {
                "id": exp["experiment_id"],
                "name": exp["name"],
                "timestamp": exp["timestamp"],
                "parameters": {
                    k: exp.get("parameters", {}).get(k, "-") for k in all_params
                },
                "metrics": {
                    k: exp.get("metrics", {}).get(k, "-") for k in all_metrics
                },
            }
            comparison["experiments"].append(row)

        return comparison

    return {
        "log_experiment": log_experiment,
        "list_experiments": list_experiments,
        "compare_experiments": compare_experiments,
    }
