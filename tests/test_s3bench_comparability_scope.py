"""Causal tests for the measurement_scope comparability fix.

These tests prove that:
1. A kernel-scoped result (C, loops_per_sample>1) and a process-scoped
   result (S3 native, loops_per_sample=1) are NEVER placed in the same
   comparison group, NEVER share a reference, and NEVER produce a
   normalized_ratio between them.
2. Two process-scoped S3 native results (O0 and O1) DO share a
   comparison group and use a single deterministic canonical reference
   (O0), with no A->B / B->A cycle.
3. The comparison document preserves execution_mode, optimization_mode
   and measurement_scope on every entry.
4. Each scope group has exactly ONE canonical reference; all other rows
   reference that same row.
5. The reference choice is stable regardless of input order.
6. The exported JSON (--output-json) carries the SAME final document as
   stdout, including "comparisons".

Background: an earlier revision of the report normalized S3 native
process timing (one fork/exec/ELF load per sample, loops=1) against
C kernel timing (internal loop, loops>>1) and produced a misleading
"normalized_ratio". That cross-scope normalization is forbidden by the
benchmark methodology rules.
"""

from __future__ import annotations

import io
import pytest

pytestmark = pytest.mark.s3_benchmark
import json
import random
from contextlib import redirect_stdout
from pathlib import Path

from benchmarks.s3bench import compare_results
from benchmarks.s3bench.report import normalized_rows, render_performance_report


def _result(
    benchmark_id: str,
    implementation: str,
    execution_mode: str,
    optimization_mode: str,
    *,
    measurement_scope: str,
    median: int,
    loops: int,
    process_launches_per_sample: int,
    classification: str = "COMPARABLE",
    suite: str = "portable",
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "campaign": "1.17-1.19",
        "benchmark_id": benchmark_id,
        "input_id": "default",
        "workload_version": "1.0.0",
        "category": "runtime",
        "suite": suite,
        "implementation": implementation,
        "execution_mode": execution_mode,
        "optimization_mode": optimization_mode,
        "phase": "end_to_end",
        "status": "measured",
        "median_ns": median,
        "loops_per_sample": loops,
        "measurement_scope": measurement_scope,
        "process_launches_per_sample": process_launches_per_sample,
        "coefficient_of_variation": 0.01,
        "artifact_size_bytes": 10,
        "comparability_classification": classification,
        "repository_sha": "a" * 40,
        "repository_dirty": False,
        "operating_system": "Linux",
        "architecture": "x86_64",
        "runner_type": "controlled-linux",
        "warmup_count": 3,
        "sample_count": 15,
        "compiler_name": implementation,
        "compiler_version": "test",
        "compiler_flags": [],
        "input_size": 3,
        "expected_checksum": "42",
        "observed_checksum": "42",
        "correctness_status": "verified",
        "raw_durations_ns": [median],
        "mean_ns": float(median),
        "minimum_ns": median,
        "maximum_ns": median,
        "standard_deviation_ns": 0.0,
        "percentile_95_ns": median,
        "compile_duration_ns": 100,
        "link_duration_ns": 100,
        "startup_duration_ns": None,
        "kernel_duration_ns": None,
        "end_to_end_duration_ns": None,
        "peak_memory_bytes": None,
        "artifact_metrics": {"source_bytes": 10},
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "notes": [],
        "python_version": "3.11.9",
        "cpu_model": "test",
        "logical_cpu_count": 8,
        "physical_cpu_count": None,
        "total_memory_bytes": None,
        "linker": None,
        "calibration_attempts": 0,
    }


# ---------------------------------------------------------------------------
# Test 1: C kernel (loops=1000) vs S3 native process (loops=1) — cross-scope
# ---------------------------------------------------------------------------

def test_c_kernel_vs_s3_native_process_never_shares_reference_or_ratio():
    """The canonical causal cross-scope test.

    Result A: implementation=c, measurement_scope=kernel, loops=1000.
    Result B: implementation=s3, execution_mode=native,
              measurement_scope=process, loops=1.

    After the scope-aware fix, B must NOT receive A as a reference, no
    normalized_ratio may exist between A and B, and the two must not be
    in the same comparable group.
    """
    a = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=1_000_000, loops=1000,
        process_launches_per_sample=1,
    )
    a_peer = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=2_000_000, loops=1000,
        process_launches_per_sample=1,
    )
    b = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O1",
        measurement_scope="process", median=9_000_000_000, loops=1,
        process_launches_per_sample=1,
    )
    comparisons = compare_results([a, a_peer, b], reference_implementation="c")

    indexed = {
        (c["implementation"], c["optimization_mode"], c["measurement_scope"]): c
        for c in comparisons
    }
    a_row = indexed[("c", "O2", "kernel")]
    b_row = indexed[("s3", "O1", "process")]

    # B must NOT receive A as a reference
    assert b_row["reference_implementation"] is None, (
        f"B (s3/process) must not reference A (c/kernel); "
        f"got reference_implementation={b_row['reference_implementation']!r}"
    )
    assert b_row["normalized_ratio"] is None
    assert a_row["measurement_scope"] != b_row["measurement_scope"]
    assert b_row["reference_measurement_scope"] is None
    # A (C O2) references the kernel canonical (C O0); never B (s3/process).
    assert a_row["reference_implementation"] == "c"
    assert a_row["reference_measurement_scope"] == "kernel"
    assert a_row["normalized_ratio"] is not None


