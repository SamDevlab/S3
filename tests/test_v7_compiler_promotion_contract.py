from __future__ import annotations

import json
import re
from pathlib import Path

from tools.characterize_s3c_ng_provider import _workloads


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
    assert commands["doctor"]["state"] == (
        "HOST_DIAGNOSTIC_WITH_CANDIDATE_IDENTITY_AND_BOOTSTRAP_PIN"
    )

    run = commands["container run"]
    assert run["semantic_compilation"] == "INDIRECT"
    assert run["s3c_ng_required_for_promotion"] is True
    assert run["s3c_ng_supported_now"] is True
    assert run["promotion_blocker_if_unsupported"] is True
    bootstrap = commands["bootstrap install s3c-ng"]
    assert bootstrap["semantic_compilation"] is False
    assert bootstrap["s3c_ng_supported_now"] is False
    assert bootstrap["state"] == "EXPLICIT_RELEASE_INSTALLER_LOCK_UNPUBLISHED"
    assert document["bootstrap"]["candidate_packager_source_identity"] == (
        "REQUIRES_CHECKOUT_HEAD_AND_CLEAN_COMPILER_INPUTS_AND_RECOMPUTED_SOURCE_GRAPH_TO_MATCH_MANIFEST"
    )
    assert document["default_compiler"] == "PYTHON"
    assert document["promoted_default"] is False
    assert document["performance_characterization"]["state"] in {
        "PENDING_EXACT_HEAD_LINUX_X86_64_RUN",
        "PASS_EXACT_HEAD_LINUX_X86_64",
    }
    assert document["performance_characterization"]["classification"] == (
        "CHARACTERIZATION_ONLY"
    )
    assert document["platform_scope"] == {
        "native_candidate_target": "linux-x86_64",
        "trusted_bootstrap_targets": ["linux-x86_64"],
        "s3c_ng_supported_now_applies_only_to": "linux-x86_64",
        "global_promotion": False,
    }


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


def test_v7_performance_characterization_has_required_workload_classes() -> None:
    repository = Path(__file__).parents[1]
    workloads = _workloads(repository)

    assert [workload.name for workload in workloads] == [
        "small",
        "multimodule-ordering-search",
        "real-pebble-workload",
        "self-source",
    ]
    assert len(workloads[0].sources) == 1
    assert len(workloads[1].sources) > 1
    assert len(workloads[2].sources["main.s3"]) > 50_000
    assert set(workloads[3].sources) == {
        "app.s3",
        "character_classes.s3",
        "lexer.s3",
        "types.s3",
        "parser.s3",
        "semantic.s3",
        "ir.s3",
        "modules.s3",
    }


def test_bootstrap_evidence_uses_the_real_candidate_source_commit() -> None:
    workflow_path = Path(__file__).parents[1] / ".github" / "workflows" / "tests.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    source_ref = "${{ github.event.pull_request.head.sha || github.sha }}"

    def job_block(job_name: str) -> str:
        match = re.search(
            rf"(?ms)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:|\Z)",
            workflow,
        )
        assert match is not None, job_name
        return match.group(1)

    def has_indented_line(block: str, line: str) -> bool:
        return re.search(rf"(?m)^{re.escape(line)}$", block) is not None

    seed = job_block("s3c-ng-bootstrap-seed")
    clean = job_block("s3c-ng-clean-bootstrap")
    assert has_indented_line(seed, "          ref: " + source_ref)
    assert has_indented_line(clean, "          ref: " + source_ref)
    assert has_indented_line(seed, "          name: s3c-ng-bootstrap-" + source_ref)
    assert has_indented_line(clean, "          name: s3c-ng-bootstrap-" + source_ref)
    assert has_indented_line(
        clean, "          name: s3c-ng-provider-performance-" + source_ref
    )
