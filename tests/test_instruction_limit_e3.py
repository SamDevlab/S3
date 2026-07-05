import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.pipeline import compile_source

NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def _run_native(source: str, tmp_path: Path, toolchain: NativeToolchain, max_instructions: int, optimization="O0") -> subprocess.CompletedProcess[str]:
    compilation = compile_source(source, optimization)
    assembly = generate_native_assembly(compilation.assembly, max_instructions=max_instructions)
    executable = toolchain.build(assembly, tmp_path / "prog")
    return toolchain.run(executable)


def test_exact_limit(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function main() {
        var a = 1;
        var b = 2;
        return a + b;
    }
    """
    compilation = compile_source(source)
    count = sum(len(b.instructions) for b in compilation.assembly.functions[0].blocks)
    
    res = _run_native(source, tmp_path / "n", native_toolchain, count)
    assert res.returncode == 0

    res_fail = _run_native(source, tmp_path / "n_minus_1", native_toolchain, count - 1)
    assert res_fail.returncode == 1
    assert "instruction limit" in res_fail.stderr

    res_plus = _run_native(source, tmp_path / "n_plus_1", native_toolchain, count + 1)
    assert res_plus.returncode == 0


def test_order_before_effects(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function main() {
        var arr = array(2);
        return arr[5];
    }
    """
    compilation = compile_source(source)
    count = sum(len(b.instructions) for b in compilation.assembly.functions[0].blocks)
    
    res_fail = _run_native(source, tmp_path / "fail_limit", native_toolchain, count - 1)
    assert res_fail.returncode == 1
    assert "instruction limit" in res_fail.stderr
    assert "bounds" not in res_fail.stderr


def test_control_flow(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function helper(x) {
        if x == 0 {
            return 1;
        }
        return helper(x - 1);
    }
    function main() {
        var x = 0;
        loop {
            if x == 2 {
                break;
            }
            x = x + 1;
        }
        return helper(3);
    }
    """
    res_success = _run_native(source, tmp_path / "success", native_toolchain, 1000)
    assert res_success.returncode == 0

    res_fail = _run_native(source, tmp_path / "fail", native_toolchain, 20)
    assert res_fail.returncode == 1
    assert "instruction limit" in res_fail.stderr


def test_frame_limit_independence(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function recurse(n) {
        if n == 0 {
            return 0;
        }
        return recurse(n - 1);
    }
    function main() {
        return recurse(10);
    }
    """
    compilation = compile_source(source)
    
    assembly_inst_fail = generate_native_assembly(
        compilation.assembly, max_instructions=5, max_frames=100
    )
    exe1 = native_toolchain.build(assembly_inst_fail, tmp_path / "p1")
    res1 = native_toolchain.run(exe1)
    assert res1.returncode == 1
    assert "instruction limit" in res1.stderr
    assert "frame limit" not in res1.stderr

    assembly_frame_fail = generate_native_assembly(
        compilation.assembly, max_instructions=1000, max_frames=5
    )
    exe2 = native_toolchain.build(assembly_frame_fail, tmp_path / "p2")
    res2 = native_toolchain.run(exe2)
    assert res2.returncode == 1
    assert "frame limit" in res2.stderr
    assert "instruction limit" not in res2.stderr


def test_o0_and_o1(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function main() {
        var a = 1;
        var b = 2;
        var c = a + b;
        return c;
    }
    """
    res_o0 = _run_native(source, tmp_path / "o0", native_toolchain, 1, "O0")
    res_o1 = _run_native(source, tmp_path / "o1", native_toolchain, 1, "O1")
    
    assert res_o0.returncode == 1
    assert "instruction limit" in res_o0.stderr
    
    assert res_o1.returncode == 1
    assert "instruction limit" in res_o1.stderr


def test_native_textual_diagnostic(native_toolchain: NativeToolchain, tmp_path: Path) -> None:
    source = """
    function main() {
        var x = 0;
        return x;
    }
    """
    res = _run_native(source, tmp_path / "diag", native_toolchain, 1)
    assert res.returncode == 1
    stderr = res.stderr
    assert "instruction limit" in stderr
    assert "exceeded" in stderr
    assert "function 'main'" in stderr
    assert "block" in stderr
    assert "TCONST" in stderr or "TRET" in stderr or "TMOV" in stderr
    assert "source" in stderr
    assert "traceback" not in stderr.lower()
    assert "{" not in stderr


def test_run_native_cli_textual_and_json(native_toolchain: NativeToolchain, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_file = tmp_path / "source.s3"
    source_file.write_text("function main() { return 1 + 2; }", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["s3", "run-native", str(source_file), "--max-instructions=1"])
    with pytest.raises(SystemExit) as excinfo:
        cli_main()
    assert excinfo.value.code != 0
    
    from io import BytesIO
    mock_stderr = BytesIO()
    monkeypatch.setattr(sys, "stderr", mock_stderr)
    monkeypatch.setattr(sys.stderr, "buffer", mock_stderr, raising=False)
    
    monkeypatch.setattr(sys, "argv", ["s3", "run-native", str(source_file), "--max-instructions=1", "--diagnostic-format=json"])
    with pytest.raises(SystemExit) as excinfo:
        cli_main()
    assert excinfo.value.code != 0
    
    output = mock_stderr.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data["code"] == "S3E_NATIVE_PROCESS_FAILED"
    assert any("instruction limit" in note for note in data["notes"])
    assert "traceback" not in output.lower()