def test_normalized_rows_never_cross_scope():
    """normalized_rows must also refuse to normalize process vs kernel."""
    a = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=1_000_000, loops=1000,
        process_launches_per_sample=1,
    )
    a_peer = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=2_000_000, loops=1000,
        process_launches_per_sample=1,
    )
    b = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O1",
        measurement_scope="process", median=9_000_000_000, loops=1,
        process_launches_per_sample=1,
    )
    rows = normalized_rows([a, a_peer, b])
    indexed = {
        (r["implementation"], r["optimization_mode"], r["measurement_scope"]): r
        for r in rows
    }
    a_row = indexed[("c", "O2", "kernel")]
    b_row = indexed[("s3", "O1", "process")]
    assert b_row["normalized_ratio"] is None
    assert b_row["reference_implementation"] is None
    assert b_row["reference_measurement_scope"] is None
    assert a_row["reference_implementation"] == "c"
    assert a_row["reference_measurement_scope"] == "kernel"
    assert a_row["normalized_ratio"] is not None


def test_markdown_splits_kernel_and_process_sections():
    a = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=1_000_000, loops=1000,
        process_launches_per_sample=1,
    )
    b = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O1",
        measurement_scope="process", median=9_000_000_000, loops=1,
        process_launches_per_sample=1,
    )
    report = render_performance_report([a, b], raw_result_path="raw.json")
    assert "## KERNEL MEASUREMENTS" in report
    assert "## PROCESS/STARTUP MEASUREMENTS" in report
    process_section = report.split("## PROCESS/STARTUP MEASUREMENTS", 1)[1]
    process_section = process_section.split("## Portable suite", 1)[0]
    assert "duration per process/sample" in process_section or "per-process" in process_section.lower()


# ---------------------------------------------------------------------------
# Test 2: Single canonical reference per scope group (kernel)
# ---------------------------------------------------------------------------

def test_kernel_group_has_one_canonical_reference_c_o0():
    """Kernel group: C O0 is the canonical reference.

    With median_ns_per_loop = 10 for C O0 and 2 for C O2:
      - C O0 references itself, ratio = 1.0
      - C O2 references C O0, ratio = 0.2
      - C O2 never references itself.
    """
    c_o0 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=10_000, loops=1000,
        process_launches_per_sample=1,
    )
    c_o2 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=2_000, loops=1000,
        process_launches_per_sample=1,
    )
    comparisons = compare_results([c_o0, c_o2], reference_implementation="c")
    indexed = {
        (c["implementation"], c["optimization_mode"]): c for c in comparisons
    }
    o0_row = indexed[("c", "O0")]
    o2_row = indexed[("c", "O2")]

    # C O0 is the canonical reference -> self-reference, ratio 1.0
    assert o0_row["reference_implementation"] == "c"
    assert o0_row["reference_optimization_mode"] == "O0"
    assert o0_row["normalized_ratio"] == 1.0
    # C O2 references C O0, ratio 0.2 (2 / 10), never references itself
    assert o2_row["reference_implementation"] == "c"
    assert o2_row["reference_optimization_mode"] == "O0", (
        f"C O2 must reference C O0, got {o2_row['reference_optimization_mode']!r}"
    )
    assert o2_row["normalized_ratio"] == 0.2, (
        f"C O2 ratio must be 0.2, got {o2_row['normalized_ratio']!r}"
    )
    # No self-reference for O2: its reference's optimization differs from its own
    assert o2_row["reference_optimization_mode"] != o2_row["optimization_mode"]


