from __future__ import annotations

import subprocess
import sys


def test_assembly_program_data_contract_is_valid() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_program_data_contract.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly program data contract: ok" in completed.stdout
    assert completed.stderr == ""
