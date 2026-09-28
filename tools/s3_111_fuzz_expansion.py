"""Deterministic expanded memory-transform fuzz and alias metamorphic checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3 import run_source
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.memory_value_availability import (
    analyze_memory_value_availability,
    analyze_repeated_load_availability,
)
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder
from tools.s3_memory_availability_experiment import forward_available_stores
from tools.s3_memory_repeated_load_experiment import forward_available_loads

SEEDS = tuple(range(6110, 6160))
EXPERIMENT_ID = "EXP-S3-111-FUZZ-002"
DEFAULT_OUTPUT = (
    ROOT
    / "reports/s3-1.11-adaptive-optimization-machine-intelligence/evidence/control-832b"
    / f"{EXPERIMENT_ID}.json"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def generate_source(seed: int, *, reverse_writes: bool) -> tuple[str, dict[str, int]]:
    rng = random.Random(seed)
    length = 2 + (seed - SEEDS[0]) % 15
    first = rng.randrange(length)
    second = (first + rng.randrange(1, length)) % length
    initial = [rng.randint(-12, 12) for _ in range(length)]
    first_value = rng.randint(-16, 16)
    second_value = rng.randint(-16, 16)
    loop_limit = (seed - SEEDS[0]) % 9
    writes = [
        f"    values[{first}] = {first_value}\n",
        f"    values[{second}] = {second_value}\n",
    ]
    if reverse_writes:
        writes.reverse()
    source = (
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
    return source, {
        "array_length": length,
        "first_index": first,
        "second_index": second,
        "loop_limit": loop_limit,
    }


def _case(seed: int, reverse_writes: bool) -> dict[str, object]:
    source, shape = generate_source(seed, reverse_writes=reverse_writes)
    expected = run_source(source)
    o0, o1 = (
        compile_source(source, level)
        for level in (OptimizationLevel.O0, OptimizationLevel.O1)
    )
    o0_ir, _ = o0.require_ordinary_artifacts()
    o1_ir, _ = o1.require_ordinary_artifacts()
    if execute_ir(o0_ir) != expected or execute_ir(o1_ir) != expected:
        raise AssertionError("O0/O1/reference execution differs")

    ssa_function = SSABuilder.build_function(o1_ir.functions[0])
    store_report = analyze_memory_value_availability(ssa_function)
    load_report = analyze_repeated_load_availability(ssa_function)
    if store_report.forwardable_load_count == 0 or load_report.cross_block_candidate_count == 0:
        raise AssertionError("generated case lost required proven transform sites")

    store_candidate, store_count = forward_available_stores(o1_ir)
    load_candidate, load_count = forward_available_loads(o1_ir)
    if store_count != store_report.forwardable_load_count:
        raise AssertionError("STORE-to-LOAD transform count disagrees with proof report")
    if load_count != load_report.cross_block_candidate_count:
        raise AssertionError("LOAD-to-LOAD transform count disagrees with proof report")
    if execute_ir(store_candidate) != expected or execute_ir(load_candidate) != expected:
        raise AssertionError("transformed output differs from reference")

    return {
        "seed": seed,
        "write_order": "reversed" if reverse_writes else "forward",
        **shape,
        "source_sha256": _sha(source.encode("utf-8")),
        "expected_result": expected,
        "reference_o0_o1_agree": True,
        "store_to_load_sites": store_report.forwardable_load_count,
        "load_to_load_sites": load_report.cross_block_candidate_count,
        "transformed_outputs_match": True,
    }


def _same_storage_order_control(seed: int) -> dict[str, object]:
    rng = random.Random(seed ^ 0x5A17)
    length = 2 + (seed - SEEDS[0]) % 15
    index = rng.randrange(length)
    initial = [rng.randint(-12, 12) for _ in range(length)]
    first_value, second_value = -7, 9
    def source(first_write: int, second_write: int) -> str:
        return (
            "fn main() -> tryte:\n"
            f"    mut values: tryte[{length}] = [{', '.join(map(str, initial))}]\n"
            + f"    values[{index}] = {first_write}\n"
            + f"    values[{index}] = {second_write}\n"
            + f"    return values[{index}]\n"
        )

    forward_source = source(first_value, second_value)
    reverse_source = source(second_value, first_value)
    forward, reverse = run_source(forward_source), run_source(reverse_source)
    if forward == reverse:
        raise AssertionError("same-storage write order unexpectedly appeared independent")
    return {
        "seed": seed,
        "array_length": length,
        "shared_index": index,
        "forward_result": forward,
        "reversed_result": reverse,
        "order_change_observed": True,
    }


def run_corpus() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    pairs: dict[int, dict[str, dict[str, object]]] = {}
    alias_controls: list[dict[str, object]] = []
    for seed in SEEDS:
        for reverse in (False, True):
            order = "reversed" if reverse else "forward"
            try:
                row = _case(seed, reverse)
                cases.append(row)
                pairs.setdefault(seed, {})[order] = row
            except Exception as exc:
                failures.append({"seed": seed, "write_order": order, "failure": f"{type(exc).__name__}: {exc}"})
        try:
            forward, reverse = pairs.get(seed, {}).get("forward"), pairs.get(seed, {}).get("reversed")
            if forward is not None and reverse is not None and forward["expected_result"] != reverse["expected_result"]:
                raise AssertionError("distinct-index independent writes changed result when reordered")
            alias_controls.append(_same_storage_order_control(seed))
        except Exception as exc:
            failures.append({"seed": seed, "failure": f"{type(exc).__name__}: {exc}"})

    return {
        "schema": "s3-1.11-bounded-memory-fuzz-v1",
        "experiment_id": EXPERIMENT_ID,
        "source_revision": _git("rev-parse", "HEAD"),
        "source_tree": _git("rev-parse", "HEAD^{tree}"),
        "python": platform.python_version(),
        "generator_sha256": _sha(Path(__file__).read_bytes()),
        "seed_start": SEEDS[0],
        "seed_end_inclusive": SEEDS[-1],
        "cases_expected": len(SEEDS) * 2,
        "cases_completed": len(cases),
        "array_lengths_covered": sorted({row["array_length"] for row in cases}),
        "loop_limits_covered": sorted({row["loop_limit"] for row in cases}),
        "metamorphic_independent_write_pairs": len(pairs),
        "same_storage_order_controls": len(alias_controls),
        "same_storage_controls_proved_order_sensitive": sum(row["order_change_observed"] for row in alias_controls),
        "failures": failures,
        "cases": cases,
        "same_storage_controls": alias_controls,
        "passed": (
            not failures
            and len(cases) == len(SEEDS) * 2
            and len(pairs) == len(SEEDS)
            and len(alias_controls) == len(SEEDS)
        ),
        "scope": [
            "bounded tryte arrays with lengths 2 through 16",
            "distinct-index writes in both statement orders",
            "loop limits 0 through 8",
            "O0/O1/reference and STORE-to-LOAD plus cross-block LOAD-to-LOAD transform agreement",
            "same-storage reversed-write controls must remain order-sensitive",
        ],
        "limitations": [
            "This is deterministic parameter fuzz over one small source grammar, not general language fuzzing.",
            "It does not exercise native execution, floating point, references, calls, or concurrency.",
        ],
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
    print(f"OUTPUT_SHA256={_sha(encoded)}")
    print(
        f"CASES={result['cases_completed']}/{result['cases_expected']} "
        f"METAMORPHIC_PAIRS={result['metamorphic_independent_write_pairs']} "
        f"ALIAS_CONTROLS={result['same_storage_controls_proved_order_sensitive']} "
        f"FAILURES={len(result['failures'])} PASS={result['passed']}"
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
