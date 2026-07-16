from __future__ import annotations

import subprocess
import sys

from tools.golden_inspect import GOLDEN_CASES, GOLDEN_ROOT, REPO_ROOT


def test_golden_inspect_check_matches_committed_outputs() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/golden_inspect.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "golden inspect: checked 4 example(s)" in completed.stdout
    assert completed.stderr == ""


def test_golden_inspect_includes_renderer_candidate_stub() -> None:
    cases = {
        case.name: case.source_path.relative_to(REPO_ROOT).as_posix()
        for case in GOLDEN_CASES
    }

    assert (
        cases["assembly_renderer_stub"]
        == "examples/self_hosting/assembly_renderer_stub.s3"
    )
    assert (GOLDEN_ROOT / "assembly_renderer_stub.ir.json").is_file()
    assert (GOLDEN_ROOT / "assembly_renderer_stub.assembly.txt").is_file()
