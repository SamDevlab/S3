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
        "bootstrap install s3c-ng",
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
    bootstrap = commands["bootstrap install s3c-ng"]
    assert bootstrap["semantic_compilation"] is False
    assert bootstrap["s3c_ng_supported_now"] is False
    assert bootstrap["state"] == "EXPLICIT_RELEASE_INSTALLER_LOCK_UNPUBLISHED"
    assert document["default_compiler"] == "PYTHON"
    assert document["promoted_default"] is False


def test_v7_parity_evidence_is_scoped_and_points_to_existing_tests() -> None:
    repository = Path(__file__).parents[1]
    document = json.loads(
        (repository / "docs" / "selfhost" / "V7_COMPILER_PARITY.json").read_text(
            encoding="utf-8"
        )
    )
    allowed_states = set(document["feature_matrix_policy"]["allowed_states"])
    scope = document["evidence_scope"]
    assert "not native-candidate qualification" in scope["hosted_bridge_tests"]
    assert "actual native candidate" in scope["native_candidate_tests"]

    for feature in document["features"]:
        evidence = feature["evidence"]
        assert feature["state"] in allowed_states, feature["family"]
        if feature["state"] == "PARTIAL":
            assert evidence
        for item in evidence:
            if "::" not in item:
                assert feature["state"] == "S3C_NG_MISSING", (feature["family"], item)
                continue
            selector = item.split(" (", maxsplit=1)[0]
            path_text, test_name = selector.split("::", maxsplit=1)
            test_path = repository / path_text
            assert test_path.is_file(), selector
            assert f"def {test_name}(" in test_path.read_text(encoding="utf-8"), selector
