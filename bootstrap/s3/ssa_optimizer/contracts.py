"""Internal contracts for SSA optimization passes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SSAPassContract:
    name: str
    requires_ssa: bool
    preserves_ssa: bool
    mutates_cfg: bool
    required_analyses: tuple[str, ...] = ()
    invalidated_analyses: tuple[str, ...] = ()
    telemetry_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SSA pass contract name must be non-empty")
        if not self.requires_ssa:
            raise ValueError("SSA optimizer passes must require SSA")
        if not self.preserves_ssa:
            raise ValueError("SSA fixpoint passes must preserve SSA")
        _require_unique("required analyses", self.required_analyses)
        _require_unique("invalidated analyses", self.invalidated_analyses)
        _require_unique("telemetry fields", self.telemetry_fields)


def _require_unique(label: str, values: tuple[str, ...]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if not value:
            raise ValueError(f"{label} must not contain empty names")
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        rendered = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate {label}: {rendered}")
