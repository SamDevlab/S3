"""Deterministic internal policy model for the x86-64 native backend."""

from __future__ import annotations

from dataclasses import dataclass

from .registers import (
    CALLER_SAVED_ALLOCATABLE_REGISTERS,
    CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    FULL_ALLOCATABLE_REGISTERS,
    EMITTER_SCRATCH_REGISTERS,
    NON_ALLOCATABLE_REGISTERS,
    RETURN_REGISTER,
)


_CALL_RESIDENCE = frozenset({
    "whole_function_frame_fallback",
    "selective_live_across_call",
})
_RESIDENCE_SCOPE = frozenset({"single_definition_cross_block", "region"})
_SPILL_POLICY = frozenset({"stack_on_exhaustion", "cost_weighted", "region_aware"})
_REMATERIALIZATION = frozenset({"disabled", "const_only"})
_LIVE_RANGE_SPLIT = frozenset({"disabled", "loop_boundary"})
_MOVE_POLICY = frozenset({"disabled", "safe_affinity"})
_INDEXED_POLICY = frozenset({"canonical", "compact_ea", "base_pinning", "index_pinning", "base_plus_index"})
_SCALAR_POLICY = frozenset({"disabled", "conservative_mem2reg", "read_cache", "writeback_island"})
_FORWARDING_POLICY = frozenset({"disabled", "safe_frame_forwarding"})
_WRITEBACK_POLICY = frozenset({"canonical", "boundary_flush"})

SPILL_COST_KEYS = (
    "use_count",
    "loop_depth",
    "interference_degree",
    "call_crossing",
    "rematerializable",
    "live_range_length",
)
DEFAULT_SPILL_COST_PARAMETERS = tuple(
    (key, value)
    for key, value in (
        ("use_count", 4),
        ("loop_depth", 8),
        ("interference_degree", 2),
        ("call_crossing", 6),
        ("rematerializable", -5),
        ("live_range_length", 1),
    )
)


@dataclass(frozen=True, slots=True)
class NativePolicy:
    """A complete, deterministic strategy description for backend experiments.

    The fields intentionally describe policy choices without exposing a public
    language or ABI concept.  Unsupported lowering choices remain explicit and
    are rejected by the experiment harness rather than silently approximated.
    """

    name: str
    register_order: tuple[str, ...]
    call_register_order: tuple[str, ...]
    call_residence: str
    residence_scope: str
    spill_policy: str
    spill_cost_parameters: tuple[tuple[str, int], ...]
    rematerialization: str
    live_range_split: str
    move_coalescing: str
    indexed_memory_policy: str
    scalar_promotion: str
    load_forwarding: str
    writeback_policy: str

    def validate(self) -> None:
        if not self.name or not self.name.isidentifier():
            raise ValueError("native policy name must be a non-empty identifier")
        expected = set(FULL_ALLOCATABLE_REGISTERS)
        reserved = EMITTER_SCRATCH_REGISTERS | NON_ALLOCATABLE_REGISTERS | {RETURN_REGISTER}
        for field_name, order in (("register_order", self.register_order), ("call_register_order", self.call_register_order)):
            if len(order) != len(expected) or set(order) != expected or len(set(order)) != len(order):
                raise ValueError(f"{field_name} must be a permutation of the ABI allocatable pool")
            if set(order) & reserved:
                raise ValueError(f"{field_name} contains a reserved register")
        if self.call_residence not in _CALL_RESIDENCE:
            raise ValueError(f"unsupported call residence policy: {self.call_residence}")
        if self.residence_scope not in _RESIDENCE_SCOPE:
            raise ValueError(f"unsupported residence scope: {self.residence_scope}")
        if self.spill_policy not in _SPILL_POLICY:
            raise ValueError(f"unsupported spill policy: {self.spill_policy}")
        parameters = tuple(self.spill_cost_parameters)
        if tuple(key for key, _ in parameters) != SPILL_COST_KEYS:
            raise ValueError("spill_cost_parameters must use the canonical key order")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not -64 <= value <= 64
            for _, value in parameters
        ):
            raise ValueError("spill cost parameters must be bounded integers")
        if self.rematerialization not in _REMATERIALIZATION:
            raise ValueError(f"unsupported rematerialization policy: {self.rematerialization}")
        if self.live_range_split not in _LIVE_RANGE_SPLIT:
            raise ValueError(f"unsupported live-range split policy: {self.live_range_split}")
        if self.move_coalescing not in _MOVE_POLICY:
            raise ValueError(f"unsupported move policy: {self.move_coalescing}")
        if self.indexed_memory_policy not in _INDEXED_POLICY:
            raise ValueError(f"unsupported indexed-memory policy: {self.indexed_memory_policy}")
        if self.scalar_promotion not in _SCALAR_POLICY:
            raise ValueError(f"unsupported scalar policy: {self.scalar_promotion}")
        if self.load_forwarding not in _FORWARDING_POLICY:
            raise ValueError(f"unsupported load-forwarding policy: {self.load_forwarding}")
        if self.writeback_policy not in _WRITEBACK_POLICY:
            raise ValueError(f"unsupported writeback policy: {self.writeback_policy}")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "register_order": list(self.register_order),
            "call_register_order": list(self.call_register_order),
            "call_residence": self.call_residence,
            "residence_scope": self.residence_scope,
            "spill_policy": self.spill_policy,
            "spill_cost_parameters": [
                [key, value] for key, value in self.spill_cost_parameters
            ],
            "rematerialization": self.rematerialization,
            "live_range_split": self.live_range_split,
            "move_coalescing": self.move_coalescing,
            "indexed_memory_policy": self.indexed_memory_policy,
            "scalar_promotion": self.scalar_promotion,
            "load_forwarding": self.load_forwarding,
            "writeback_policy": self.writeback_policy,
        }


