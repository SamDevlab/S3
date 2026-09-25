"""Causal tests for the process-per-loop explosion fix.

These tests verify that:
1. Process-based adapters never spawn N subprocesses for loops=N.
2. The harness forces loops_per_sample=1 for process-scoped adapters.
3. Result metadata includes measurement_scope and process_launches_per_sample.
4. Kernel-scoped adapters can still use calibrated loops > 1.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytestmark = pytest.mark.s3_benchmark

from benchmarks.s3bench import (
    BenchmarkHarness,
    BuildArtifact,
    ExecutionObservation,
    load_manifest,
)
from benchmarks.s3bench.adapters import (
    MEASUREMENT_SCOPE_KERNEL,
    MEASUREMENT_SCOPE_PROCESS,
    S3NativeAdapter,
    S3EmulatorAdapter,
    PythonReferenceAdapter,
    ExternalCompilerAdapter,
    _native_instruction_limit,
    _native_instruction_budget_mode,
)
from benchmarks.s3bench.core import BenchmarkError, CommandResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _case():
    root = Path(__file__).resolve().parents[1]
    _, cases = load_manifest(root / "benchmarks" / "manifests" / "s3bench-1.0.0.json")
    return replace(
        cases[0],
        benchmark_id="test.fake.v1",
        implementation="fake",
        adapter="fake",
        expected_checksum="7",
    )


def test_native_instruction_limit_is_explicit_bounded_and_backward_compatible() -> None:
    case = _case()
    assert _native_instruction_limit(case) == 100_000
    assert _native_instruction_limit(
        replace(case, configuration={"native_max_instructions": 50_000_000})
    ) == 50_000_000

    for value in (True, 0, -1, 1.5, "50000000", 1 << 64):
        with pytest.raises(BenchmarkError, match="native_max_instructions"):
            _native_instruction_limit(
                replace(case, configuration={"native_max_instructions": value})
            )


def test_native_instruction_budget_mode_is_explicit_and_backward_compatible() -> None:
    case = _case()
    assert _native_instruction_budget_mode(case).value == "per-instruction"
    assert _native_instruction_budget_mode(
        replace(case, configuration={"native_instruction_budget_mode": "loop-hybrid"})
    ).value == "loop-hybrid"
    assert _native_instruction_budget_mode(
        replace(case, configuration={"native_instruction_budget_mode": "exact-segment"})
    ).value == "exact-segment"

    for value in (True, 1, None, "unknown"):
        with pytest.raises(BenchmarkError, match="native_instruction_budget_mode"):
            _native_instruction_budget_mode(
                replace(case, configuration={"native_instruction_budget_mode": value})
            )


class ProcessCountingAdapter:
    """Adapter that counts how many times run_command (subprocess) is called."""

    def __init__(self, *, measurement_scope: str, process_launches_per_sample: int):
        self.measurement_scope = measurement_scope
        self.process_launches_per_sample = process_launches_per_sample
        self.subprocess_call_count = 0
        self.loops_received: list[int] = []

    def build(self, case, build_dir):
        del case, build_dir
        return BuildArtifact(compile_duration_ns=5, artifact_size_bytes=8)

    def execute(self, case, artifact, loops, timeout_seconds):
        del case, artifact, timeout_seconds
        self.loops_received.append(loops)
        # Simulate exactly the number of subprocesses this adapter type would launch
        if self.measurement_scope == MEASUREMENT_SCOPE_PROCESS:
            # Mode B: always exactly 1 subprocess, regardless of loops
            self.subprocess_call_count += 1
        else:
            # Mode A: 1 subprocess per execute() call, loops handled internally
            self.subprocess_call_count += 1
        return ExecutionObservation("7", loops * 100)


class KernelAdapter:
    """In-process adapter — no subprocess, loops handled internally."""

    measurement_scope = MEASUREMENT_SCOPE_KERNEL
    process_launches_per_sample = 0

    def __init__(self):
        self.loops_received: list[int] = []

    def build(self, case, build_dir):
        del case, build_dir
        return BuildArtifact(compile_duration_ns=5, artifact_size_bytes=8)

    def execute(self, case, artifact, loops, timeout_seconds):
        del case, artifact, timeout_seconds
        self.loops_received.append(loops)
        return ExecutionObservation("7", loops * 100)


# ---------------------------------------------------------------------------
# Core causal test: loops=100 must NOT produce 100 subprocess launches
# ---------------------------------------------------------------------------

class TestProcessExplosionPrevention:
    """Verify that process-scoped adapters never multiply subprocess launches."""

    def test_process_scoped_adapter_does_not_fork_per_loop(self, tmp_path):
        """The definitive causal test.

        If the harness were to pass loops=100 to a process-scoped adapter
        and the adapter were to launch 100 processes, this test would fail.

        After the fix, the harness forces loops=1 for process-scoped adapters.
        """
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=2,
            samples=5,
            # Explicitly request loops=100 — the harness must override to 1
            loops=100,
            target_sample_ns=200_000_000,
        )

        # The harness must have forced loops_per_sample = 1
        assert result["loops_per_sample"] == 1, (
            f"Expected loops_per_sample=1 for process-scoped adapter, "
            f"got {result['loops_per_sample']}"
        )

        # Verify: all execute() calls received loops=1
        measurement_calls = adapter.loops_received
        # verification(1) + warmups(2) + samples(5) = 8 calls total
        assert all(loop == 1 for loop in measurement_calls), (
            f"Expected all loops=1, got: {measurement_calls}"
        )

        # The total subprocess count must be small (1 per call, not N per call)
        # verification(1) + warmups(2) + samples(5) = 8 subprocess calls
        assert adapter.subprocess_call_count == 8, (
            f"Expected 8 subprocess calls (1+2+5), got {adapter.subprocess_call_count}"
        )

    def test_kernel_scoped_adapter_uses_calibrated_loops(self, tmp_path):
        """Kernel-scoped adapters must be able to use loops > 1."""
        adapter = KernelAdapter()
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=2,
            samples=3,
            target_sample_ns=200,
        )

        # Calibration should produce loops > 1 for this fast adapter
        assert result["loops_per_sample"] >= 1
        # Measurement samples should use the calibrated loops count
        sample_loops = adapter.loops_received[-(3):]  # last 3 are samples
        assert all(loop == result["loops_per_sample"] for loop in sample_loops)


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------

class TestMeasurementScopeMetadata:
    """Verify that result documents carry measurement_scope metadata."""

    def test_process_scoped_result_has_correct_metadata(self, tmp_path):
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=0,
            samples=2,
        )

        assert result["measurement_scope"] == "process"
        assert result["process_launches_per_sample"] == 1
        assert result["loops_per_sample"] == 1

    def test_kernel_scoped_result_has_correct_metadata(self, tmp_path):
        adapter = KernelAdapter()
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=0,
            samples=2,
            loops=1,
        )

        assert result["measurement_scope"] == "kernel"
        assert result["process_launches_per_sample"] == 0

    def test_verify_only_includes_metadata(self, tmp_path):
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            verify_only=True,
        )

        assert result["measurement_scope"] == "process"
        assert result["process_launches_per_sample"] == 1

    def test_build_only_includes_metadata(self, tmp_path):
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            build_only=True,
        )

        assert result["measurement_scope"] == "process"
        assert result["process_launches_per_sample"] == 1


# ---------------------------------------------------------------------------
# Adapter classification tests
# ---------------------------------------------------------------------------

class TestAdapterClassification:
    """Verify that each adapter declares the correct measurement scope."""

    def test_s3_emulator_is_kernel_scoped(self):
        adapter = S3EmulatorAdapter()
        assert adapter.measurement_scope == MEASUREMENT_SCOPE_KERNEL
        assert adapter.process_launches_per_sample == 0

    def test_s3_native_is_process_scoped(self):
        adapter = S3NativeAdapter()
        assert adapter.measurement_scope == MEASUREMENT_SCOPE_PROCESS
        assert adapter.process_launches_per_sample == 1

    def test_python_reference_is_kernel_scoped(self):
        adapter = PythonReferenceAdapter()
        assert adapter.measurement_scope == MEASUREMENT_SCOPE_KERNEL
        assert adapter.process_launches_per_sample == 1

    def test_external_c_is_kernel_scoped(self):
        from benchmarks.s3bench.adapters import Toolchain
        tc = Toolchain("clang", None, None, False, ("clang", "--version"))
        adapter = ExternalCompilerAdapter("c", tc)
        assert adapter.measurement_scope == MEASUREMENT_SCOPE_KERNEL
        assert adapter.process_launches_per_sample == 1


class TestS3EmulatorUnrenderableAssembly:
    def test_tmul_executes_without_claiming_text_or_artifact_size(self, tmp_path):
        source_path = tmp_path / "tmul.s3"
        source_path.write_text(
            "fn multiply(left: f64, right: f64) -> f64:\n"
            "    return left * right\n\n"
            "fn main() -> f64:\n    return multiply(6.0, 7.0)\n",
            encoding="utf-8",
        )
        case = replace(
            _case(),
            benchmark_id="test.s3-emulator-tmul.v1",
            implementation="s3",
            adapter="s3-emulator",
            execution_mode="emulator",
            optimization_mode="O0",
            expected_checksum="42.0",
            source=source_path,
        )

        adapter = S3EmulatorAdapter()
        artifact = adapter.build(case, tmp_path / "build")

        assert artifact.artifact_size_bytes is None
        assert "assembly_bytes" not in artifact.artifact_metrics
        assert artifact.artifact_metrics["assembly_instruction_count"] > 0
        assert any("opcode TMUL" in note for note in artifact.notes)
        assert any(
            instruction.opcode.value == "TMUL"
            for function in artifact.payload.assembly.functions
            for block in function.blocks
            for instruction in block.instructions
        )

        observation = adapter.execute(case, artifact, loops=1, timeout_seconds=1.0)
        assert observation.checksum == "42.0"


# ---------------------------------------------------------------------------
# S3NativeAdapter: verify subprocess counting via monkeypatch
# ---------------------------------------------------------------------------

class TestS3NativeSubprocessCount:
    """Directly verify that S3NativeAdapter.execute() calls run_command
    exactly once, regardless of the loops parameter."""

    def test_execute_calls_run_command_exactly_once(self, monkeypatch, tmp_path):
        """Even if loops=100 is passed, only 1 subprocess must be launched."""
        call_count = 0

        def counting_run_command(args, cwd, timeout_seconds):
            nonlocal call_count
            call_count += 1
            return CommandResult(
                tuple(args), "program returned: 42\n", "", 0, False, False, 1000,
            )

        monkeypatch.setattr(
            "benchmarks.s3bench.adapters.run_command",
            counting_run_command,
        )

        adapter = S3NativeAdapter()
        case = _case()
        artifact = BuildArtifact(path=tmp_path / "fake_elf")

        # Call with loops=100 — the adapter must ignore it and call once
        obs = adapter.execute(case, artifact, loops=100, timeout_seconds=30.0)

        assert call_count == 1, (
            f"S3NativeAdapter.execute(loops=100) spawned {call_count} processes; "
            f"expected exactly 1"
        )
        assert obs.checksum == "42"

    def test_execute_with_loops_1_calls_run_command_once(self, monkeypatch, tmp_path):
        """Baseline: loops=1 should also be exactly 1 subprocess."""
        call_count = 0

        def counting_run_command(args, cwd, timeout_seconds):
            nonlocal call_count
            call_count += 1
            return CommandResult(
                tuple(args), "program returned: 42\n", "", 0, False, False, 1000,
            )

        monkeypatch.setattr(
            "benchmarks.s3bench.adapters.run_command",
            counting_run_command,
        )

        adapter = S3NativeAdapter()
        case = _case()
        artifact = BuildArtifact(path=tmp_path / "fake_elf")

        obs = adapter.execute(case, artifact, loops=1, timeout_seconds=30.0)

        assert call_count == 1
        assert obs.checksum == "42"


# ---------------------------------------------------------------------------
# Regression guard: harness + process adapter end-to-end
# ---------------------------------------------------------------------------

class TestHarnessProcessScopedRegression:
    """Full harness integration: process-scoped adapter with calibration attempt."""

    def test_calibration_does_not_multiply_forks(self, tmp_path):
        """When loops is not specified, the harness must not calibrate
        a process-scoped adapter — it should force loops=1 immediately."""
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        result = harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=1,
            samples=3,
            # No loops specified — calibration would normally run
            target_sample_ns=200_000_000,
        )

        assert result["loops_per_sample"] == 1
        assert result["measurement_scope"] == "process"
        # verification(1) + warmups(1) + samples(3) = 5 total calls
        assert adapter.subprocess_call_count == 5

    def test_maximum_subprocess_count_per_sample_is_one(self, tmp_path):
        """Verify at most 1 subprocess per sample for process-scoped adapters."""
        adapter = ProcessCountingAdapter(
            measurement_scope=MEASUREMENT_SCOPE_PROCESS,
            process_launches_per_sample=1,
        )
        harness = BenchmarkHarness({"fake": adapter}, repository_root=tmp_path)

        harness.run_case(
            _case(),
            build_dir=tmp_path / "build",
            warmups=0,
            samples=10,
        )

        # 1 verification + 10 samples = 11 total
        assert adapter.subprocess_call_count == 11
        # Each execute() call must have received loops=1
        assert all(loop == 1 for loop in adapter.loops_received)
"""Tests for the process-per-loop explosion fix in s3bench."""
