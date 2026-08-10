from __future__ import annotations

import os
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


pytestmark = [pytest.mark.s3_native, pytest.mark.s3_differential]
NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"


@pytest.fixture(scope="session")
def numeric_native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def test_f64_sysv_call_executes_natively(
    numeric_native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    source = (
        "fn add(left: f64, right: f64) -> f64:\n"
        "    return left + right\n"
        "fn main() -> trit:\n"
        "    return add(0.5, 0.25) <=> 1.0\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization, mode=SyntaxMode.V0_6)
        assert Emulator().execute(compilation.assembly) == -1
        native_source = generate_native_assembly(compilation.assembly)
        executable = numeric_native_toolchain.build(
            native_source,
            tmp_path / optimization.lower(),
        )
        completed = numeric_native_toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == "program returned: -1\n"