def test_kernel_group_rust_zig_use_same_canonical_c_o0():
    """All non-canonical items in the kernel group reference the SAME row."""
    c_o0 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=10_000, loops=1000,
        process_launches_per_sample=1,
    )
    rust = _result(
        "runtime.scalar.accumulate.v1", "rust", "native", "opt-level=2",
        measurement_scope="kernel", median=3_000, loops=1000,
        process_launches_per_sample=1,
    )
    comparisons = compare_results([c_o0, rust], reference_implementation="c")
    indexed = {
        (c["implementation"], c["optimization_mode"]): c for c in comparisons
    }
    c_row = indexed[("c", "O0")]
    rust_row = indexed[("rust", "opt-level=2")]
    # Both reference the canonical (c/O0)
    assert c_row["reference_implementation"] == "c"
    assert c_row["reference_optimization_mode"] == "O0"
    assert rust_row["reference_implementation"] == "c"
    assert rust_row["reference_optimization_mode"] == "O0"
    assert c_row["normalized_ratio"] == 1.0
    assert rust_row["normalized_ratio"] == 0.3  # 3 / 10


# ---------------------------------------------------------------------------
# Test 3: Single canonical reference per scope group (process)
# ---------------------------------------------------------------------------

def test_process_group_has_one_canonical_reference_s3_o0():
    """Process group: S3 native O0 is the canonical reference.

    With duration 1000 for O0 and 800 for O1:
      - O0 references itself, ratio = 1.0
      - O1 references O0, ratio = 0.8
      - No A->B / B->A cycle.
    """
    o0 = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O0",
        measurement_scope="process", median=1000, loops=1,
        process_launches_per_sample=1,
    )
    o1 = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O1",
        measurement_scope="process", median=800, loops=1,
        process_launches_per_sample=1,
    )
    comparisons = compare_results([o0, o1], reference_implementation="c")
    indexed = {
        (c["implementation"], c["optimization_mode"]): c for c in comparisons
    }
    o0_row = indexed[("s3", "O0")]
    o1_row = indexed[("s3", "O1")]

    # O0 is the canonical reference (c not present; fallback picks O0,
    # the lowest optimization rank).
    assert o0_row["reference_implementation"] == "s3"
    assert o0_row["reference_optimization_mode"] == "O0"
    assert o0_row["normalized_ratio"] == 1.0
    # O1 references O0, ratio 0.8 (800 / 1000), no cycle
    assert o1_row["reference_implementation"] == "s3"
    assert o1_row["reference_optimization_mode"] == "O0", (
        f"O1 must reference O0, got {o1_row['reference_optimization_mode']!r}"
    )
    assert o1_row["normalized_ratio"] == 0.8
    # Cycle guard: O0's reference is NOT O1
    assert o0_row["reference_optimization_mode"] != "O1"
    # Canonical reference is unique: both rows reference the same opt
    assert o0_row["reference_optimization_mode"] == o1_row["reference_optimization_mode"]


# ---------------------------------------------------------------------------
# Test 4: Reference choice is stable regardless of input order
# ---------------------------------------------------------------------------

def test_reference_choice_is_order_independent():
    """Shuffling the input list must not change the canonical reference."""
    c_o0 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=10_000, loops=1000,
        process_launches_per_sample=1,
    )
    c_o2 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=2_000, loops=1000,
        process_launches_per_sample=1,
    )
    base = [c_o0, c_o2]
    reference_first = compare_results(base, reference_implementation="c")
    rng = random.Random(1234)
    for _ in range(20):
        shuffled = list(base)
        rng.shuffle(shuffled)
        got = compare_results(shuffled, reference_implementation="c")
        # Same comparisons (the output is sorted internally)
        assert got == reference_first, "compare_results must be order-independent"
    # Canonical is always C O0
    o0_row = next(c for c in reference_first if c["optimization_mode"] == "O0")
    o2_row = next(c for c in reference_first if c["optimization_mode"] == "O2")
    assert o0_row["reference_optimization_mode"] == "O0"
    assert o0_row["normalized_ratio"] == 1.0
    assert o2_row["reference_optimization_mode"] == "O0"
    assert o2_row["normalized_ratio"] == 0.2


# ---------------------------------------------------------------------------
# Test 5: Export — output-json carries the SAME final document as stdout
# ---------------------------------------------------------------------------

