from __future__ import annotations

import json

import pytest

from bootstrap.s3.ir import IRBasicBlock, IRFunction, IRInstruction, IRModule, IROpcode, IRRegister, IRType
from bootstrap.s3.metrics import OptimizationBudget, evaluate_optimization_budget
from tools.check_optimization_budgets import DEFAULT_MANIFEST, evaluate_manifest, main


def _module(instruction_count: int, *, blocks: int = 1) -> IRModule:
    register_count = max(instruction_count - blocks, 1)
    registers = tuple(IRRegister(index, IRType.TRYTE) for index in range(register_count))
    output = []
    next_register = 0
    for block_index in range(blocks):
        instructions = []
        body_count = instruction_count // blocks
        if block_index < instruction_count % blocks:
            body_count += 1
        for _ in range(max(body_count - 1, 0)):
            instructions.append(IRInstruction(IROpcode.CONST, result=next_register, immediate=0))
            next_register += 1
        return_register = max(next_register - 1, 0)
        instructions.append(IRInstruction(IROpcode.RETURN, operands=(return_register,)))
        output.append(IRBasicBlock(f"block-{block_index}", tuple(instructions)))
    function = IRFunction("main", (), IRType.TRYTE, registers, tuple(output))
    return IRModule((function,))


def test_budget_passes_at_exact_limits() -> None:
    before = _module(5)
    after = _module(3)
    budget = OptimizationBudget(1, 3, 0)

    result = evaluate_optimization_budget(before, after, budget)

    assert result.passed is True
    assert result.violations == ()


def test_budget_reports_limits_and_growth_in_deterministic_order() -> None:
    before = _module(2)
    after = _module(4, blocks=2)
    budget = OptimizationBudget(1, 3, 0)

    result = evaluate_optimization_budget(before, after, budget)

    assert result.passed is False
    assert result.violations == (
        "blocks: actual 2 exceeds maximum 1",
        "instructions: actual 4 exceeds maximum 3",
        "blocks: optimized count grew from 1 to 2",
        "instructions: optimized count grew from 2 to 4",
    )


def test_budget_can_allow_structural_growth_within_limits() -> None:
    result = evaluate_optimization_budget(
        _module(2),
        _module(4, blocks=2),
        OptimizationBudget(2, 4, 0, require_non_growth=False),
    )
    assert result.passed is True


@pytest.mark.parametrize("value", [-1, -2])
def test_budget_rejects_negative_limits(value) -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        OptimizationBudget(value, 1, 0)


def test_budget_requires_boolean_growth_policy() -> None:
    with pytest.raises(TypeError, match="require_non_growth must be a boolean"):
        OptimizationBudget(1, 1, 0, require_non_growth=1)  # type: ignore[arg-type]


def test_versioned_repository_manifest_passes() -> None:
    report = evaluate_manifest(DEFAULT_MANIFEST)

    assert report["status"] == "PASS"
    assert [item["id"] for item in report["programs"]] == [
        "first",
        "sign",
        "static-array",
    ]
    assert all(item["status"] == "PASS" for item in report["programs"])


def test_cli_returns_nonzero_for_exceeded_budget(tmp_path, capsys) -> None:
    document = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    document["programs"] = [document["programs"][0]]
    document["programs"][0]["budget"]["maximum_instructions"] = 0
    manifest = tmp_path / "budgets.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert main(["--manifest", str(manifest)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "FAIL"
    assert report["programs"][0]["violations"] == [
        "instructions: actual 2 exceeds maximum 0"
    ]


def test_cli_rejects_duplicate_ids(tmp_path, capsys) -> None:
    document = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    document["programs"] = [document["programs"][0], dict(document["programs"][0])]
    manifest = tmp_path / "budgets.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    assert main(["--manifest", str(manifest)]) == 2
    assert "program ids must be unique" in capsys.readouterr().err
