from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_source


pytestmark = [pytest.mark.s3_native, pytest.mark.s3_differential]

SOURCE_PATH = Path("examples/external/jsmn/jsmn_demo.s3")
EXPECTED_DEMO_TOKEN_COUNT = 3


@pytest.fixture(scope="session")
def jsmn_native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))


@pytest.mark.parametrize("optimization", ["O0", "O1"])
def test_external_jsmn_demo_executes_natively(
    optimization: str,
    jsmn_native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    program = compile_source(source, optimization).assembly

    assert Emulator().execute(program) == EXPECTED_DEMO_TOKEN_COUNT

    native_assembly = generate_native_assembly(program)
    executable = jsmn_native_toolchain.build(
        native_assembly,
        tmp_path / f"jsmn-{optimization.lower()}",
    )
    completed = jsmn_native_toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {EXPECTED_DEMO_TOKEN_COUNT}\n"