def test_cli_export_json_contains_comparisons_matching_stdout(tmp_path):
    """The exported JSON file must contain BOTH results and comparisons,
    and must equal the document printed to stdout."""
    from benchmarks.s3bench import cli as s3cli
    from benchmarks.s3bench.core import write_json

    c_o0 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=10_000, loops=1000,
        process_launches_per_sample=1,
    )
    c_o2 = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O2",
        measurement_scope="kernel", median=2_000, loops=1000,
        process_launches_per_sample=1,
    )
    results = [c_o0, c_o2]
    comparisons = compare_results(results, reference_implementation="c")
    out_json = tmp_path / "out.json"
    write_json(out_json, results, comparisons=comparisons)

    on_disk = json.loads(out_json.read_text(encoding="utf-8"))
    assert "comparisons" in on_disk, "exported JSON must include 'comparisons'"
    assert len(on_disk["comparisons"]) == 2, "comparisons must not be empty"
    # The enriched fields must be preserved on disk
    for c in on_disk["comparisons"]:
        assert "execution_mode" in c
        assert "optimization_mode" in c
        assert "measurement_scope" in c
        assert "reference_implementation" in c
        assert "reference_execution_mode" in c
        assert "reference_optimization_mode" in c
        assert "reference_measurement_scope" in c
    # The stdout document must match what is on disk, including schema_version
    from benchmarks.s3bench.core import BENCHMARK_SCHEMA_VERSION
    stdout_doc = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "results": results,
        "comparisons": comparisons,
    }
    assert json.loads(json.dumps(on_disk, sort_keys=True)) == json.loads(
        json.dumps(stdout_doc, sort_keys=True)
    ), "output-json must equal the final stdout document"


def test_cli_main_writes_comparisons_to_output_json(tmp_path, monkeypatch):
    """End-to-end: `python tools/s3bench.py --output-json` must persist
    comparisons and the on-disk file must equal the stdout payload."""
    from benchmarks.s3bench import cli as s3cli

    out_json = tmp_path / "pilot.json"
    argv = [
        "--manifest", str(Path(__file__).resolve().parents[1] / "benchmarks" / "manifests" / "s3bench-1.0.0.json"),
        "--benchmark", "runtime.scalar.accumulate.v1",
        "--implementation", "s3", "--mode", "emulator", "--optimization", "O0",
        "--warmups", "0", "--samples", "1",
        "--output-json", str(out_json),
        "--timeout", "60",
    ]
    buf = io.StringIO()
    rc = -1
    with redirect_stdout(buf):
        rc = s3cli.main(argv)
    assert rc == 0
    on_disk = json.loads(out_json.read_text(encoding="utf-8"))
    stdout_doc = json.loads(buf.getvalue())
    assert "comparisons" in on_disk, "on-disk JSON must include comparisons"
    assert len(on_disk["comparisons"]) >= 1, "on-disk comparisons must not be empty"
    # The disk file and stdout must carry the same results/comparisons
    assert json.dumps(on_disk, sort_keys=True) == json.dumps(stdout_doc, sort_keys=True), (
        "output-json must equal the final stdout document"
    )


# ---------------------------------------------------------------------------
# Test 6: Cross-scope isolation is absolute
# ---------------------------------------------------------------------------

def test_kernel_never_uses_process_reference_and_vice_versa():
    """A kernel result never references a process row, and a process
    result never references a kernel row, even when both live in the same
    benchmark_id/input_id/phase group."""
    c_kernel = _result(
        "runtime.scalar.accumulate.v1", "c", "native", "O0",
        measurement_scope="kernel", median=10_000, loops=1000,
        process_launches_per_sample=1,
    )
    s3_process = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O0",
        measurement_scope="process", median=1000, loops=1,
        process_launches_per_sample=1,
    )
    comparisons = compare_results([c_kernel, s3_process], reference_implementation="c")
    for c in comparisons:
        if c["measurement_scope"] == "kernel":
            assert c["reference_measurement_scope"] in (None, "kernel"), (
                f"kernel row must not reference process: {c}"
            )
        elif c["measurement_scope"] == "process":
            assert c["reference_measurement_scope"] in (
                None, "process",
            ), f"process row must not reference kernel, got {c}"


# ---------------------------------------------------------------------------
# Test 7: NOT_COMPARABLE when no same-scope peer exists
# ---------------------------------------------------------------------------

def test_isolated_process_result_is_not_comparable_without_same_scope_peer():
    """A lone process result with no other process peer must be
    NOT_COMPARABLE, with normalized_ratio=null and reference_implementation=null.
    """
    solo = _result(
        "runtime.scalar.accumulate.v1", "s3", "native", "O1",
        measurement_scope="process", median=9_000_000_000, loops=1,
        process_launches_per_sample=1,
        classification="NOT_COMPARABLE",
    )
    comparisons = compare_results([solo], reference_implementation="c")
    row = comparisons[0]
    assert row["measurement_scope"] == "process"
    assert row["reference_implementation"] is None
    assert row["reference_measurement_scope"] is None
    assert row["normalized_ratio"] is None
    assert row["comparability_classification"] == "NOT_COMPARABLE"