BASELINE_NATIVE_POLICY = NativePolicy(
    name="baseline",
    register_order=(*CALLER_SAVED_ALLOCATABLE_REGISTERS, *CALLEE_SAVED_ALLOCATABLE_REGISTERS),
    call_register_order=(*CALLEE_SAVED_ALLOCATABLE_REGISTERS, *CALLER_SAVED_ALLOCATABLE_REGISTERS),
    call_residence="whole_function_frame_fallback",
    residence_scope="single_definition_cross_block",
    spill_policy="stack_on_exhaustion",
    spill_cost_parameters=DEFAULT_SPILL_COST_PARAMETERS,
    rematerialization="disabled",
    live_range_split="disabled",
    move_coalescing="disabled",
    indexed_memory_policy="canonical",
    scalar_promotion="disabled",
    load_forwarding="disabled",
    writeback_policy="canonical",
)


BASELINE_NATIVE_POLICY.validate()


def policy_with(policy: NativePolicy = BASELINE_NATIVE_POLICY, **changes: object) -> NativePolicy:
    """Build and validate one deterministic experimental policy."""

    values = policy.to_dict()
    values.update(changes)
    result = NativePolicy(
        name=str(values["name"]),
        register_order=tuple(values["register_order"]),
        call_register_order=tuple(values["call_register_order"]),
        call_residence=str(values["call_residence"]),
        residence_scope=str(values["residence_scope"]),
        spill_policy=str(values["spill_policy"]),
        spill_cost_parameters=tuple(
            (str(key), int(value))
            for key, value in values["spill_cost_parameters"]
        ),
        rematerialization=str(values["rematerialization"]),
        live_range_split=str(values["live_range_split"]),
        move_coalescing=str(values["move_coalescing"]),
        indexed_memory_policy=str(values["indexed_memory_policy"]),
        scalar_promotion=str(values["scalar_promotion"]),
        load_forwarding=str(values["load_forwarding"]),
        writeback_policy=str(values["writeback_policy"]),
    )
    result.validate()
    return result
