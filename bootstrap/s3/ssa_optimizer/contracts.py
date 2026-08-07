"""Internal contracts for SSA optimization passes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ssa import SSAFunction


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


@dataclass(frozen=True, slots=True)
class PassResult:
    function: SSAFunction
    changed: bool
    telemetry: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        _require_unique(
            "telemetry fields",
            tuple(field for field, _count in self.telemetry),
        )
        for _field, count in self.telemetry:
            if count < 0:
                raise ValueError("pass result telemetry counts must be non-negative")


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


SSA_PASS_CONTRACTS = (
    SSAPassContract(
        "gvn",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        required_analyses=("cfg", "dominance"),
        invalidated_analyses=("value-numbering", "uses"),
        telemetry_fields=("expressions_eliminated",),
    ),
    SSAPassContract(
        "copy_propagation",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        invalidated_analyses=("uses",),
    ),
    SSAPassContract(
        "dse",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        required_analyses=("alias-analysis",),
        invalidated_analyses=("memory-uses",),
        telemetry_fields=("stores_removed",),
    ),
    SSAPassContract(
        "global_dse",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        required_analyses=(),
        invalidated_analyses=("memory-uses", "uses"),
        telemetry_fields=("stores_removed",),
    ),
    SSAPassContract(
        "dce",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        invalidated_analyses=("uses",),
    ),
    SSAPassContract(
        "adce",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        invalidated_analyses=("uses",),
        telemetry_fields=("dead_instructions_removed",),
    ),
    SSAPassContract(
        "licm",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        required_analyses=("cfg", "dominance"),
        invalidated_analyses=("uses",),
        telemetry_fields=("licm_moves",),
    ),
    SSAPassContract(
        "sccp",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=True,
        required_analyses=("cfg",),
        invalidated_analyses=("cfg", "dominance", "uses"),
        telemetry_fields=("expressions_eliminated", "branches_removed"),
    ),
    SSAPassContract(
        "strength_reduction",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        invalidated_analyses=("uses",),
        telemetry_fields=("strength_reductions",),
    ),
    SSAPassContract(
        "peephole",
        requires_ssa=True,
        preserves_ssa=True,
        mutates_cfg=False,
        invalidated_analyses=("uses",),
    ),
)
