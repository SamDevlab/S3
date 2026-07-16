from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.s3_program_check import find_program


MANIFEST_PATH = Path("tests/golden/assembly_renderer_candidate_manifest.json")
SUBSET_MANIFEST_PATH = Path("tests/golden/assembly_renderer_subset_manifest.json")
STUB_PATH = Path("examples/self_hosting/assembly_renderer_stub.s3")


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


def test_assembly_renderer_candidate_manifest_smoke_matches_stub() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = STUB_PATH.read_text(encoding="utf-8")
    smoke = data["candidate_smoke"]

    assert smoke == {
        "expected_return": -1,
        "function": "renderer_candidate_capability_smoke",
        "kind": "hosted_assertion",
    }
    assert "fn renderer_candidate_capability_smoke() -> trit:" in source
    assert "renderer_supported_directive_count()" in source
    assert "renderer_supported_opcode_count()" in source
    assert "renderer_directive_end_id()" in source
    assert "renderer_directive_s3asm_id()" in source
    assert "renderer_opcode_tadd_id()" in source
    assert "renderer_opcode_tret_id()" in source
    assert "renderer_first_directive_id()" in source
    assert "renderer_last_directive_id()" in source
    assert "renderer_first_opcode_id()" in source
    assert "renderer_last_opcode_id()" in source
    assert "renderer_supports_directive_id(" in source
    assert "renderer_supports_opcode_id(" in source


def test_assembly_renderer_candidate_manifest_symbol_ranges_match_subset() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    subset = json.loads(SUBSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    source = STUB_PATH.read_text(encoding="utf-8")
    ranges = data["candidate_symbol_ranges"]

    assert ranges["directives"] == {
        "first_function": "renderer_first_directive_id",
        "first_id": 0,
        "last_function": "renderer_last_directive_id",
        "last_id": len(subset["directives"]) - 1,
    }
    assert ranges["opcodes"] == {
        "first_function": "renderer_first_opcode_id",
        "first_id": 0,
        "last_function": "renderer_last_opcode_id",
        "last_id": len(subset["opcodes"]) - 1,
    }
    assert "fn renderer_first_directive_id() -> tryte:\n    return 0" in source
    assert "fn renderer_last_directive_id() -> tryte:\n    return 5" in source
    assert "fn renderer_first_opcode_id() -> tryte:\n    return 0" in source
    assert "fn renderer_last_opcode_id() -> tryte:\n    return 7" in source


def test_assembly_renderer_candidate_manifest_symbol_predicates_match_stub() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = STUB_PATH.read_text(encoding="utf-8")
    predicates = data["candidate_symbol_predicates"]

    assert predicates == {
        "directive_function": "renderer_supports_directive_id",
        "opcode_function": "renderer_supports_opcode_id",
        "supported_return": 1,
        "unsupported_return": -1,
    }
    assert "fn renderer_supports_directive_id(id: tryte) -> trit:" in source
    assert "fn renderer_supports_opcode_id(id: tryte) -> trit:" in source


def test_assembly_renderer_candidate_manifest_symbol_ids_match_subset() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    subset = json.loads(SUBSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    capabilities = data["candidate_capabilities"]
    symbol_ids = data["candidate_symbol_ids"]

    directives = symbol_ids["directives"]
    opcodes = symbol_ids["opcodes"]

    assert len(directives) == capabilities["expected_directive_count"]
    assert len(opcodes) == capabilities["expected_opcode_count"]
    assert set(directives) == set(subset["directives"])
    assert set(opcodes) == set(subset["opcodes"])

    for expected_id, directive in enumerate(subset["directives"]):
        function_name = directive.removeprefix(".").replace(".", "_")
        assert directives[directive] == {
            "function": f"renderer_directive_{function_name}_id",
            "id": expected_id,
        }

    for expected_id, opcode in enumerate(subset["opcodes"]):
        assert opcodes[opcode] == {
            "function": f"renderer_opcode_{opcode.lower()}_id",
            "id": expected_id,
        }
