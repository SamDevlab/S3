"""Public boundary for validated S3 Assembly native generation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ...assembly import AssemblyProgram, AssemblyType
from ...assembly_verifier import AssemblyVerifier
from ...emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS, DEFAULT_MAX_MEMORY_TRITS
from .diagnostics import NativeBackendError
from .emitter import X8664Emitter
from .instruction_budget import (
    InstructionBudgetMode,
    parse_instruction_budget_mode,
)
from .experimental_policy import (
    ExperimentalNativePolicyMode,
    parse_experimental_native_policy_mode,
)
from .native_policy import (
    NativeCodegenPolicy,
    NativePolicyDecision,
    NativePolicySummary,
    parse_native_codegen_policy,
    _index_register,
    resolve_native_policies,
    summarize_native_policy,
)

NATIVE_MAX_INSTRUCTIONS = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class X8664Backend:
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS
    max_frames: int = DEFAULT_MAX_FRAMES
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS
    # Native code keeps eligible values location-flexible by default.  The
    # explicit False mode remains available for stack-backed diagnostics and
    # conservative compatibility probes.
    register_allocation: bool = True
    experimental_mode: ExperimentalNativePolicyMode | str | None = field(
        default=None,
        kw_only=True,
    )
    native_policy: NativeCodegenPolicy | str | None = field(
        default=None,
        kw_only=True,
    )
    instruction_budget_mode: InstructionBudgetMode | str | None = field(
        default=None,
        kw_only=True,
    )

    def __post_init__(self) -> None:
        if self.native_policy is not None and self.experimental_mode is not None:
            raise ValueError(
                "native_policy and experimental_mode cannot both be set"
            )
        if self.experimental_mode is not None:
            legacy = parse_experimental_native_policy_mode(self.experimental_mode)
            policy = (
                NativeCodegenPolicy.BASELINE
                if legacy is ExperimentalNativePolicyMode.OFF
                else NativeCodegenPolicy.COMPACT_EA
            )
            object.__setattr__(self, "experimental_mode", legacy)
        else:
            policy = parse_native_codegen_policy(self.native_policy)
        object.__setattr__(self, "native_policy", policy)
        object.__setattr__(
            self,
            "instruction_budget_mode",
            parse_instruction_budget_mode(self.instruction_budget_mode),
        )

    def generate(self, program: AssemblyProgram) -> str:
        if isinstance(self.max_instructions, bool) or not isinstance(self.max_instructions, int):
            raise TypeError("max_instructions must be an integer")
        if self.max_frames < 1:
            raise NativeBackendError("max_frames must be at least 1")
        if self.max_instructions < 1:
            raise NativeBackendError("max_instructions must be at least 1")
        if self.max_instructions > NATIVE_MAX_INSTRUCTIONS:
            raise NativeBackendError(f"max_instructions exceeds physical 64-bit limit of {NATIVE_MAX_INSTRUCTIONS}")
        AssemblyVerifier(max_memory_trits=self.max_memory_trits).validate(
            program,
            entry="main",
        )
        main = next(function for function in program.functions if function.name == "main")
        if main.return_type is AssemblyType.STRING:
            raise NativeBackendError(
                "native entry function 'main' cannot return string"
            )
        if main.return_type in {AssemblyType.BYTES, AssemblyType.TEXT, AssemblyType.VECTOR}:
            raise NativeBackendError(
                "native entry function 'main' cannot return a dynamic value"
            )
        if main.return_type is AssemblyType.F64:
            raise NativeBackendError(
                "native entry function 'main' cannot return f64 until the "
                "standalone runtime provides decimal float output"
            )
        if main.result_width != 1:
            raise NativeBackendError(
                "native entry function 'main' must return one result cell"
            )
        compact_ea_by_function = None
        if self.native_policy is NativeCodegenPolicy.COMPACT_EA:
            selections = self._resolved_native_policy_decisions(program)
            compact_ea_by_function = {
                name: decision.applied
                for name, decision in selections.items()
            }
        return X8664Emitter(
            program,
            max_frames=self.max_frames,
            max_instructions=self.max_instructions,
            register_allocation=self.register_allocation,
            compact_ea_by_function=compact_ea_by_function,
            instruction_budget_mode=self.instruction_budget_mode,
        ).emit()

    def explain_native_policy(self, program: AssemblyProgram) -> NativePolicySummary:
        """Return deterministic per-function policy decisions for observability."""

        return summarize_native_policy(
            program.functions,
            self.native_policy,
            decisions=self._resolved_native_policy_decisions(program),
        )

    def _resolved_native_policy_decisions(
        self,
        program: AssemblyProgram,
    ) -> dict[str, NativePolicyDecision]:
        decisions = resolve_native_policies(program.functions, self.native_policy)
        if self.native_policy is not NativeCodegenPolicy.COMPACT_EA:
            return decisions
        from .allocation import analyze_allocation
        from .residence import analyze_cross_block_residence

        for function in program.functions:
            decision = decisions[function.name]
            if not decision.applied:
                continue
            plan = (
                analyze_allocation(function)
                if self.register_allocation
                else analyze_cross_block_residence(function)
            )
            for instruction in function.instructions:
                index_register = _index_register(instruction)
                if index_register is None:
                    continue
                physical = plan.physical_register(index_register)
                if physical is None or physical in {"rax", "r10", "r11"}:
                    decisions[function.name] = replace(
                        decision,
                        effective_policy=NativeCodegenPolicy.BASELINE,
                        applied=False,
                        reason=(
                            "compact_ea_fallback:"
                            "physical_index_residence_not_proven"
                        ),
                    )
                    break
        return decisions

    def _generate_ffi(self, program: AssemblyProgram) -> str:
        return X8664Emitter(
            program,
            max_frames=self.max_frames,
            max_instructions=self.max_instructions,
            register_allocation=self.register_allocation,
            instruction_budget_mode=self.instruction_budget_mode,
            compact_ea_by_function=(
                {
                    name: decision.applied
                    for name, decision in self._resolved_native_policy_decisions(
                        program
                    ).items()
                }
                if self.native_policy is NativeCodegenPolicy.COMPACT_EA
                else None
            ),
        ).emit()


def generate_native_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    native_policy: NativeCodegenPolicy | str | None = None,
) -> str:
    from .._native_assembly import _generate_native_assembly

    return _generate_native_assembly(
        program,
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
        native_policy=native_policy,
    )


def _generate_native_assembly_with_budget(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    native_policy: NativeCodegenPolicy | str | None = None,
    instruction_budget_mode: InstructionBudgetMode | str,
) -> str:
    from .._native_assembly import _generate_native_assembly

    return _generate_native_assembly(
        program,
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
        native_policy=native_policy,
        instruction_budget_mode=instruction_budget_mode,
    )


def generate_ffi_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    native_policy: NativeCodegenPolicy | str | None = None,
) -> str:
    """Generate native text for a hosted FFI artifact without entry restrictions."""

    AssemblyVerifier(max_memory_trits=max_memory_trits).validate(program)
    return X8664Backend(
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
        native_policy=native_policy,
    )._generate_ffi(program)
