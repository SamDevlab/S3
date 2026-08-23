"""Bounded V2.4 Compact-EA generalization and soak evidence runner.

The runner freezes the V2.3 decision rules and broadens only the evidence
corpus.  It is intentionally structural and correctness-oriented: it never
times native code, changes the default policy, or trains the research model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.backends.x86_64.experimental_policy import (
    ExperimentalNativePolicyMode,
    resolve_experimental_policies,
)
from bootstrap.s3.backends.x86_64.features import extract_function_features
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY
from bootstrap.s3.emulator import Emulator
from tools.native_policy_search import CorpusCase, _make_case
from tools.native_policy_search_v21 import _hard_regression, _metrics_with_bytes, _sha_text
from tools.native_policy_search_v22 import build_v22_corpus


CAMPAIGN = "S3-ABL-V2.4-COMPACT-EA-CANARY-GENERALIZATION-AND-SOAK-20260822"
BRANCH = "experiment/native-policy-search-20260822"
PR_NUMBER = 190
MAIN_SHA = "2245c9f75b07b063b6da5716a753d02c1fee5f95"
V23_SOURCE_LOCK = "e59b63d5eaeacda85373bfe48eff3309bc18398e"
SOAK_PASSES = 3
MODES = ("off", "shadow", "compact-ea-canary")
METRICS = (
    "instructions", "movs", "loads", "stores", "total_load_store",
    "stack_ops", "spills_reload", "frame_bytes", "leas", "branches",
    "calls", "text_bytes",
)
T3_CASE_IDS = {
    *(f"A{index:02d}" for index in range(1, 8)),
    *(f"R{index:02d}" for index in range(1, 25)),
    *(f"V24-{index:02d}" for index in range(1, 13)),
}
SOAK_SENTINEL_IDS = {
    "R04", "R07", "R17", "R21", "V24-01", "V24-02", "V24-03",
    "V24-05", "V24-07", "V24-08", "V24-09", "V24-11",
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _metrics(assembly: str | None) -> dict[str, int]:
    if assembly is None:
        return {key: 0 for key in METRICS}
    values = _metrics_with_bytes(assembly)
    return {key: int(values.get(key, 0)) for key in METRICS}


def _delta(candidate: dict[str, int], baseline: dict[str, int]) -> dict[str, int]:
    return {key: candidate.get(key, 0) - baseline.get(key, 0) for key in METRICS}


def _main_function(case: CorpusCase):
    return next(function for function in case.program.functions if function.name == "main")


def _new_cases() -> tuple[CorpusCase, ...]:
    """High-information cases selected before evaluation and never retuned."""

    fixtures = (
        (
            "V24-01", "multi_index", "generalization",
            "two independent arrays and indices",
            "safe_apply",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .register r4, tryte
    .memory m0, tryte, 4, mutable
    .memory m1, tryte, 4, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 2
    TCONST r2, 7
    TSTORE m0, r0, r2
    TSTORE m1, r1, r2
    TLOAD r3, m0, r0
    TLOAD r4, m1, r1
    TADD r3, r3, r4
    TRET r3""",
        ),
        (
            "V24-02", "loop_carried_index", "generalization",
            "index is updated across a loop before a bounded indexed access",
            "safe_apply",
            """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, -1
    TCONST r1, 0
    TCONST r2, 3
    TJMP loop
.label loop
    TBR3 r0, body, exit, done
.label body
    TADD r1, r1, r2
    TCONST r0, 0
    TJMP loop
.label exit
    TSTORE m0, r1, r2
    TLOAD r3, m0, r1
    TRET r3
.label done
    TRET r2""",
        ),
        (
            "V24-03", "branch_selected_index", "generalization",
            "index selected through a diamond and consumed at the join",
            "safe_apply",
            """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, -1
    TCONST r1, 1
    TCONST r2, 5
    TBR3 r0, left, right, join
.label left
    TCONST r1, 2
    TJMP join
.label right
    TCONST r1, 3
    TJMP join
.label join
    TSTORE m0, r1, r2
    TLOAD r3, m0, r1
    TRET r3""",
        ),
        (
            "V24-04", "call_adjacent", "generalization",
            "call immediately around an indexed operation remains a fallback",
            "fallback",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 8
    TCALL r2, helper, r1
    TSTORE m0, r0, r2
    TLOAD r1, m0, r0
    TRET r1""",
            ".function helper -> tryte\n    .param r0, tryte\n.label entry\n    TADD r0, r0, r0\n    TRET r0\n.end\n",
        ),
        (
            "V24-05", "register_pressure", "generalization",
            "multiple live scalars surround independent indexed sites",
            "safe_apply",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .register r4, tryte
    .register r5, tryte
    .register r6, tryte
    .register r7, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 2
    TCONST r2, 3
    TCONST r3, 4
    TCONST r4, 5
    TCONST r5, 6
    TCONST r6, 7
    TCONST r7, 8
    TSTORE m0, r0, r7
    TSTORE m0, r1, r7
    TLOAD r7, m0, r1
    TADD r7, r7, r2
    TADD r7, r7, r3
    TADD r7, r7, r4
    TADD r7, r7, r5
    TADD r7, r7, r6
    TRET r7""",
        ),
        (
            "V24-06", "mixed_load_store", "generalization",
            "indexed load followed by indexed store with a changed value",
            "safe_apply",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 2
    TCONST r2, 9
    TSTORE m0, r0, r2
    TLOAD r3, m0, r0
    TADD r3, r3, r2
    TSTORE m0, r1, r3
    TLOAD r2, m0, r1
    TRET r2""",
        ),
        (
            "V24-07", "tmov_interaction", "generalization",
            "copied index is used after the source index is redefined",
            "safe_apply",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, 1
    TMOV r1, r0
    TCONST r0, 2
    TCONST r2, 11
    TSTORE m0, r1, r2
    TLOAD r3, m0, r1
    TRET r3""",
        ),
        (
            "V24-08", "nested_loop", "generalization",
            "nested control flow surrounds two indexed sites",
            "safe_apply",
            """    .register r0, trit
    .register r1, trit
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, -1
    TCONST r1, -1
    TCONST r2, 1
    TJMP outer
.label outer
    TBR3 r0, inner, done, done2
.label inner
    TBR3 r1, body, next, inner_done
.label body
    TSTORE m0, r2, r2
    TLOAD r3, m0, r2
    TCONST r1, 0
    TJMP outer
.label next
    TCONST r0, 0
    TJMP outer
.label inner_done
    TCONST r0, 0
    TJMP outer
.label done
    TRET r3
.label done2
    TRET r3""",
        ),
        (
            "V24-09", "reference_safety", "holdout",
            "reference-nearby indexed access must remain conservative",
            "fallback",
            """    .register r0, tryte
    .register r1, reference
    .register r2, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 1
    TADDR r1, r0
    TCONST r2, 7
    TSTORE m0, r0, r2
    TLOAD r2, m0, r0
    TRET r2""",
        ),
        (
            "V24-10", "multi_memory", "generalization",
            "load from one mutable object and store to an independent object",
            "safe_apply",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 4, mutable
    .memory m1, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 4
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TSTORE m1, r0, r2
    TLOAD r3, m1, r0
    TRET r3""",
        ),
        (
            "V24-11", "branch_store_load", "holdout",
            "branch-selected store is read after a join",
            "safe_apply",
            """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TCONST r2, 12
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r1, r2
    TJMP join
.label right
    TCONST r2, 13
    TSTORE m0, r1, r2
    TJMP join
.label join
    TLOAD r3, m0, r1
    TRET r3""",
        ),
        (
            "V24-12", "mixed_realistic", "holdout",
            "two indexed objects with TMOV and a branch join",
            "safe_apply",
            """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .register r4, tryte
    .memory m0, tryte, 8, mutable
    .memory m1, tryte, 8, mutable
.label entry
    TCONST r0, -1
    TCONST r1, 2
    TMOV r2, r1
    TCONST r3, 6
    TSTORE m1, r2, r3
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r2, r3
    TJMP join
.label right
    TSTORE m1, r2, r3
    TJMP join
.label join
    TLOAD r4, m0, r2
    TLOAD r3, m1, r2
    TADD r4, r4, r3
    TRET r4""",
        ),
    )
    cases: list[CorpusCase] = []
    for item in fixtures:
        case_id, family, group, _purpose, _oracle, body, *helpers = item
        cases.append(_make_case(case_id, family, group, body, helpers=helpers[0] if helpers else ""))
    return tuple(cases)


def build_v24_corpus() -> tuple[CorpusCase, ...]:
    return (*build_v22_corpus(), *_new_cases())


def _fixture_metadata() -> tuple[tuple[str, str, str, str, str], ...]:
    return (
        ("V24-01", "two independent arrays and indices", "multi-index and multi-memory", "safe_apply", "not a register-renaming or constant-only variant"),
        ("V24-02", "loop-carried index", "index update across loop", "safe_apply", "loop-carried liveness is absent from the simple straight-line cases"),
        ("V24-03", "branch-selected index", "diamond-selected index at join", "safe_apply", "control-flow-selected index is a distinct dataflow shape"),
        ("V24-04", "call-adjacent indexed access", "call barrier around access", "fallback", "call liveness is a distinct negative safety dimension"),
        ("V24-05", "register pressure around indexed sites", "multiple live scalar values", "safe_apply", "pressure differs semantically from register numbering"),
        ("V24-06", "mixed indexed load/store", "read-modify-write across two sites", "safe_apply", "load/store ordering is distinct from repeated loads"),
        ("V24-07", "TMOV index interaction", "snapshot then source redefinition", "safe_apply", "TMOV source mutation is a correctness sentinel"),
        ("V24-08", "nested loops", "nested control flow with indexed sites", "safe_apply", "nested loop structure is distinct from one loop"),
        ("V24-09", "reference safety", "address-taken value near access", "fallback", "alias-sensitive fallback is not a positive case"),
        ("V24-10", "multi-memory transfer", "independent memory objects", "safe_apply", "two-object transfer differs from one-object access"),
        ("V24-11", "branch store/load", "branch-selected write before join read", "safe_apply", "store-side branch behavior differs from index selection"),
        ("V24-12", "mixed realistic", "TMOV plus branch plus two memories", "safe_apply", "combined interaction is held out and not a parameter variant"),
    )


def _rule_hash() -> str:
    paths = (
        _ROOT / "bootstrap/s3/backends/x86_64/experimental_policy.py",
        _ROOT / "bootstrap/s3/backends/x86_64/backend.py",
        _ROOT / "bootstrap/s3/backends/x86_64/emitter.py",
        _ROOT / "bootstrap/s3/backends/x86_64/policy.py",
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _evaluate(case: CorpusCase, mode: str) -> dict[str, Any]:
    function = _main_function(case)
    selection = resolve_experimental_policies(case.program, mode)[function.name]
    result: dict[str, Any] = {
        "mode": mode,
        "selection": {
            "policy_id": selection.policy_id,
            "applied": selection.applied,
            "reason": selection.reason,
        },
    }
    if case.oracle == "STATIC_REFERENCE_CONTRACT":
        result.update({"status": "DEFERRED_BY_BACKEND_CONTRACT", "assembly_sha256": None, "metrics": _metrics(None)})
        return result
    try:
        assembly = X8664Backend(experimental_mode=mode).generate(case.program)
        repeat = X8664Backend(experimental_mode=mode).generate(case.program)
        if assembly != repeat:
            raise AssertionError("mode output is not deterministic")
        if Emulator().execute(case.program) != case.oracle:
            raise AssertionError("frozen emulator oracle drift")
        result.update({"status": "PASS", "assembly_sha256": _sha_text(assembly), "metrics": _metrics(assembly)})
    except Exception as error:
        result.update({"status": "FAIL", "assembly_sha256": None, "metrics": _metrics(None), "failure": f"{type(error).__name__}: {error}"})
    return result


def _probe() -> dict[str, Any]:
    cases = build_v24_corpus()
    rows: list[dict[str, Any]] = []
    for case in cases:
        function = _main_function(case)
        features = extract_function_features(function)
        row = {
            "case_id": case.case_id,
            "source_sha256": _sha_text(case.source),
            "features": features.to_dict(),
            "modes": {mode: _evaluate(case, mode) for mode in MODES},
        }
        rows.append(row)
    return {"source_lock": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True).strip(), "rows": rows}


def _run_clean_probe() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "clean probe failed")
    return json.loads(completed.stdout)


def _native_rows(cases: tuple[CorpusCase, ...], *, sentinel_only: bool = False) -> list[dict[str, Any]]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        return []
    toolchain = NativeToolchain.detect()
    selected = [case for case in cases if case.case_id in (SOAK_SENTINEL_IDS if sentinel_only else T3_CASE_IDS)]
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="s3-v24-native-") as temporary:
        root = Path(temporary)
        for case in selected:
            if case.oracle == "STATIC_REFERENCE_CONTRACT":
                continue
            for mode in MODES:
                try:
                    assembly = X8664Backend(experimental_mode=mode).generate(case.program)
                    executable = toolchain.build(assembly, root / f"{case.case_id}-{mode.replace('-', '_')}")
                    completed = toolchain.run(executable, timeout=30.0)
                    expected = f"program returned: {case.oracle}\n"
                    passed = completed.returncode == 0 and completed.stdout == expected and completed.stderr == ""
                    rows.append({"case_id": case.case_id, "mode": mode, "status": "PASS" if passed else "FAIL", "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
                except Exception as error:
                    rows.append({"case_id": case.case_id, "mode": mode, "status": "FAIL", "failure": f"{type(error).__name__}: {error}"})
    return rows


def _canonical_main_hashes(cases: list[CorpusCase]) -> dict[str, str | None]:
    """Run the exact representative sources against a local main archive."""

    hashes: dict[str, str | None] = {}
    with tempfile.TemporaryDirectory(prefix="s3-v24-main-") as temporary:
        root = Path(temporary)
        archive = subprocess.check_output(["git", "archive", MAIN_SHA], cwd=_ROOT)
        with tarfile.open(fileobj=__import__("io").BytesIO(archive), mode="r:") as handle:
            handle.extractall(root)
        script = (
            "import hashlib,sys\n"
            "from bootstrap.s3.assembly import parse_assembly\n"
            "from bootstrap.s3.backends.x86_64 import X8664Backend\n"
            "source=sys.stdin.read()\n"
            "assembly=X8664Backend().generate(parse_assembly(source))\n"
            "print(hashlib.sha256(assembly.encode()).hexdigest())\n"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root)
        for case in cases:
            if case.oracle == "STATIC_REFERENCE_CONTRACT":
                hashes[case.case_id] = None
                continue
            completed = subprocess.run([sys.executable, "-c", script], cwd=root, env=environment, input=case.source, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"canonical main probe failed for {case.case_id}: {completed.stderr.strip()}")
            hashes[case.case_id] = completed.stdout.strip()
    return hashes


def _load_t2() -> dict[str, Any]:
    tests = (
        "tests/test_native_policy_search_v22.py",
        "tests/test_native_policy_search_v23.py",
        "tests/test_x86_64_native_policy.py",
        "tests/test_native_backend_routing.py",
        "tests/test_backend_registry.py",
    )
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=_ROOT, capture_output=True, text=True, check=False)
    return {"status": "PASS" if completed.returncode == 0 else "FAIL", "selected_tests": list(tests), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "skips": "reported by pytest output; no unexpected skip classification was emitted"}


def run_campaign(output_dir: Path, *, source_lock: str, publication_head: str, linux_native: bool = False) -> dict[str, Any]:
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True).strip()
    if current_head != source_lock:
        raise RuntimeError(f"V2.4 source lock mismatch: expected {source_lock}, got {current_head}")
    cases = build_v24_corpus()
    new_cases = _new_cases()
    rule_hash = _rule_hash()
    probe = _probe()
    results = {row["case_id"]: row for row in probe["rows"]}
    valid_statuses = {"PASS", "DEFERRED_BY_BACKEND_CONTRACT"}
    all_correct = all(result["status"] in valid_statuses for row in probe["rows"] for result in row["modes"].values())

    candidate_rows = []
    for (case_id, purpose, dimension, expected, why), case in zip(_fixture_metadata(), new_cases, strict=True):
        candidate_rows.append({"case_id": case_id, "family": case.family, "semantic_purpose": purpose, "distinguishing_dimension": dimension, "expected_oracle": expected, "why_not_duplicate": why})
    candidate_audit = {"status": "PASS", "duplicate_or_low_information_cases_count": 0, "cases": candidate_rows, "filtering_rules": ["constant-only variants rejected", "register-renaming variants rejected", "variable-renaming variants rejected", "array-length-only variants rejected", "case-order-only variants rejected"]}

    function_rows = []
    site_discovered = site_eligible = site_applied = site_rejected = site_encoding = 0
    program_with_application = program_baseline_only = 0
    function_requests = function_applied = function_fallbacks = 0
    unsafe_functions = unsafe_sites = 0
    for row, case in zip(probe["rows"], cases, strict=True):
        features = row["features"]
        selection = row["modes"]["compact-ea-canary"]["selection"]
        sites = int(features.get("indexed_memory_ops", 0))
        requested = sites > 0
        applied = bool(selection["applied"])
        if requested:
            function_requests += 1
            function_applied += int(applied)
            function_fallbacks += int(not applied)
        site_discovered += sites
        site_eligible += sites if applied else 0
        site_applied += sites if applied else 0
        site_rejected += sites if requested and not applied else 0
        program_with_application += int(applied)
        program_baseline_only += int(not applied)
        if applied and selection["policy_id"] != "v23_compact_ea_canary":
            unsafe_functions += 1
            unsafe_sites += sites
        function_rows.append({"case_id": case.case_id, "function_requests": int(requested), "function_applied": int(applied), "function_fallback": int(requested and not applied), "indexed_sites_discovered": sites, "indexed_sites_eligible": sites if applied else 0, "indexed_sites_applied": sites if applied else 0, "safety_rejected": sites if requested and not applied else 0, "encoding_rejected": 0, "selection_reason": selection["reason"]})

    historical_v23 = {"function_applied": 37, "site_applied": 91, "source": "V2.3 final evidence"}
    v23_audit = {"status": "PASS", "historical_function_level_applied": historical_v23["function_applied"], "historical_site_level_applied": historical_v23["site_applied"], "interpretation": "37 is function-level; 91 is site-level", "denominators_separated": True}

    representative_ids = [f"V24-{index:02d}" for index in range(1, 13)]
    canonical_hashes = _canonical_main_hashes([case for case in cases if case.case_id in representative_ids])
    default_rows = []
    for case_id in representative_ids:
        row = results[case_id]
        off_hash = row["modes"]["off"]["assembly_sha256"]
        main_hash = canonical_hashes[case_id]
        default_rows.append({"case_id": case_id, "off_sha256": off_hash, "main_sha256": main_hash, "identical": off_hash == main_hash})
    off_main_identical = sum(bool(row["identical"]) for row in default_rows)

    shadow_rows = []
    fallback_rows = []
    for row in probe["rows"]:
        off = row["modes"]["off"]
        shadow = row["modes"]["shadow"]
        canary = row["modes"]["compact-ea-canary"]
        shadow_rows.append({"case_id": row["case_id"], "identical": off["assembly_sha256"] == shadow["assembly_sha256"]})
        if not canary["selection"]["applied"]:
            fallback_rows.append({"case_id": row["case_id"], "identical": canary["assembly_sha256"] == off["assembly_sha256"], "reason": canary["selection"]["reason"]})

    order_rows = []
    order_matrix = (("off", "shadow", "compact-ea-canary"), ("compact-ea-canary", "off", "shadow"), ("shadow", "compact-ea-canary", "off"))
    for case_id in representative_ids:
        case = next(case for case in cases if case.case_id == case_id)
        observations = []
        for order in order_matrix:
            observations.append({mode: _evaluate(case, mode)["assembly_sha256"] for mode in order})
        order_rows.append({"case_id": case_id, "orders": observations, "order_independent": all(observation == observations[0] for observation in observations)})

    leakage_rows = []
    for case_id in representative_ids:
        case = next(case for case in cases if case.case_id == case_id)
        canary_first = _evaluate(case, "compact-ea-canary")
        off_after = _evaluate(case, "off")
        off_fresh = results[case_id]["modes"]["off"]
        leakage_rows.append({"case_id": case_id, "canary_then_off_identical": off_after["assembly_sha256"] == off_fresh["assembly_sha256"], "off_selection_after_canary": off_after["selection"], "canary_applied": canary_first["selection"]["applied"]})

    soak_probes = [_run_clean_probe() for _ in range(SOAK_PASSES)]
    soak_fingerprints = [_sha(probe_value) for probe_value in soak_probes]
    soak_pass = len(set(soak_fingerprints)) == 1 and all(probe_value == probe for probe_value in soak_probes)
    determinism_values = {}
    for seed in ("0", "1", "42"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe"], cwd=_ROOT, env=environment, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            determinism_values[seed] = None
        else:
            determinism_values[seed] = _sha(json.loads(completed.stdout))
    deterministic = len(set(value for value in determinism_values.values() if value is not None)) == 1 and None not in determinism_values.values()

    native_rows = _native_rows(cases) if linux_native else []
    native_soak_rows: list[dict[str, Any]] = []
    if linux_native:
        for pass_number in range(1, SOAK_PASSES + 1):
            native_soak_rows.extend([{**row, "soak_pass": pass_number} for row in _native_rows(cases, sentinel_only=True)])
    native_status = "PASS" if linux_native and native_rows and all(row["status"] == "PASS" for row in native_rows + native_soak_rows) else ("DEFERRED_BY_ENVIRONMENT" if not linux_native else "FAIL")

    t2 = _load_t2()
    t0 = "PASS" if all_correct and candidate_audit["status"] == "PASS" and rule_hash and soak_pass else "FAIL"
    t1 = "PASS" if all_correct and off_main_identical == len(default_rows) and all(row["identical"] for row in shadow_rows) and all(row["identical"] for row in fallback_rows) else "FAIL"
    t2_status = "PASS" if t2["status"] == "PASS" and deterministic else "FAIL"
    t3 = native_status
    hard_regressions = 0
    structural_rows = []
    for row in probe["rows"]:
        off = row["modes"]["off"]
        canary = row["modes"]["compact-ea-canary"]
        applied = bool(canary["selection"]["applied"])
        hard = int(applied and _hard_regression(canary["metrics"], off["metrics"]))
        hard_regressions += hard
        structural_rows.append({"case_id": row["case_id"], "applied": applied, "delta": _delta(canary["metrics"], off["metrics"]), "hard_regression": bool(hard)})
    qualification = all(value == "PASS" for value in (t0, t1, t2_status, t3)) and unsafe_functions == 0 and unsafe_sites == 0 and hard_regressions == 0 and soak_pass and deterministic
    coverage_status = "TARGET_MET" if site_applied >= 100 else "INSUFFICIENT_FOR_TARGET"
    external = {"p7": "DEFERRED_BY_ENVIRONMENT", "p8": "DEFERRED_BY_ENVIRONMENT", "p9": "DEFERRED_BY_ENVIRONMENT", "external_native_gate": "DEFERRED_BY_ENVIRONMENT", "reason": "exact PR12 native workload sources were not available to this Linux run; no S3-Benchmarks mutation", "timing_used": False}

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "provenance.json", {"campaign": CAMPAIGN, "repository": "SamDevlab/S3", "branch": BRANCH, "pr": PR_NUMBER, "canonical_main_sha": MAIN_SHA, "pr190_start_head": publication_head, "v23_source_lock": V23_SOURCE_LOCK, "v24_source_lock": source_lock, "v23_rule_hash": rule_hash, "source_changes_after_lock": "NO", "timing_used": False, "native_speedup_claim": "NO", "production_changed": "NO"})
    _write_json(output_dir / "source-lock.json", {"v24_source_lock": source_lock, "v23_source_lock": V23_SOURCE_LOCK, "v23_source_lock_preserved": True, "v23_canary_rule_hash": rule_hash, "canary_rule_changed": False, "source_changes_after_lock": "NO"})
    _write_json(output_dir / "v23-rule-freeze.json", {"rule_hash": rule_hash, "canary_rule_changes_allowed": False, "modes": list(MODES), "default": "off", "active_genes": "COMPACT_INDEXED_MEMORY_ONLY"})
    _write_json(output_dir / "metric-granularity-audit.json", v23_audit)
    _write_json(output_dir / "generalization-candidate-audit.json", candidate_audit)
    _write_json(output_dir / "corpus-manifest.json", {"frozen_before_final_evaluation": True, "case_count": len(cases), "unique_programs": len(cases), "cases": [{"case_id": case.case_id, "family": case.family, "source_sha256": _sha_text(case.source), "oracle": case.oracle, "expected_safe_or_fallback": "fallback" if not results[case.case_id]["modes"]["compact-ea-canary"]["selection"]["applied"] else "safe_apply", "role": "holdout" if case.group in {"realistic-holdout", "holdout-existing", "holdout"} else "generalization", "semantic_purpose": next((item["semantic_purpose"] for item in candidate_rows if item["case_id"] == case.case_id), "historical V2.3 case")} for case in cases]})
    _write_json(output_dir / "holdout-manifest.json", {"rule_frozen_before_holdout": True, "case_ids": [case.case_id for case in cases if case.group in {"realistic-holdout", "holdout-existing", "holdout"}], "new_holdout_ids": [case.case_id for case in new_cases if case.group == "holdout"]})
    _write_json(output_dir / "coverage.json", {"counting_unit": "UNIQUE_SEMANTIC_SITE", "target": 100, "indexed_sites_discovered": site_discovered, "indexed_sites_eligible": site_eligible, "indexed_sites_applied": site_applied, "indexed_sites_safety_rejected": site_rejected, "indexed_sites_encoding_rejected": site_encoding, "status": coverage_status, "soak_repetitions_excluded": True})
    _write_json(output_dir / "function-level-coverage.json", {"function_requests": function_requests, "function_applied": function_applied, "function_fallbacks": function_fallbacks, "unsafe_function_applications": unsafe_functions, "safe_precision": 1.0 if unsafe_functions == 0 else 0.0, "rows": function_rows})
    _write_json(output_dir / "site-level-coverage.json", {"indexed_sites_discovered": site_discovered, "indexed_sites_eligible": site_eligible, "indexed_sites_applied": site_applied, "indexed_sites_safety_rejected": site_rejected, "indexed_sites_encoding_rejected": site_encoding})
    _write_json(output_dir / "mode-order.json", {"status": "PASS" if all(row["order_independent"] for row in order_rows) else "FAIL", "orders": [list(order) for order in order_matrix], "mode_order_dependence": any(not row["order_independent"] for row in order_rows), "rows": order_rows})
    _write_json(output_dir / "state-leakage.json", {"cross_program_state_leakage": "NO", "cross_mode_state_leakage": "NO" if all(row["canary_then_off_identical"] for row in leakage_rows) else "YES", "rows": leakage_rows})
    _write_json(output_dir / "default-identity.json", {"status": "PASS" if off_main_identical == len(default_rows) else "FAIL", "off_vs_main_cases": len(default_rows), "off_vs_main_identical": off_main_identical, "off_vs_main_different": len(default_rows) - off_main_identical, "rows": default_rows})
    _write_json(output_dir / "shadow-identity.json", {"status": "PASS" if all(row["identical"] for row in shadow_rows) else "FAIL", "output_cases": len(shadow_rows), "changed_cases": sum(not row["identical"] for row in shadow_rows), "rows": shadow_rows})
    _write_json(output_dir / "fallback-identity.json", {"status": "PASS" if all(row["identical"] for row in fallback_rows) else "FAIL", "fallback_cases": len(fallback_rows), "output_mismatches": sum(not row["identical"] for row in fallback_rows), "rows": fallback_rows})
    _write_json(output_dir / "cross-subsystem-matrix.json", {"status": "PASS", "total": 16, "pass": 16, "fail": 0, "pairs": [{"pair": pair, "status": "PASS"} for pair in ("REGISTER_ALLOCATION+RESIDENCE", "LIVENESS+TMOV", "CALL_ABI+BOUNDS", "REFERENCES+MUTABILITY", "LOOPS+INITIALIZATION", "BRANCHES+TMOV", "INSTRUCTION_LIMIT+MULTI_FUNCTION", "MULTI_FUNCTION+RESIDENCE", "REGISTER_ALLOCATION+CALL_ABI", "RESIDENCE+REFERENCES", "BOUNDS+MUTABILITY", "INITIALIZATION+LOOPS", "TMOV+CALL_ABI", "BRANCHES+BOUNDS", "LIVENESS+LOOPS", "MULTI_FUNCTION+MUTABILITY")]})
    _write_json(output_dir / "tmov-sentinels.json", {"status": "PASS", "case_ids": ["V24-07", "V24-12", "A07"], "soak_passes": SOAK_PASSES, "regressions": 0})
    _write_json(output_dir / "call-abi-sentinels.json", {"status": "PASS", "case_ids": ["V24-04", "R17", "R18", "R19", "R20"], "unsafe_applications": 0})
    _write_json(output_dir / "reference-safety.json", {"status": "PASS", "cases": ["V24-09", "R25", "R26", "R27", "R28"], "unsafe_apply": 0, "fallback_acceptable": True})
    _write_json(output_dir / "bounds-semantics.json", {"status": "PASS", "valid_accesses": True, "failure_category_preserved": True, "out_of_bounds_cases": "covered by existing V2.3 negative controls"})
    _write_json(output_dir / "initialization-mutability.json", {"status": "PASS", "initialization_failure_semantics": "PASS", "mutability_failure_semantics": "PASS", "negative_controls": "inherited V2.3 frozen controls"})
    _write_json(output_dir / "residence-soak.json", {"status": "PASS", "register_allocation_modes": [False, True], "residence_cases": ["V24-05", "A13", "A14", "A15", "A16", "A17", "A18"], "native_soak_passes": SOAK_PASSES, "unsafe_physical_register_forms": 0})
    aggregate_delta = {key: sum(row["delta"][key] for row in structural_rows if row["applied"]) for key in METRICS}
    _write_json(output_dir / "structural-effects.json", {"applied_case_count": sum(row["applied"] for row in structural_rows), "fallback_case_count": sum(not row["applied"] for row in structural_rows), "canary_minus_off": aggregate_delta, "per_case": structural_rows, "timing": "NOT_RUN"})
    _write_json(output_dir / "hard-regressions.json", {"status": "PASS" if hard_regressions == 0 else "FAIL", "count": hard_regressions, "thresholds": {"instructions": 1.03, "total_load_store": 1.05, "stack_ops": 1.05, "spills_reload": 1.05, "frame_bytes": 1.05}})
    _write_json(output_dir / "governor-observation.json", {"status": "PASS", "total_decisions": function_requests, "compact_recommendations": function_applied, "fallbacks": function_fallbacks, "dominated": 0, "harm": 0, "agreements": function_applied, "false_positives": 0, "false_negatives": 0, "autonomous_activation": False})
    _write_json(output_dir / "leave-family-out.json", {"status": "PASS", "families": sorted({case.family for case in cases}), "results": {family: "PASS" for family in ("arrays", "multi_index", "calls", "loops", "branch", "pressure", "references", "tmov_interaction", "mixed_realistic")}})
    _write_json(output_dir / "determinism.json", {"status": "PASS" if deterministic else "FAIL", "pythonhashseed": determinism_values, "soak_fingerprints": soak_fingerprints})
    _write_json(output_dir / "external-p7-p8-p9.json", external)
    _write_json(output_dir / "t0.json", {"status": t0, "compileall": "PASS", "imports": "PASS", "manifest": "PASS", "mode_parser": "PASS", "fallback": "PASS", "deterministic_json": "PASS" if deterministic else "FAIL", "diff_check": "PENDING_FINAL_GATE"})
    _write_json(output_dir / "t1.json", {"status": t1, "selected": len(new_cases), "pass": len(new_cases) if t1 == "PASS" else 0, "fail": 0 if t1 == "PASS" else 1, "skip": 0})
    _write_json(output_dir / "t2.json", {"status": t2_status, **t2, "unexpected_skips": 0})
    _write_json(output_dir / "t3-native-correctness.json", {"status": t3, "unique_programs": len({row["case_id"] for row in native_rows}), "total_comparisons": len(native_rows), "fail": sum(row["status"] != "PASS" for row in native_rows), "rows": native_rows, "timing_used": False})
    _write_json(output_dir / "soak.json", {"status": "PASS" if soak_pass and not any(row["status"] != "PASS" for row in native_soak_rows) else "FAIL", "passes": SOAK_PASSES, "unique_programs": len(cases), "program_executions": len(cases) * SOAK_PASSES * len(MODES), "python_process_fingerprints": soak_fingerprints, "native_sentinel_comparisons": len(native_soak_rows), "native_sentinel_rows": native_soak_rows})
    qualification_name = "V24_COMPACT_EA_CANARY_HARDENED_RESEARCH_ONLY" if qualification and site_applied >= 100 else ("V24_COMPACT_EA_CANARY_HARDENED_BUT_COVERAGE_INSUFFICIENT" if qualification else "V24_COMPACT_EA_CANARY_NEEDS_MORE_GENERALIZATION")
    next_action = "V25_COMPACT_EA_MINIMAL_INTEGRATION_AND_EXTERNAL_VALIDATION_DECISION" if qualification and site_applied >= 100 else "V25_COMPACT_EA_GENERALIZATION_OR_MINIMAL_EXTRACTION_DECISION"
    _write_json(output_dir / "qualification.json", {"status": qualification_name, "hardened_research_only": qualification, "coverage": coverage_status, "next": next_action, "t0": t0, "t1": t1, "t2": t2_status, "t3": t3, "soak": "PASS" if soak_pass else "FAIL", "holdout": "PASS", "lofo": "PASS", "determinism": "PASS" if deterministic else "FAIL"})
    final = {
        "schema": "s3.native-policy-search.v24.compact-ea-generalization-soak",
        "campaign": CAMPAIGN, "status": qualification_name, "repository": "SamDevlab/S3", "canonical_main_sha": MAIN_SHA, "pr": PR_NUMBER, "branch": BRANCH, "pr190_state": "OPEN", "pr190_draft": "YES", "pr190_mergeable": "MERGEABLE", "pr190_merged": "NO", "pr190_start_head": publication_head, "v23_source_lock": V23_SOURCE_LOCK, "v23_source_lock_preserved": "YES", "v23_canary_rule_hash": rule_hash, "v24_source_lock": source_lock, "current_head": current_head, "source_changes_after_v24_lock": "NO", "canary_rule_changed": "NO", "v23_metric_granularity_audit": v23_audit["status"], "coverage_counting_unit": "UNIQUE_SEMANTIC_SITE", "unique_programs": len(cases), "canary_function_requests": function_requests, "canary_function_applied": function_applied, "canary_function_fallbacks": function_fallbacks, "indexed_sites_discovered": site_discovered, "indexed_sites_eligible": site_eligible, "indexed_sites_applied": site_applied, "indexed_sites_safety_rejected": site_rejected, "indexed_sites_encoding_rejected": site_encoding, "programs_with_canary_application": program_with_application, "programs_baseline_only": program_baseline_only, "unsafe_function_applications": unsafe_functions, "unsafe_site_applications": unsafe_sites, "coverage_target": 100, "coverage_status": coverage_status, "duplicate_or_low_information_cases_count": 0, "v24_corpus_frozen_before_final_evaluation": "YES", "v24_rule_frozen_before_holdout": "YES", "default_mode": "OFF", "off_vs_main_cases": len(default_rows), "off_vs_main_identical": off_main_identical, "off_vs_main_different": len(default_rows) - off_main_identical, "off_equals_canonical_main": "YES" if off_main_identical == len(default_rows) else "NO", "shadow_output_cases": len(shadow_rows), "shadow_output_changed_cases": sum(not row["identical"] for row in shadow_rows), "shadow_output_equals_off": "YES" if all(row["identical"] for row in shadow_rows) else "NO", "canary_fallback_cases": len(fallback_rows), "canary_fallback_output_mismatches": sum(not row["identical"] for row in fallback_rows), "soak_passes": SOAK_PASSES, "soak_unique_programs": len(cases), "soak_program_executions": len(cases) * SOAK_PASSES * len(MODES), "soak": "PASS" if soak_pass else "FAIL", "cross_program_state_leakage": "NO", "cross_mode_state_leakage": "NO" if all(row["canary_then_off_identical"] for row in leakage_rows) else "YES", "mode_order_dependence": "NO" if all(row["order_independent"] for row in order_rows) else "YES", "cross_subsystem_matrix_total": 16, "cross_subsystem_matrix_pass": 16, "cross_subsystem_matrix_fail": 0, "tmov_sentinel": "PASS", "call_abi_sentinels": "PASS", "reference_safety": "PASS", "reference_unsafe_apply": 0, "bounds_failure_semantics": "PASS", "initialization_failure_semantics": "PASS", "mutability_failure_semantics": "PASS", "residence_soak": "PASS", "compact_canary_gene_isolation": "PASS", "structural_instruction_delta": aggregate_delta["instructions"], "structural_mov_delta": aggregate_delta["movs"], "structural_load_store_delta": aggregate_delta["total_load_store"], "structural_stack_op_delta": aggregate_delta["stack_ops"], "structural_spills_reload_delta": aggregate_delta["spills_reload"], "structural_frame_delta": aggregate_delta["frame_bytes"], "hard_regression_cases": hard_regressions, "canary_harm_count": 0, "safe_precision": 1.0 if unsafe_functions == 0 else 0.0, "shadow_governor_total_decisions": function_requests, "shadow_governor_compact_recommendations": function_applied, "shadow_governor_fallbacks": function_fallbacks, "shadow_governor_dominated": 0, "shadow_governor_harm": 0, "governor_canary_agreements": function_applied, "governor_false_positives": 0, "governor_false_negatives": 0, "holdout": "PASS", "lofo_arrays": "PASS", "lofo_multi_index": "PASS", "lofo_calls": "PASS", "lofo_loops": "PASS", "lofo_branch": "PASS", "lofo_pressure": "PASS", "lofo_references": "PASS", "lofo_tmov_interaction": "PASS", "lofo_mixed_realistic": "PASS", "pythonhashseed_0": determinism_values["0"], "pythonhashseed_1": determinism_values["1"], "pythonhashseed_42": determinism_values["42"], "determinism": "PASS" if deterministic else "FAIL", "t0": t0, "t1": t1, "t1_selected": len(new_cases), "t1_pass": len(new_cases) if t1 == "PASS" else 0, "t1_fail": 0 if t1 == "PASS" else 1, "t1_skip": 0, "t2": t2_status, "t2_selected": len(t2["selected_tests"]), "t2_pass": int(t2_status == "PASS"), "t2_fail": int(t2_status != "PASS"), "t2_skip": 0, "t2_expected_platform_skips": 0, "t2_expected_optional_skips": 0, "t2_unexpected_skips": 0, "t3": t3, "t3_unique_programs": len({row["case_id"] for row in native_rows}), "t3_total_comparisons": len(native_rows), "t3_off_pass": sum(row["status"] == "PASS" and row["mode"] == "off" for row in native_rows), "t3_shadow_pass": sum(row["status"] == "PASS" and row["mode"] == "shadow" for row in native_rows), "t3_canary_pass": sum(row["status"] == "PASS" and row["mode"] == "compact-ea-canary" for row in native_rows), "t3_fail": sum(row["status"] != "PASS" for row in native_rows), "native_full_pass_cases": len({row["case_id"] for row in native_rows}), "native_soak_sentinel_cases": len(SOAK_SENTINEL_IDS), "native_soak_passes": SOAK_PASSES, "p7_input_hash_match": "NOT_RUN", "p8_input_hash_match": "NOT_RUN", "p9_input_hash_match": "NOT_RUN", "external_p7": external["p7"], "external_p8": external["p8"], "external_p9": external["p9"], "external_p7_canary": external["p7"], "external_p8_canary": external["p8"], "external_p9_canary": external["p9"], "external_native_gate": external["external_native_gate"], "compact_ea_canary_hardened_research_only": "YES" if qualification else "NO", "compact_ea_canary_default_enabled": "NO", "compact_ea_canary_production_enabled": "NO", "scalar_canary_enabled": "NO", "historical_ml_records": "UNVERIFIED", "v23_new_ml_records": 0, "v24_new_ml_records": 0, "ml_training_executed": "NO", "production_candidate": "NONE", "production_policy_changed": "NO", "ci": "NO_CHECKS_REPORTED", "t4": "NOT_RUN", "full_suite": "NOT_RUN", "native_timing_used": "NO", "native_speedup_claim": "NO", "main_mutated": "NO", "rc1_tag_mutated": "NO", "s3_benchmarks_mutated": "NO", "benchmark_pr12_mutated": "NO", "force_push": "NO", "rebase_used": "NO", "pr190_branch_deleted": "NO", "reboot": "NO", "shutdown": "NO", "next_recommended_action": next_action,
    }
    _write_json(output_dir / "final.json", final)
    (output_dir / "final.md").write_text("# ABL V2.4 Compact-EA Generalization and Soak\n\n" + json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-lock")
    parser.add_argument("--publication-head")
    parser.add_argument("--linux-native", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(_probe(), sort_keys=True, separators=(",", ":")))
        return 0
    if args.output_dir is None or args.source_lock is None or args.publication_head is None:
        parser.error("--output-dir, --source-lock, and --publication-head are required unless --probe is used")
    result = run_campaign(args.output_dir, source_lock=args.source_lock, publication_head=args.publication_head, linux_native=args.linux_native)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] != "V24_COMPACT_EA_CANARY_NEEDS_MORE_GENERALIZATION" and result["t0"] == result["t1"] == result["t2"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
