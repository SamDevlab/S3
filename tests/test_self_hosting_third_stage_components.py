from __future__ import annotations

from pathlib import Path

from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources


ROOT = Path(__file__).parents[1]
WIDTH_MODULE = "selfhost.results.result_width_classifier"
HEADER_MODULE = "selfhost.results.assembly_header_classifier"
PLANNER_MODULE = "selfhost.results.call_result_cell_planner"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _component_sources(main_source: str) -> dict[str, str]:
    return {
        "selfhost/results/result_width_classifier.s3": _source(
            "selfhost/results/result_width_classifier.s3"
        ),
        "selfhost/results/assembly_header_classifier.s3": _source(
            "selfhost/results/assembly_header_classifier.s3"
        ),
        "selfhost/results/call_result_cell_planner.s3": _source(
            "selfhost/results/call_result_cell_planner.s3"
        ),
        "main.s3": main_source,
    }


def _main_source(imports: str, body: str) -> str:
    return (
        "module main\n"
        f"{imports}"
        "fn main() -> tryte:\n"
        f"{body}\n"
    )


def _run(imports: str, body: str, optimization: OptimizationLevel) -> int:
    compilation = compile_sources(
        _component_sources(_main_source(imports, body)),
        optimization=optimization,
    )
    return _execute_hosted_assembly(compilation.assembly, "main")


def _run_o0_o1(imports: str, body: str) -> tuple[int, int]:
    return (
        _run(imports, body, OptimizationLevel.O0),
        _run(imports, body, OptimizationLevel.O1),
    )


def _width_imports() -> str:
    return (
        f"from {WIDTH_MODULE} import classify_result_width\n"
        f"from {WIDTH_MODULE} import result_width_classifier_smoke\n"
        f"from {WIDTH_MODULE} import WidthResult\n"
    )


def _header_imports() -> str:
    return (
        f"from {HEADER_MODULE} import classify_assembly_header\n"
        f"from {HEADER_MODULE} import assembly_header_classifier_smoke\n"
        f"from {HEADER_MODULE} import HeaderResult\n"
    )


def _planner_imports() -> str:
    return (
        f"from {PLANNER_MODULE} import plan_call_result_cells\n"
        f"from {PLANNER_MODULE} import call_result_cell_planner_smoke\n"
        f"from {PLANNER_MODULE} import PlanResult\n"
    )


def test_width_classifier_returns_structured_success_and_error() -> None:
    imports = _width_imports()
    success = (
        "    match classify_result_width(4):\n"
        "        WidthResult.Ok(info):\n"
        "            return info.width + info.is_aggregate\n"
        "        WidthResult.Err(error):\n"
        "            return 0 - error.code"
    )
    error = (
        "    match classify_result_width(0):\n"
        "        WidthResult.Ok(info):\n"
        "            return info.width\n"
        "        WidthResult.Err(error):\n"
        "            return 0 - error.code"
    )

    assert _run_o0_o1(imports, success) == (3, 3)
    assert _run_o0_o1(imports, error) == (-1, -1)


def test_assembly_header_classifier_distinguishes_legacy_and_current() -> None:
    imports = _header_imports()
    legacy = (
        "    match classify_assembly_header(0, 5, 0):\n"
        "        HeaderResult.Ok(info):\n"
        "            return info.minor + info.is_legacy\n"
        "        HeaderResult.Err(error):\n"
        "            return 0 - error.code"
    )
    current = (
        "    match classify_assembly_header(0, 6, 0):\n"
        "        HeaderResult.Ok(info):\n"
        "            return info.minor + info.is_legacy\n"
        "        HeaderResult.Err(error):\n"
        "            return 0 - error.code"
    )

    assert _run_o0_o1(imports, legacy) == (4, 4)
    assert _run_o0_o1(imports, current) == (6, 6)


def test_call_result_planner_propagates_width_classifier_error_explicitly() -> None:
    imports = _planner_imports()
    success = (
        "    match plan_call_result_cells(5):\n"
        "        PlanResult.Ok(plan):\n"
        "            return plan.width + plan.last_cell + plan.is_aggregate\n"
        "        PlanResult.Err(error):\n"
        "            return 0 - error.code"
    )
    error = (
        "    match plan_call_result_cells(0):\n"
        "        PlanResult.Ok(plan):\n"
        "            return plan.width\n"
        "        PlanResult.Err(error):\n"
        "            return 0 - error.code"
    )

    assert _run_o0_o1(imports, success) == (8, 8)
    assert _run_o0_o1(imports, error) == (-1, -1)


def test_third_stage_smoke_components_are_deterministic() -> None:
    assert _run_o0_o1(
        _width_imports(),
        "    return result_width_classifier_smoke()",
    ) == (3, 3)
    assert _run_o0_o1(
        _header_imports(),
        "    return assembly_header_classifier_smoke()",
    ) == (6, 6)
    assert _run_o0_o1(
        _planner_imports(),
        "    return call_result_cell_planner_smoke()",
    ) == (3, 3)
