"""Candidate analysis for semantics-preserving native codegen optimizations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
import re
from typing import Any

from .assembly import AssemblyOpcode, AssemblyProgram


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DETERMINISM_CONTRACTS = (
    "IR_DETERMINISM",
    "ASSEMBLY_PROGRAM_DETERMINISM",
    "ASSEMBLY_TEXT_DETERMINISM",
    "OBJECT_DETERMINISM",
    "BINARY_DETERMINISM",
)


class OptimizationFrameworkError(ValueError):
    """Raised when optimization evidence is incomplete or untrustworthy."""


class EvidenceClass(str, Enum):
    CORRECTNESS_ONLY = "CORRECTNESS_ONLY"
    CHARACTERIZATION_ONLY = "CHARACTERIZATION_ONLY"
    NATIVE_COMPARATIVE = "NATIVE_COMPARATIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID = "INVALID"


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OptimizationFrameworkError(f"{field} must be non-empty")


def _require_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise OptimizationFrameworkError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class OptimizationHypothesis:
    observation: str
    hypothesis: str
    expected_structural_delta: str
    expected_performance_direction: str
    correctness_risk: str
    rollback_rule: str

    def validate(self) -> None:
        for name, value in asdict(self).items():
            _require_text(value, f"hypothesis.{name}")


@dataclass(frozen=True, slots=True)
class OptimizationProvenance:
    experiment_id: str
    baseline_s3_sha: str
    candidate_s3_sha: str
    benchmark_sha: str
    source_digest: str
    workload_id: str
    target: str
    backend: str
    optimization_level: str
    python_version: str
    assembler: str
    compiler: str
    linker: str
    operating_system: str
    cpu: str
    ram: str
    execution_mode: str
    warmups: int
    repetitions: int
    loops: int

    def validate(
        self,
        *,
        expected_baseline_sha: str,
        expected_candidate_sha: str,
        expected_benchmark_sha: str,
    ) -> None:
        _require_text(self.experiment_id, "provenance.experiment_id")
        _require_text(self.workload_id, "provenance.workload_id")
        for name in (
            "baseline_s3_sha",
            "candidate_s3_sha",
            "benchmark_sha",
            "source_digest",
        ):
            _require_digest(getattr(self, name), f"provenance.{name}")
        for name in (
            "target",
            "backend",
            "optimization_level",
            "python_version",
            "assembler",
            "compiler",
            "linker",
            "operating_system",
            "cpu",
            "ram",
            "execution_mode",
        ):
            _require_text(getattr(self, name), f"provenance.{name}")
        if self.baseline_s3_sha != expected_baseline_sha:
            raise OptimizationFrameworkError("baseline S3 SHA does not match the pinned evidence")
        if self.candidate_s3_sha != expected_candidate_sha:
            raise OptimizationFrameworkError("candidate S3 SHA does not match the pinned evidence")
        if self.benchmark_sha != expected_benchmark_sha:
            raise OptimizationFrameworkError("benchmark SHA does not match the pinned evidence")
        if self.warmups < 0 or self.repetitions <= 0 or self.loops <= 0:
            raise OptimizationFrameworkError("warmups, repetitions, and loops have invalid bounds")


@dataclass(frozen=True, slots=True)
class OptimizationArtifacts:
    assembly_program_digest: str
    assembly_digest: str
    object_digest: str | None = None
    binary_digest: str | None = None

    def validate(self) -> None:
        _require_digest(self.assembly_program_digest, "artifacts.assembly_program_digest")
        _require_digest(self.assembly_digest, "artifacts.assembly_digest")
        for name in ("object_digest", "binary_digest"):
            value = getattr(self, name)
            if value is not None:
                _require_digest(value, f"artifacts.{name}")


@dataclass(frozen=True, slots=True)
class OptimizationMetrics:
    instructions: int
    stack_ops: int
    branches: int
    loads_stores: int
    text_bytes: int

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value < 0:
                raise OptimizationFrameworkError(f"metrics.{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class OptimizationObservation:
    correctness: str
    provenance: str
    determinism: str
    determinism_contracts: tuple[tuple[str, str], ...]
    same_workload: bool
    same_host: bool
    same_toolchain: bool
    measurement_pairing: str
    timing_samples: tuple[float, ...]
    control_samples: tuple[float, ...]
    classification: EvidenceClass
    native_speedup_claim: bool = False

    def validate(self) -> None:
        if self.correctness not in {"PASS", "FAIL", "NOT_RUN"}:
            raise OptimizationFrameworkError("observation.correctness is invalid")
        if self.provenance not in {"PASS", "FAIL", "NOT_RUN"}:
            raise OptimizationFrameworkError("observation.provenance is invalid")
        if self.determinism not in {"PASS", "FAIL", "NOT_RUN"}:
            raise OptimizationFrameworkError("observation.determinism is invalid")
        contract_names = [name for name, _status in self.determinism_contracts]
        if len(contract_names) != len(set(contract_names)):
            raise OptimizationFrameworkError("determinism contracts must not contain duplicates")
        contracts = dict(self.determinism_contracts)
        if set(contracts) != set(_DETERMINISM_CONTRACTS):
            raise OptimizationFrameworkError("determinism contracts must cover the exact five contracts")
        for name in _DETERMINISM_CONTRACTS:
            if contracts[name] not in {"PASS", "NOT_APPLICABLE", "FAIL", "NOT_RUN"}:
                raise OptimizationFrameworkError(f"invalid status for {name}")
        for name, samples in (("timing", self.timing_samples), ("control", self.control_samples)):
            for sample in samples:
                if not isinstance(sample, (int, float)) or not math.isfinite(sample) or sample < 0:
                    raise OptimizationFrameworkError(f"{name} samples must be finite and non-negative")
        if self.classification is EvidenceClass.NATIVE_COMPARATIVE:
            if self.correctness != "PASS" or self.provenance != "PASS" or self.determinism != "PASS":
                raise OptimizationFrameworkError("native comparative evidence requires all gates to pass")
            if not self.same_workload or not self.same_host or not self.same_toolchain:
                raise OptimizationFrameworkError("native comparative evidence requires matched environments")
            if self.measurement_pairing not in {"A_B_B_A", "A_B_B_A_A_B_B_A"}:
                raise OptimizationFrameworkError("native comparative evidence requires paired measurements")
            if not self.timing_samples or len(self.timing_samples) != len(self.control_samples):
                raise OptimizationFrameworkError("native comparative evidence requires paired samples")
            if not self.native_speedup_claim:
                raise OptimizationFrameworkError("native comparative evidence must state its speedup claim")
        elif self.native_speedup_claim:
            raise OptimizationFrameworkError("native speedup claims require native comparative evidence")


@dataclass(frozen=True, slots=True)
class OptimizationExperiment:
    hypothesis: OptimizationHypothesis
    provenance: OptimizationProvenance
    artifacts: OptimizationArtifacts
    metrics: OptimizationMetrics
    observation: OptimizationObservation

    def validate(
        self,
        *,
        expected_baseline_sha: str,
        expected_candidate_sha: str,
        expected_benchmark_sha: str,
    ) -> None:
        self.hypothesis.validate()
        self.provenance.validate(
            expected_baseline_sha=expected_baseline_sha,
            expected_candidate_sha=expected_candidate_sha,
            expected_benchmark_sha=expected_benchmark_sha,
        )
        self.artifacts.validate()
        self.metrics.validate()
        self.observation.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_optimization_experiment(
    experiment: OptimizationExperiment,
    *,
    expected_baseline_sha: str,
    expected_candidate_sha: str,
    expected_benchmark_sha: str,
) -> None:
    """Validate a complete experiment and fail closed on provenance drift."""

    if not isinstance(experiment, OptimizationExperiment):
        raise OptimizationFrameworkError("optimization evidence has an invalid root type")
    experiment.validate(
        expected_baseline_sha=expected_baseline_sha,
        expected_candidate_sha=expected_candidate_sha,
        expected_benchmark_sha=expected_benchmark_sha,
    )


@dataclass(frozen=True, slots=True)
class NativeOptimizationReport:
    input_instruction_count: int
    output_instruction_count: int
    candidate_noop_moves: int

    @property
    def changed(self) -> bool:
        return self.candidate_noop_moves > 0


def analyze_redundant_noop_moves(program: AssemblyProgram) -> tuple[AssemblyProgram, NativeOptimizationReport]:
    """Analyze native self-move candidates without changing Assembly semantics."""

    if not isinstance(program, AssemblyProgram) or not program.functions:
        raise ValueError("native optimization requires a non-empty AssemblyProgram")
    input_count = sum(len(block.instructions) for function in program.functions for block in function.blocks)
    candidates = 0
    for function in program.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode is AssemblyOpcode.TMOV and len(instruction.registers) == 2 and instruction.registers[0] == instruction.registers[1]:
                    candidates += 1
    return program, NativeOptimizationReport(input_count, input_count, candidates)


def eliminate_redundant_noop_moves(program: AssemblyProgram) -> tuple[AssemblyProgram, NativeOptimizationReport]:
    """Compatibility name for candidate analysis; Assembly is never rewritten."""

    return analyze_redundant_noop_moves(program)
