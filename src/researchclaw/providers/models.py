"""Provider data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProviderConfig:
    name: str
    provider_type: str
    model_name: str = ""
    model_names: list[str] = field(default_factory=list)
    api_key: str = ""
    base_url: str = ""
    enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        model_names = [str(item).strip() for item in self.model_names if str(item).strip()]
        if self.model_name and self.model_name not in model_names:
            model_names.insert(0, self.model_name)
        if not data["model_name"] and model_names:
            data["model_name"] = model_names[0]
        data["model_names"] = model_names
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        raw_model_names = data.get("model_names")
        model_names = (
            [str(item).strip() for item in raw_model_names if str(item).strip()]
            if isinstance(raw_model_names, list)
            else []
        )
        model_name = str(data.get("model_name", "") or "").strip()
        if model_name and model_name not in model_names:
            model_names.insert(0, model_name)
        if not model_name and model_names:
            model_name = model_names[0]
        return cls(
            name=data.get("name", ""),
            provider_type=data.get("provider_type", ""),
            model_name=model_name,
            model_names=model_names,
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            enabled=bool(data.get("enabled", False)),
            extra=data.get("extra", {}),
        )
