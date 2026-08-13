from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).with_name("validate_remote_write.py")
SPEC = importlib.util.spec_from_file_location("validate_remote_write", TOOL_PATH)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TOOL
SPEC.loader.exec_module(TOOL)


def scan(workflow: str, *, target: str = "research/zettelkasten-lab-20260812", changed: tuple[str, ...] = ("research-lab/STATE.json",)):
    return TOOL.scan_workflows(
        {"fixture.yml": workflow},
        target_ref=target,
        event_type="push",
        proposed_head="fixture-head",
        changed_files=changed,
    )


class RemoteWriteValidatorTests(unittest.TestCase):
    def test_control_a_nested_on_mapping_is_unknown(self) -> None:
        result = scan("workflow:\n  on:\n    push:\n")
        self.assertEqual(result.classification, "UNKNOWN")

    def test_control_b_matching_research_branch_is_possible(self) -> None:
        result = scan("name: fixture\non:\n  push:\n    branches: [research/zettelkasten-lab-20260812]\n")
        self.assertEqual(result.classification, "ACTIONS_POSSIBLE")
        self.assertEqual(result.possible_actions_run_count, 1)

    def test_control_c_main_only_push_does_not_match_research(self) -> None:
        result = scan("name: fixture\non:\n  push:\n    branches: [main]\n")
        self.assertEqual(result.classification, "PROVEN_ZERO_ACTIONS")
        self.assertEqual(result.possible_actions_run_count, 0)

    def test_control_d_matching_research_path_is_possible(self) -> None:
        result = scan("name: fixture\non:\n  push:\n    paths:\n      - \"research-lab/**\"\n")
        self.assertEqual(result.classification, "ACTIONS_POSSIBLE")

    def test_control_e_unsupported_trigger_key_is_unknown(self) -> None:
        result = scan("name: fixture\non:\n  push:\n    types: [synchronize]\n")
        self.assertEqual(result.classification, "UNKNOWN")

    def test_control_f_malformed_yaml_is_unknown(self) -> None:
        result = scan("name: fixture\non:\n  push: [\n")
        self.assertEqual(result.classification, "UNKNOWN")

    def test_dispatch_is_not_an_ordinary_push(self) -> None:
        result = scan("name: fixture\non:\n  workflow_dispatch:\n")
        self.assertEqual(result.classification, "PROVEN_ZERO_ACTIONS")
        self.assertTrue(result.manual_trigger_available)

    def test_pull_request_semantics_fail_closed(self) -> None:
        result = TOOL.scan_workflows(
            {"fixture.yml": "name: fixture\non:\n  pull_request:\n"},
            target_ref="main",
            event_type="pull_request",
            proposed_head="fixture-head",
            changed_files=("bootstrap/s3/__init__.py",),
        )
        self.assertEqual(result.classification, "UNKNOWN")

    def test_trigger_drift_distinguishes_unsafe_broadening(self) -> None:
        main = "name: fixture\non:\n  push:\n    branches: [main]\n"
        broad = "name: fixture\non:\n  push:\n"
        fixed = "name: fixture\non:\n  push:\n    branches: [main]\n"
        self.assertEqual(
            TOOL.compare_trigger_policy(
                {"fixture.yml": main},
                {"fixture.yml": broad},
                candidate_ref="research/zettelkasten-lab-20260812",
            ),
            "UNSAFE_DIVERGENCE",
        )
        self.assertEqual(
            TOOL.compare_trigger_policy(
                {"fixture.yml": main},
                {"fixture.yml": fixed},
                candidate_ref="research/zettelkasten-lab-20260812",
            ),
            "NONE",
        )


if __name__ == "__main__":
    unittest.main()
