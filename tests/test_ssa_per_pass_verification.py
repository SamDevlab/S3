from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel, optimize_ir
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3 import ssa_opt


SOURCE = """\
fn main() -> tryte:
    return 1 + 2
"""


def _ssa_function():
    compilation = compile_source(SOURCE, "O0", mode=SyntaxMode.V0_6)
    return SSABuilder.build_function(compilation.ir.functions[0])


def test_per_pass_verification_is_active_and_identifies_the_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_verify = ssa_opt._verify_pipeline_ssa
    calls = 0

    def fail_after_initial_verification(function):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("simulated invalid transformation")
        original_verify(function)

    monkeypatch.setattr(ssa_opt, "_verify_pipeline_ssa", fail_after_initial_verification)
    with pytest.raises(
        ssa_opt.SSAPassVerificationError,
        match="SSA verification failed after pass 'gvn'",
    ):
        ssa_opt.run_fixpoint_pipeline(
            _ssa_function(),
            disabled_passes=set(ssa_opt._FIXPOINT_PASSES) - {"gvn"},
            verify_each_pass=True,
        )


def test_default_pipeline_does_not_enable_per_pass_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_verification(_function):
        raise AssertionError("verification should be opt-in")

    monkeypatch.setattr(ssa_opt, "_verify_pipeline_ssa", unexpected_verification)
    ssa_opt.run_fixpoint_pipeline(
        _ssa_function(),
        disabled_passes=set(ssa_opt._FIXPOINT_PASSES),
    )


def test_o0_does_not_enter_the_ssa_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_ssa_pipeline(*_args, **_kwargs):
        raise AssertionError("O0 must not enter SSA optimization")

    monkeypatch.setattr(ssa_opt, "run_fixpoint_pipeline", unexpected_ssa_pipeline)
    compilation = compile_source(SOURCE, OptimizationLevel.O0, mode=SyntaxMode.V0_6)
    optimize_ir(compilation.ir, OptimizationLevel.O0)
