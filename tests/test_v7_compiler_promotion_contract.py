from __future__ import annotations

import json
from pathlib import Path


def test_v7_command_matrix_is_complete_and_classifies_indirect_container_run() -> None:
    path = Path(__file__).parents[1] / "docs" / "selfhost" / "V7_COMPILER_PARITY.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    commands = {row["command"]: row for row in document["cli_commands"]}

    assert set(commands) == {
        "doctor", "targets", "tokens", "ast", "check", "ir", "ir-json",
        "inspect", "verify-ir", "asm", "run", "native-asm", "build",
        "run-native", "ffi-build", "format", "docs", "test",
        "container inspect", "container plan", "container build", "container run",
    }
    for row in commands.values():
        assert {
            "semantic_compilation",
            "python_reference_only",
            "s3c_ng_required_for_promotion",
            "s3c_ng_supported_now",
            "promotion_blocker_if_unsupported",
            "state",
        } <= row.keys()

    run = commands["container run"]
    assert run["semantic_compilation"] == "INDIRECT"
    assert run["s3c_ng_required_for_promotion"] is True
    assert run["s3c_ng_supported_now"] is True
    assert run["promotion_blocker_if_unsupported"] is True
    assert document["default_compiler"] == "PYTHON"
    assert document["promoted_default"] is False
