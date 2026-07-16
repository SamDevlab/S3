from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.s3_program_check import find_program


MANIFEST_PATH = Path("tests/golden/assembly_renderer_candidate_manifest.json")
SUBSET_MANIFEST_PATH = Path("tests/golden/assembly_renderer_subset_manifest.json")


def test_assembly_renderer_candidate_manifest_is_valid() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/check_assembly_renderer_candidate_manifest.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "assembly renderer candidate manifest: ok" in completed.stdout
    assert completed.stderr == ""


def test_assembly_renderer_candidate_manifest_matches_program_inventory() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    program_inventory = data["program_inventory"]

    program = find_program(program_inventory["path"])

    assert program is not None
    assert (
        program_inventory["path"]
        == "examples/self_hosting/assembly_renderer_stub.s3"
    )
    assert program_inventory["covered_by_s3_program_check"] is True
    assert program_inventory["hosted_expected_return"] == -1
    assert (
        program.hosted_expected_return
        == program_inventory["hosted_expected_return"]
    )


def test_assembly_renderer_candidate_manifest_capabilities_match_subset() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    subset = json.loads(SUBSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    capabilities = data["candidate_capabilities"]

    assert (
        capabilities["directive_count_function"]
        == "renderer_supported_directive_count"
    )
    assert capabilities["expected_directive_count"] == len(subset["directives"])
    assert capabilities["opcode_count_function"] == "renderer_supported_opcode_count"
    assert capabilities["expected_opcode_count"] == len(subset["opcodes"])
