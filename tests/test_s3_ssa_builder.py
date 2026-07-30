from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder, SSAFunction


def test_ssa_builder_linear_function() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    mut b: tryte = a + 5\n"
        "    return b\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)

    assert isinstance(ssa_fn, SSAFunction)
    assert ssa_fn.name == "main"
    assert len(ssa_fn.blocks) == len(fn.blocks)
    assert len(ssa_fn.values) > 0


def test_ssa_builder_renaming_version_increments() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 1\n"
        "    a = 2\n"
        "    a = 3\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)

    # Values for register defining 'a' should have distinct versions (_v0, _v1, _v2, etc.)
    val_names = [v.name for v in ssa_fn.values]
    assert len(val_names) == len(set(val_names))
