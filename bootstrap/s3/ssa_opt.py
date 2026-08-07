"""Compatibility facade and fixpoint pipeline for S3 SSA optimization."""

from __future__ import annotations

from typing import Set, Tuple

from .cfg import ControlFlowGraph
from .dominance import DominatorTree
from .ir import IRModule
from .metrics import FixpointTelemetry
from .ssa import SSAFunction, validate_ssa
from .ssa_optimizer.contracts import PassResult, SSA_PASS_CONTRACTS
from .ssa_optimizer.elimination import (
    run_ssa_adce,
    run_ssa_dead_code_elimination,
    run_ssa_dse,
    run_ssa_global_dse,
)
from .ssa_optimizer.loops import (
    run_ssa_licm,
    run_ssa_strength_reduction,
)
from .ssa_optimizer.lowering import _cfg_from_ssa, to_ir
from .ssa_optimizer.peephole import run_ssa_peephole
from .ssa_optimizer.propagation import (
    run_ssa_constant_propagation,
    run_ssa_copy_propagation,
)
from .ssa_optimizer.sccp import run_ssa_sccp
from .ssa_optimizer.value_numbering import run_ssa_cse, run_ssa_gvn
from .verifier import verify_ir

_FIXPOINT_PASSES = frozenset(contract.name for contract in SSA_PASS_CONTRACTS)


class SSAPassVerificationError(AssertionError):
    """Identifies the optimization pass that violated an SSA invariant."""


def _ssa_structure(ssa_fn: SSAFunction) -> tuple[object, ...]:
    return (
        ssa_fn.parameters,
        ssa_fn.blocks,
        ssa_fn.memory_objects,
        ssa_fn.return_type,
        ssa_fn.result_types,
    )


def _verify_pipeline_ssa(ssa_fn: SSAFunction) -> None:
    cfg = _cfg_from_ssa(ssa_fn)
    dom_tree = DominatorTree.build(cfg)
    validate_ssa(ssa_fn, cfg, dom_tree)


def _verify_pipeline_ir(ssa_fn: SSAFunction) -> None:
    verify_ir(IRModule((to_ir(ssa_fn),)))


def run_fixpoint_pipeline(
    ssa_fn: SSAFunction,
    max_iterations: int = 10,
    *,
    disabled_passes: Set[str] | None = None,
    verify_each_pass: bool = False,
) -> Tuple[SSAFunction, FixpointTelemetry]:
    """Iteratively executes optimization passes until reaching fixpoint or max iterations."""
    telemetry = FixpointTelemetry()
    curr_fn = ssa_fn
    disabled = set(disabled_passes or set())
    unknown_passes = disabled - _FIXPOINT_PASSES
    if unknown_passes:
        names = ", ".join(sorted(unknown_passes))
        raise ValueError(f"unknown SSA optimization pass(es): {names}")

    def pass_enabled(name: str) -> bool:
        return name not in disabled

    def make_pass_result(
        next_fn: SSAFunction,
        pass_telemetry: tuple[tuple[str, int], ...] = (),
    ) -> PassResult:
        return PassResult(
            function=next_fn,
            changed=_ssa_structure(next_fn) != _ssa_structure(curr_fn),
            telemetry=pass_telemetry,
        )

    def apply_pass(result: PassResult, pass_name: str) -> bool:
        nonlocal curr_fn
        curr_fn = result.function
        if verify_each_pass:
            try:
                _verify_pipeline_ssa(curr_fn)
            except Exception as error:
                raise SSAPassVerificationError(
                    f"SSA verification failed after pass {pass_name!r}"
                ) from error
        if result.changed:
            for field, count in result.telemetry:
                setattr(telemetry, field, getattr(telemetry, field) + count)
        return result.changed

    if verify_each_pass:
        _verify_pipeline_ssa(curr_fn)

    for it in range(1, max_iterations + 1):
        telemetry.iterations = it
        changed = False

        # 1. GVN
        if pass_enabled("gvn"):
            next_fn, gvn_cnt = run_ssa_gvn(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("expressions_eliminated", gvn_cnt),),
                ),
                "gvn",
            ):
                changed = True

        # 2. Copy Propagation
        if pass_enabled("copy_propagation"):
            next_fn = run_ssa_copy_propagation(curr_fn)
            if apply_pass(make_pass_result(next_fn), "copy_propagation"):
                changed = True

        # 3. DSE (Dead Store Elimination - Milestone 0.92)
        if pass_enabled("dse"):
            next_fn, dse_cnt = run_ssa_dse(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("stores_removed", dse_cnt),),
                ),
                "dse",
            ):
                changed = True

        # 4. Global dead stores with a whole-function no-load proof.
        if pass_enabled("global_dse"):
            next_fn, global_dse_cnt = run_ssa_global_dse(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("stores_removed", global_dse_cnt),),
                ),
                "global_dse",
            ):
                changed = True

        # 5. DCE
        if pass_enabled("dce"):
            next_fn = run_ssa_dead_code_elimination(curr_fn)
            if apply_pass(make_pass_result(next_fn), "dce"):
                changed = True

        # 5. ADCE (Aggressive DCE - Milestone 0.91)
        if pass_enabled("adce"):
            next_fn, adce_cnt = run_ssa_adce(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("dead_instructions_removed", adce_cnt),),
                ),
                "adce",
            ):
                changed = True

        # 6. LICM
        if pass_enabled("licm"):
            next_fn, licm_cnt = run_ssa_licm(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("licm_moves", licm_cnt),),
                ),
                "licm",
            ):
                changed = True

        # 7. SCCP
        if pass_enabled("sccp"):
            next_fn, sccp_expr_cnt, sccp_br_cnt = run_ssa_sccp(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (
                        ("expressions_eliminated", sccp_expr_cnt),
                        ("branches_removed", sccp_br_cnt),
                    ),
                ),
                "sccp",
            ):
                changed = True

        # 8. Strength Reduction
        if pass_enabled("strength_reduction"):
            next_fn, sr_cnt = run_ssa_strength_reduction(curr_fn)
            if apply_pass(
                make_pass_result(
                    next_fn,
                    (("strength_reductions", sr_cnt),),
                ),
                "strength_reduction",
            ):
                changed = True

        # 9. Peephole
        if pass_enabled("peephole"):
            next_fn = run_ssa_peephole(curr_fn)
            if apply_pass(make_pass_result(next_fn), "peephole"):
                changed = True

        if not changed:
            telemetry.converged = True
            telemetry.max_iterations_reached = False
            break
    else:
        telemetry.converged = False
        telemetry.max_iterations_reached = True

    if verify_each_pass:
        _verify_pipeline_ir(curr_fn)

    return curr_fn, telemetry
