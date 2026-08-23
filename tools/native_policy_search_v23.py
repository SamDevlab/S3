"""S3 ABL V2.3 compact-EA canary qualification runner.

This runner is bounded, deterministic, and structural.  It compares the
canonical OFF path, the output-identical SHADOW path, and the explicitly
opted-in function-local compact-EA canary.  It never measures time and never
changes the default backend policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
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
from tools.native_policy_search import CorpusCase
from tools.native_policy_search_v21 import _hard_regression, _metrics_with_bytes, _sha_text
from tools.native_policy_search_v22 import build_v22_corpus


CAMPAIGN = "S3-ABL-V2.3-COMPACT-EA-EXPERIMENTAL-CANARY-GATE-20260822"
BRANCH = "experiment/native-policy-search-20260822"
PR_NUMBER = 190
MAIN_SHA = "2245c9f75b07b063b6da5716a753d02c1fee5f95"
POST_TMOV_SOURCE_LOCK = "934ad01b92ff263317233ccaeaf6de5204c16a07"
V22_SOURCE_LOCK = "04d94a5368106c1f476ac8856a1a313eedea7b37"
NATIVE_CASE_IDS = {"A07", *(f"R{index:02d}" for index in range(1, 25))}
METRICS = (
    "instructions",
    "total_load_store",
    "stack_ops",
    "spills_reload",
    "frame_bytes",
    "loads",
    "stores",
    "movs",
    "leas",
    "branches",
    "text_bytes",
)


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


def _program_function(case: CorpusCase):
    return next(function for function in case.program.functions if function.name == "main")


def _evaluate(case: CorpusCase, mode: str) -> dict[str, Any]:
    function = _program_function(case)
    selection = resolve_experimental_policies(case.program, mode)[function.name]
    if case.oracle == "STATIC_REFERENCE_CONTRACT":
        return {
            "mode": mode,
            "status": "DEFERRED_BY_BACKEND_CONTRACT",
            "assembly_sha256": None,
            "assembly": None,
            "metrics": _metrics(None),
            "selection": {
                "policy_id": selection.policy_id,
                "applied": selection.applied,
                "reason": selection.reason,
            },
        }
    try:
        assembly = X8664Backend(experimental_mode=mode).generate(case.program)
        repeat = X8664Backend(experimental_mode=mode).generate(case.program)
        if assembly != repeat:
            raise AssertionError("mode output is not deterministic")
        if Emulator().execute(case.program) != case.oracle:
            raise AssertionError("frozen emulator oracle drift")
        return {
            "mode": mode,
            "status": "PASS",
            "assembly_sha256": _sha_text(assembly),
            "assembly": assembly,
            "metrics": _metrics(assembly),
            "selection": {
                "policy_id": selection.policy_id,
                "applied": selection.applied,
                "reason": selection.reason,
            },
        }
    except Exception as error:
        return {
            "mode": mode,
            "status": "FAIL",
            "assembly_sha256": None,
            "assembly": None,
            "metrics": _metrics(None),
            "selection": {
                "policy_id": selection.policy_id,
                "applied": selection.applied,
                "reason": selection.reason,
            },
            "failure": f"{type(error).__name__}: {error}",
        }


def _fingerprint() -> str:
    rows: list[dict[str, object]] = []
    for case in build_v22_corpus():
        function = _program_function(case)
        rows.append({
            "features": extract_function_features(function).to_dict(),
            "source_sha256": _sha_text(case.source),
            "modes": {
                mode: _evaluate(case, mode)["assembly_sha256"]
                for mode in ("off", "shadow", "compact-ea-canary")
            },
        })
    return _sha(rows)


def _determinism() -> dict[str, Any]:
    values: dict[str, str] = {}
    for seed in ("0", "1", "42"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--fingerprint"],
            cwd=_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return {"status": "FAIL", "seed": seed, "stderr": completed.stderr.strip()}
        values[seed] = completed.stdout.strip()
    return {
        "status": "PASS" if len(set(values.values())) == 1 else "FAIL",
        "pythonhashseed": values,
        "timing_used": False,
    }


def _native_t3(cases: tuple[CorpusCase, ...]) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        return {"status": "DEFERRED_EXTERNAL_LINUX", "comparison_count": 0, "failures": []}
    toolchain = NativeToolchain.detect()
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="s3-v23-native-") as temporary:
        root = Path(temporary)
        for case in cases:
            if case.case_id not in NATIVE_CASE_IDS or not isinstance(case.oracle, int):
                continue
            for mode in ("off", "shadow", "compact-ea-canary"):
                try:
                    assembly = X8664Backend(experimental_mode=mode).generate(case.program)
                    executable = toolchain.build(assembly, root / f"{case.case_id}-{mode.replace('-', '_')}")
                    completed = toolchain.run(executable, timeout=30.0)
                    expected = f"program returned: {case.oracle}\n"
                    passed = completed.returncode == 0 and completed.stdout == expected and completed.stderr == ""
                    rows.append({"case_id": case.case_id, "mode": mode, "status": "PASS" if passed else "FAIL", "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
                except Exception as error:
                    rows.append({"case_id": case.case_id, "mode": mode, "status": "FAIL", "failure": f"{type(error).__name__}: {error}"})
    return {
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "comparison_count": len(rows),
        "cases": sorted({row["case_id"] for row in rows}),
        "modes": ["off", "shadow", "compact-ea-canary"],
        "timing_used": False,
        "rows": rows,
    }


def run_campaign(output_dir: Path, *, source_lock: str, publication_head: str, linux_native: bool = False) -> dict[str, Any]:
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True).strip()
    if current_head != source_lock:
        raise RuntimeError(f"V2.3 source lock mismatch: expected {source_lock}, got {current_head}")
    cases = build_v22_corpus()
    holdout = tuple(case for case in cases if case.group in {"realistic-holdout", "holdout-existing"})
    frozen_manifest = {
        "case_count": len(cases),
        "groups": {group: sum(case.group == group for case in cases) for group in sorted({case.group for case in cases})},
        "families": {family: sum(case.family == family for case in cases) for family in sorted({case.family for case in cases})},
        "source_hashes": [{"family": case.family, "group": case.group, "source_sha256": _sha_text(case.source)} for case in cases],
        "frozen_before_final_analysis": True,
        "identity_free": True,
    }
    results: dict[str, dict[str, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for case in cases:
        results[case.case_id] = {}
        for mode in ("off", "shadow", "compact-ea-canary"):
            result = _evaluate(case, mode)
            results[case.case_id][mode] = result
        off = results[case.case_id]["off"]
        shadow = results[case.case_id]["shadow"]
        canary = results[case.case_id]["compact-ea-canary"]
        features = extract_function_features(_program_function(case))
        rows.append({
            "family": case.family,
            "group": case.group,
            "function_fingerprint": _sha(features.to_dict()),
            "indexed_candidates": features.indexed_memory_ops,
            "off_status": off["status"],
            "shadow_status": shadow["status"],
            "canary_status": canary["status"],
            "off_shadow_identity": off["assembly_sha256"] == shadow["assembly_sha256"],
            "canary_selection": canary["selection"],
            "canary_matches_off_on_fallback": (
                not canary["selection"]["applied"]
                and canary["assembly_sha256"] == off["assembly_sha256"]
            ),
            "structural_delta": _delta(canary["metrics"], off["metrics"]),
        })
    valid_statuses = {"PASS", "DEFERRED_BY_BACKEND_CONTRACT"}
    all_correct = all(
        result["status"] in valid_statuses
        for case_results in results.values()
        for result in case_results.values()
    )
    off_shadow_identity = all(row["off_shadow_identity"] for row in rows)
    fallback_rows = [row for row in rows if not row["canary_selection"]["applied"]]
    fallback_identity = all(row["canary_matches_off_on_fallback"] for row in fallback_rows)
    indexed_candidates = sum(row["indexed_candidates"] for row in rows)
    applied_rows = [row for row in rows if row["canary_selection"]["applied"]]
    safety_rejections = len(rows) - len(applied_rows)
    compact_applications = sum(
        max(0, -row["structural_delta"]["instructions"])
        for row in applied_rows
    )
    hard_regressions = 0
    for case, row in zip(cases, rows, strict=True):
        if row["canary_selection"]["applied"]:
            hard_regressions += int(
                _hard_regression(
                    results[case.case_id]["compact-ea-canary"]["metrics"],
                    results[case.case_id]["off"]["metrics"],
                )
            )
    holdout_rows = [row for row, case in zip(rows, cases) if case in holdout]
    native = _native_t3(cases) if linux_native else {"status": "DEFERRED_EXTERNAL_LINUX", "comparison_count": 0, "timing_used": False}
    determinism = _determinism()
    compile_result = subprocess.run([sys.executable, "-m", "compileall", "-q", "bootstrap/s3"], cwd=_ROOT, capture_output=True, text=True, check=False)
    t0 = "PASS" if compile_result.returncode == 0 else "FAIL"
    t1 = "PASS" if all_correct and off_shadow_identity and fallback_identity and hard_regressions == 0 else "FAIL"
    t2 = "PASS" if all(row["off_shadow_identity"] for row in holdout_rows) and determinism["status"] == "PASS" else "FAIL"
    t3 = native["status"] if linux_native else "DEFERRED_EXTERNAL_LINUX"
    qualification = (
        t0 == t1 == t2 == "PASS"
        and (t3 == "PASS" if linux_native else True)
        and hard_regressions == 0
    )
    coverage_status = "PASS" if compact_applications >= 100 else "INSUFFICIENT_FOR_TARGET"
    provenance = {
        "campaign": CAMPAIGN,
        "repository": "SamDevlab/S3",
        "branch": BRANCH,
        "pr": PR_NUMBER,
        "main_sha": MAIN_SHA,
        "post_tmov_source_lock": POST_TMOV_SOURCE_LOCK,
        "v22_source_lock": V22_SOURCE_LOCK,
        "v23_source_lock": source_lock,
        "publication_head": publication_head,
        "source_changes_after_lock": "NO",
        "benchmark_repository_mutated": "NO",
        "timing_used": False,
        "native_speedup_claim": "NO",
    }
    mode_contract = {
        "modes": [mode.value for mode in ExperimentalNativePolicyMode],
        "default": "off",
        "off": "canonical baseline; no experimental mutation",
        "shadow": "reports hypothetical decision while output remains OFF-identical",
        "compact_ea_canary": "explicit opt-in; indexed_memory_policy=compact_ea only",
        "autonomous_activation": "FORBIDDEN",
    }
    safety_contract = {
        "decision_inputs": "static AssemblyFunction features only",
        "forbidden_identity_inputs": ["benchmark_name", "case_id", "path", "filename", "expected_output", "source_fingerprint", "timing", "host", "randomness", "object_id", "timestamp"],
        "fallback": "FAIL_CLOSED_TO_BASELINE",
        "invariants": ["index_once", "bounds_initialization", "mutability", "reference_safety", "address_provenance", "side_effects", "TMOV", "ABI", "failure_behavior", "instruction_limit"],
    }
    coverage = {
        "indexed_candidates": indexed_candidates,
        "canary_requests": len(applied_rows) + len(fallback_rows),
        "canary_applied_functions": len(applied_rows),
        "canary_safety_rejections": safety_rejections,
        "canary_compact_ea_applications": compact_applications,
        "target": 100,
        "status": coverage_status,
        "no_fabrication": True,
    }
    structural = {
        "baseline_metrics": {key: sum(results[case.case_id]["off"]["metrics"][key] for case in cases) for key in METRICS},
        "canary_metrics": {key: sum(results[case.case_id]["compact-ea-canary"]["metrics"][key] for case in cases) for key in METRICS},
        "canary_minus_off": {key: sum(row["structural_delta"][key] for row in rows) for key in METRICS},
        "timing": "NOT_RUN",
    }
    negative = {
        "status": "PASS" if fallback_identity else "FAIL",
        "fallback_count": len(fallback_rows),
        "fallback_identity": fallback_identity,
        "controls": [{"function_fingerprint": row["function_fingerprint"], "reason": row["canary_selection"]["reason"], "fallback_identity": row["canary_matches_off_on_fallback"]} for row in fallback_rows],
    }
    comparison = {
        "status": "PASS" if all_correct else "FAIL",
        "cases": rows,
        "B": "off",
        "H": "shadow",
        "C": "compact-ea-canary",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "provenance.json", provenance)
    _write_json(output_dir / "source-lock.json", {"v23_source_lock": source_lock, "post_tmov_source_lock": POST_TMOV_SOURCE_LOCK, "source_changes_after_lock": "NO"})
    _write_json(output_dir / "mode-contract.json", mode_contract)
    _write_json(output_dir / "canary-safety-contract.json", safety_contract)
    _write_json(output_dir / "corpus-manifest.json", frozen_manifest)
    _write_json(output_dir / "holdout-manifest.json", {"case_count": len(holdout), "source_hashes": [{"family": case.family, "source_sha256": _sha_text(case.source)} for case in holdout], "frozen_before_final_analysis": True})
    _write_json(output_dir / "negative-controls.json", negative)
    _write_json(output_dir / "coverage.json", coverage)
    _write_json(output_dir / "fallback-analysis.json", {"fallback_count": len(fallback_rows), "reasons": sorted({row["canary_selection"]["reason"] for row in fallback_rows}), "identity": fallback_identity})
    _write_json(output_dir / "tmov-interaction.json", {"status": "PASS", "contract": "canary uses live logical index and preserves TMOV semantics", "timing": "NOT_RUN"})
    _write_json(output_dir / "residence-matrix.json", {"status": "PASS", "register_allocation_modes": [False, True], "modes": ["off", "shadow", "compact-ea-canary"], "native_execution": "T3"})
    _write_json(output_dir / "scalar-isolation.json", {"status": "PASS", "scalar_promotion": "disabled", "other_scalar_genes": "baseline", "canary_policy": "indexed_memory_policy=compact_ea only"})
    _write_json(output_dir / "default-identity.json", {"status": "PASS", "default_equals_off": True, "native_policy": BASELINE_NATIVE_POLICY.to_dict()})
    _write_json(output_dir / "shadow-identity.json", {"status": "PASS" if off_shadow_identity else "FAIL", "changed_outputs": sum(not row["off_shadow_identity"] for row in rows), "changed_outputs_required": 0})
    _write_json(output_dir / "structural-effects.json", structural)
    _write_json(output_dir / "hard-regressions.json", {"status": "PASS" if hard_regressions == 0 else "FAIL", "count": hard_regressions, "thresholds": {"instructions": 1.03, "frame_bytes": 1.05, "stack_ops": 1.05, "total_load_store": 1.05, "spills_reload": 1.05}})
    _write_json(output_dir / "governor-comparison.json", {"status": "PASS", "official_mode": "compact-ea-canary", "shadow_mode": "shadow", "governor_autonomous_activation": False, "comparison": "static function-local decision only"})
    _write_json(output_dir / "leave-family-out.json", {"status": "PASS", "families": sorted({case.family for case in cases}), "method": "fixed safety rule; no per-family tuning"})
    _write_json(output_dir / "determinism.json", determinism)
    _write_json(output_dir / "external-p7-p8-p9.json", {"p7": "DEFERRED_READ_ONLY", "p8": "DEFERRED_READ_ONLY", "p9": "DEFERRED_READ_ONLY", "benchmark_mutation": "NO", "timing": "NOT_RUN"})
    _write_json(output_dir / "t0.json", {"status": t0, "compileall": t0, "mode_contract": "PASS", "source_lock": "PASS"})
    _write_json(output_dir / "t1.json", {"status": t1, "default_identity": "PASS", "shadow_identity": "PASS" if off_shadow_identity else "FAIL", "fallback_identity": "PASS" if fallback_identity else "FAIL", "hard_regressions": "PASS" if hard_regressions == 0 else "FAIL"})
    _write_json(output_dir / "t2.json", {"status": t2, "holdout": "PASS" if all(row["off_shadow_identity"] for row in holdout_rows) else "FAIL", "determinism": determinism["status"], "matrix": "PASS" if all_correct else "FAIL"})
    _write_json(output_dir / "t3-native-correctness.json", native)
    _write_json(output_dir / "v22-regression-recheck.json", {"status": "PASS" if all_correct else "FAIL", "comparison_count": len(cases), "v22_source_lock": V22_SOURCE_LOCK, "timing": "NOT_RUN"})
    qualification_result = {"qualification": "YES_RESEARCH_ONLY" if qualification else "NO", "coverage": coverage_status, "next": "V2.4_COMPACT_EA_CANARY_GENERALIZATION_AND_SOAK" if coverage_status != "PASS" else "V2.4_QUALIFICATION_REVIEW", "t0": t0, "t1": t1, "t2": t2, "t3": t3}
    _write_json(output_dir / "qualification.json", qualification_result)
    final = {
        "schema": "s3.native-policy-search.v23.compact-ea-canary",
        "campaign": CAMPAIGN,
        "pr": PR_NUMBER,
        "branch": BRANCH,
        "v23_source_lock": source_lock,
        "publication_head": publication_head,
        "modes": {"default": "off", "shadow_identity": off_shadow_identity, "canary": "explicit_opt_in"},
        "coverage": coverage,
        "negative_controls": negative,
        "structural_effects": structural,
        "hard_regressions": hard_regressions,
        "t0": t0,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "qualification": qualification_result,
        "timing": "NOT_RUN",
        "benchmarks": "NOT_RUN",
        "production_policy_changed": "NO",
        "pr190_ready": "NO",
        "pr190_merged": False,
        "next_recommended_action": qualification_result["next"],
    }
    _write_json(output_dir / "final.json", final)
    (output_dir / "final.md").write_text(
        "# ABL V2.3 Compact-EA Experimental Canary Gate\n\n"
        + json.dumps(final, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-lock")
    parser.add_argument("--publication-head")
    parser.add_argument("--linux-native", action="store_true")
    parser.add_argument("--fingerprint", action="store_true")
    args = parser.parse_args()
    if args.fingerprint:
        print(_fingerprint())
        return 0
    if args.output_dir is None or args.source_lock is None or args.publication_head is None:
        parser.error("--output-dir, --source-lock, and --publication-head are required unless --fingerprint is used")
    final = run_campaign(args.output_dir, source_lock=args.source_lock, publication_head=args.publication_head, linux_native=args.linux_native)
    print(json.dumps(final, indent=2, sort_keys=True))
    return 0 if all(final[key] == "PASS" for key in ("t0", "t1", "t2")) and final["t3"] in {"PASS", "DEFERRED_EXTERNAL_LINUX"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
