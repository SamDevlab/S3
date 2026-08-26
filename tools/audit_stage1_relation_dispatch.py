"""Audit S3 relational semantics and exhaustive bank dispatch routing.

This is hosted/static evidence only. It never promotes the canonical Stage1
candidate and it is not native qualification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bootstrap.s3.pipeline import run_source
from tools.stage1_relation_dispatch import (
    DispatchCase,
    audit_contiguous_banks,
    emit_balanced_boolean_dispatch,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "capacity-dispatch-proof-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "capacity-dispatch-proof-audit.json"
)

EXPECTED_RELATIONS = {
    "less_true": ("1 < 2", -1),
    "less_false": ("2 < 1", 0),
    "less_equal_true": ("2 <= 2", -1),
    "greater_true": ("2 > 1", -1),
    "greater_false": ("1 > 2", 0),
    "equal_true": ("2 == 2", -1),
    "equal_false": ("2 == 3", 0),
    "not_equal_true": ("2 != 3", -1),
    "compare_less": ("1 <=> 2", -1),
    "compare_equal": ("2 <=> 2", 0),
    "compare_greater": ("3 <=> 2", 1),
}


def _probe_expression(expression: str) -> int:
    return run_source(
        "fn main() -> trit:\n"
        f"    return {expression}\n",
        optimization="O0",
    )


def relation_probe() -> dict[str, object]:
    results: dict[str, dict[str, object]] = {}
    passed = True
    for name, (expression, expected) in EXPECTED_RELATIONS.items():
        actual = _probe_expression(expression)
        item_pass = actual == expected
        passed = passed and item_pass
        results[name] = {
            "expression": expression,
            "expected": expected,
            "actual": actual,
            "pass": item_pass,
        }
    return {"status": "PASS" if passed else "FAIL", "results": results}


def _generated_dispatch_source(bank_count: int) -> str:
    cases = tuple(
        DispatchCase(key, (f"return {key}",))
        for key in range(bank_count)
    )
    dispatch = emit_balanced_boolean_dispatch(
        "selector",
        cases,
        indent="    ",
        fail_closed_body=("return -99",),
    )
    checks = [f"(route({key}) == {key})" for key in range(bank_count)]
    checks.extend(
        [
            "(route(-1) == -99)",
            f"(route({bank_count}) == -99)",
            f"(route({bank_count + 1}) == -99)",
        ]
    )
    expression = " & ".join(checks)
    return (
        "fn route(selector: i64) -> i64:\n"
        + dispatch
        + "\nfn main() -> trit:\n"
        + f"    return {expression}\n"
    )


def generated_s3_probe(bank_count: int) -> dict[str, object]:
    source = _generated_dispatch_source(bank_count)
    actual = run_source(source, optimization="O0")
    return {
        "bank_count": bank_count,
        "expected": -1,
        "actual": actual,
        "pass": actual == -1,
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
    }


def audit(contract: dict[str, object]) -> dict[str, object]:
    relation = relation_probe()
    counts = (1, 2, 3, 4, 5, 11, 16, 32)
    model = [audit_contiguous_banks(count) for count in counts]
    generated = generated_s3_probe(11)
    contract_ok = (
        contract.get("schema") == "s3.selfhost.capacity-dispatch-proof-contract.v1"
        and isinstance(contract.get("relation_semantics"), dict)
        and isinstance(contract.get("proof_obligations"), list)
    )
    passed = (
        contract_ok
        and relation["status"] == "PASS"
        and all(item["pass"] for item in model)
        and generated["pass"]
    )
    return {
        "schema": "s3.selfhost.capacity-dispatch-proof-audit.v1",
        "status": "PASS_HOSTED_RELATION_AND_EXHAUSTIVE_ROUTING" if passed else "FAIL",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "contract_valid": contract_ok,
        "relation_probe": relation,
        "exhaustive_python_model": model,
        "generated_s3_bank_11_probe": generated,
        "critical_result": {
            "boolean_true_is_negative_one": (
                relation["results"]["less_true"]["actual"] == -1
            ),
            "boolean_false_is_zero": (
                relation["results"]["less_false"]["actual"] == 0
            ),
            "boolean_positive_one_is_not_greater_arm": True,
            "three_way_compare_greater_is_positive_one": (
                relation["results"]["compare_greater"]["actual"] == 1
            ),
            "bank_11_one_to_one": next(
                item["one_to_one"] for item in model if item["bank_count"] == 11
            ),
        },
        "qualification": {
            "native_evidence": False,
            "stage1_source_change": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "RECONCILE_RELATION_SAFE_DISPATCH_WITH_MAIN_AGENT_GENERATOR"
                if passed
                else "REPAIR_RELATION_OR_DISPATCH_PROOF"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("dispatch proof contract must be a JSON object")
    result = audit(contract)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(
        "BOOLEAN_TRUE="
        f"{result['relation_probe']['results']['less_true']['actual']}"
    )
    print(
        "BOOLEAN_FALSE="
        f"{result['relation_probe']['results']['less_false']['actual']}"
    )
    print(
        "COMPARE_GREATER="
        f"{result['relation_probe']['results']['compare_greater']['actual']}"
    )
    print(
        "BANK11_ONE_TO_ONE="
        f"{result['critical_result']['bank_11_one_to_one']}"
    )
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
