from __future__ import annotations

import subprocess
import sys


def test_static_string_literal_contract_is_valid() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_static_string_literal_contract.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "static string literal contract: ok" in completed.stdout
    assert completed.stderr == ""
