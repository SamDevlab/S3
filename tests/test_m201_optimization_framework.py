from __future__ import annotations

from dataclasses import replace

import pytest

from bootstrap.s3.codegen_optimization import (
    EvidenceClass,
    OptimizationArtifacts,
    OptimizationExperiment,
    OptimizationFrameworkError,
    OptimizationHypothesis,
    OptimizationMetrics,
    OptimizationObservation,
    OptimizationProvenance,
    validate_optimization_experiment,
)


BASELINE = "a" * 64
CANDIDATE = "b" * 64
BENCHMARK = "c" * 64
DIGEST = "d" * 64


def _experiment(*, baseline: str = BASELINE, native: bool = False) -> OptimizationExperiment:
    contracts = (
        ("IR_DETERMINISM", "PASS"),
        ("ASSEMBLY_PROGRAM_DETERMINISM", "PASS"),
        ("ASSEMBLY_TEXT_DETERMINISM", "PASS"),
        ("OBJECT_DETERMINISM", "NOT_APPLICABLE"),
        ("BINARY_DETERMINISM", "NOT_APPLICABLE"),
    )
    observation = OptimizationObservation(
        correctness="PASS",
        provenance="PASS",
        determinism="PASS",
        determinism_contracts=contracts,
        same_workload=True,
        same_host=True,
        same_toolchain=True,
        measurement_pairing="A_B_B_A" if native else "NOT_TIMED",
        timing_samples=(1.0, 2.0) if native else (),
        control_samples=(1.1, 2.1) if native else (),
        classification=EvidenceClass.NATIVE_COMPARATIVE if native else EvidenceClass.CORRECTNESS_ONLY,
        native_speedup_claim=native,
    )
    return OptimizationExperiment(
        hypothesis=OptimizationHypothesis(
            observation="self moves are observable logical instructions",
            hypothesis="native lowering can avoid redundant physical moves",
            expected_structural_delta="fewer physical moves, unchanged AssemblyProgram",
            expected_performance_direction="neutral or improved",
            correctness_risk="uninitialized reads and observable instruction limits",
            rollback_rule="rollback if any hosted or native differential case changes",
        ),
        provenance=OptimizationProvenance(
            experiment_id="m201-test",
            baseline_s3_sha=baseline,
            candidate_s3_sha=CANDIDATE,
            benchmark_sha=BENCHMARK,
            source_digest=DIGEST,
            workload_id="test-workload",
            target="linux-x86-64",
            backend="x86-64",
            optimization_level="O1",
            python_version="3.11.9",
            assembler="gas",
            compiler="gcc",
            linker="ld",
            operating_system="Windows-hosted",
            cpu="test-cpu",
            ram="test-ram",
            execution_mode="hosted-emulator",
            warmups=1,
            repetitions=2,
            loops=10,
        ),
        artifacts=OptimizationArtifacts(DIGEST, DIGEST),
        metrics=OptimizationMetrics(10, 2, 3, 4, 100),
        observation=observation,
    )


def test_framework_accepts_complete_pinned_correctness_evidence() -> None:
    experiment = _experiment()
    validate_optimization_experiment(
        experiment,
        expected_baseline_sha=BASELINE,
        expected_candidate_sha=CANDIDATE,
        expected_benchmark_sha=BENCHMARK,
    )
    assert experiment.to_dict()["provenance"]["candidate_s3_sha"] == CANDIDATE


def test_framework_rejects_provenance_drift() -> None:
    with pytest.raises(OptimizationFrameworkError, match="baseline S3 SHA"):
        validate_optimization_experiment(
            _experiment(baseline="e" * 64),
            expected_baseline_sha=BASELINE,
            expected_candidate_sha=CANDIDATE,
            expected_benchmark_sha=BENCHMARK,
        )


def test_framework_rejects_incomplete_determinism_contracts() -> None:
    experiment = _experiment()
    broken = replace(
        experiment.observation,
        determinism_contracts=(("IR_DETERMINISM", "PASS"),),
    )
    broken_experiment = OptimizationExperiment(
        experiment.hypothesis,
        experiment.provenance,
        experiment.artifacts,
        experiment.metrics,
        broken,
    )
    with pytest.raises(OptimizationFrameworkError, match="exact five contracts"):
        broken_experiment.validate(
            expected_baseline_sha=BASELINE,
            expected_candidate_sha=CANDIDATE,
            expected_benchmark_sha=BENCHMARK,
        )


def test_framework_rejects_duplicate_determinism_contracts() -> None:
    experiment = _experiment()
    broken = replace(
        experiment.observation,
        determinism_contracts=(
            ("IR_DETERMINISM", "PASS"),
            ("IR_DETERMINISM", "PASS"),
            ("ASSEMBLY_PROGRAM_DETERMINISM", "PASS"),
            ("ASSEMBLY_TEXT_DETERMINISM", "PASS"),
            ("OBJECT_DETERMINISM", "NOT_APPLICABLE"),
        ),
    )
    broken_experiment = replace(experiment, observation=broken)
    with pytest.raises(OptimizationFrameworkError, match="must not contain duplicates"):
        broken_experiment.validate(
            expected_baseline_sha=BASELINE,
            expected_candidate_sha=CANDIDATE,
            expected_benchmark_sha=BENCHMARK,
        )


def test_native_comparative_requires_matched_paired_evidence() -> None:
    experiment = _experiment(native=True)
    validate_optimization_experiment(
        experiment,
        expected_baseline_sha=BASELINE,
        expected_candidate_sha=CANDIDATE,
        expected_benchmark_sha=BENCHMARK,
    )
    observation = replace(experiment.observation, same_host=False)
    broken = OptimizationExperiment(
        experiment.hypothesis,
        experiment.provenance,
        experiment.artifacts,
        experiment.metrics,
        observation,
    )
    with pytest.raises(OptimizationFrameworkError, match="matched environments"):
        broken.validate(
            expected_baseline_sha=BASELINE,
            expected_candidate_sha=CANDIDATE,
            expected_benchmark_sha=BENCHMARK,
        )
