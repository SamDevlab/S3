"""Bounded deterministic memory-transform fuzz and write-reordering probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3 import run_source  # noqa: E402
from bootstrap.s3.ir_emulator import execute_ir  # noqa: E402
from bootstrap.s3.memory_value_availability import (  # noqa: E402
    analyze_memory_value_availability,
    analyze_repeated_load_availability,
)
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.ssa import SSABuilder  # noqa: E402
from tools.s3_memory_availability_experiment import forward_available_stores  # noqa: E402
from tools.s3_memory_repeated_load_experiment import forward_available_loads  # noqa: E402


SEEDS = tuple(range(3100, 3112))
DEFAULT_OUTPUT = (
    ROOT
    / "reports/s3-1.10-memory-intelligence-value-locality/evidence"
    / "EXP-S3-110-FUZZ-001.json"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_source(seed: int, *, reverse_writes: bool) -> str:
    rng = random.Random(seed)
    length = 4
    first = rng.randrange(length)
    second = (first + rng.randrange(1, length)) % length
    initial = [rng.randint(-12, 12) for _ in range(length)]
    first_value = rng.randint(-12, 12)
    second_value = rng.randint(-12, 12)
    loop_limit = rng.randint(0, 3)
    writes = [
        f"    values[{first}] = {first_value}\n",
        f"    values[{second}] = {second_value}\n",
    ]
    if reverse_writes:
        writes.reverse()
    return (
        "fn main() -> tryte:\n"
        f"    mut values: tryte[{length}] = [{', '.join(map(str, initial))}]\n"
        + "".join(writes)
        + f"    mut earlier: tryte = values[{first}]\n"
        + "    mut counter: tryte = 0\n"
        + f"    mut limit: tryte = {loop_limit}\n"
        + "    while counter < limit:\n"
        + "        counter += 1\n"
        + f"    return earlier + values[{first}] + values[{second}] + counter\n"
    )


def _case(seed: int, reverse_writes: bool) -> dict[str, object]:
    source = generate_source(seed, reverse_writes=reverse_writes)
    source_bytes = source.encode("utf-8")
    expected = run_source(source)
    o0 = compile_source(source, OptimizationLevel.O0)
    o1 = compile_source(source, OptimizationLevel.O1)
    o0_ir, _ = o0.require_ordinary_artifacts()
    o1_ir, _ = o1.require_ordinary_artifacts()
    baseline = execute_ir(o1_ir)
    if execute_ir(o0_ir) != baseline or baseline != expected:
        raise AssertionError("O0/O1/reference execution differs")

    ssa_function = SSABuilder.build_function(o1_ir.functions[0])
    store_report = analyze_memory_value_availability(ssa_function)
    load_report = analyze_repeated_load_availability(ssa_function)
    if store_report.forwardable_load_count == 0:
        raise AssertionError("generator did not produce a proven STORE-to-LOAD site")
    if load_report.cross_block_candidate_count == 0:
        raise AssertionError("generator did not produce a proven cross-block LOAD site")

    store_candidate, store_count = forward_available_stores(o1_ir)
    load_candidate, load_count = forward_available_loads(o1_ir)
    if store_count != store_report.forwardable_load_count:
        raise AssertionError("STORE-to-LOAD transform count differs from proof report")
    if load_count != load_report.cross_block_candidate_count:
        raise AssertionError("LOAD-to-LOAD transform count differs from proof report")
    if execute_ir(store_candidate) != expected:
        raise AssertionError("STORE-to-LOAD candidate changed result")
    if execute_ir(load_candidate) != expected:
        raise AssertionError("LOAD-to-LOAD candidate changed result")

    return {
        "seed": seed,
        "write_order": "reversed" if reverse_writes else "forward",
        "source_sha256": _sha256(source_bytes),
        "expected_result": expected,
        "o0_o1_reference_agreement": True,
        "store_to_load_sites": store_report.forwardable_load_count,
        "load_to_load_cross_block_sites": load_report.cross_block_candidate_count,
        "store_to_load_transformed": store_count,
        "load_to_load_transformed": load_count,
        "transformed_outputs_match": True,
    }


def run_corpus() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    paired_results: dict[int, dict[str, int]] = {}
    for seed in SEEDS:
        for reverse in (False, True):
            try:
                row = _case(seed, reverse)
                rows.append(row)
                paired_results.setdefault(seed, {})[row["write_order"]] = row[
                    "expected_result"
                ]
            except Exception as exc:
                failures.append(
                    {
                        "seed": seed,
                        "write_order": "reversed" if reverse else "forward",
                        "failure": f"{type(exc).__name__}: {exc}",
                    }
                )
    for seed, outputs in sorted(paired_results.items()):
        if len(outputs) == 2 and outputs["forward"] != outputs["reversed"]:
            failures.append(
                {
                    "seed": seed,
                    "failure": "independent distinct-index writes are order-dependent",
                }
            )
    return {
        "schema_version": "1.0.0",
        "experiment_id": "EXP-S3-110-FUZZ-001",
        "scope": "bounded typed array writes, exact-index reads, loop continuation, cross-block reuse, independent-store reordering",
        "seed_start": SEEDS[0],
        "seed_end_exclusive": SEEDS[-1] + 1,
        "cases_expected": len(SEEDS) * 2,
        "cases_completed": len(rows),
        "failures": failures,
        "paired_metamorphic_cases": len(paired_results),
        "passed": not failures and len(rows) == len(SEEDS) * 2,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_corpus()
    encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={_sha256(encoded)}")
    print(
        f"CASES={result['cases_completed']}/{result['cases_expected']} "
        f"METAMORPHIC_PAIRS={result['paired_metamorphic_cases']} "
        f"FAILURES={len(result['failures'])} PASS={result['passed']}"
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
