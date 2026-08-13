#!/usr/bin/env python3
"""Fail-closed local simulation of workflow-triggered remote-write risk.

This intentionally models only the small trigger subset needed by the S3
research lab. It does not emulate GitHub Actions. Any syntax outside the
bounded model is UNKNOWN and therefore non-zero.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


SUPPORTED_EVENTS = {"push", "pull_request", "workflow_dispatch"}
SUPPORTED_FILTERS = {"branches", "branches-ignore", "paths", "paths-ignore"}
FULL_SHA_LENGTH = 40


class WorkflowModelError(ValueError):
    """The workflow is outside the bounded, safe-to-evaluate syntax."""


@dataclass(frozen=True)
class Trigger:
    event: str
    filters: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class Workflow:
    path: str
    triggers: Mapping[str, Trigger]


@dataclass(frozen=True)
class ScanResult:
    target_ref: str
    event_type: str
    proposed_head: str
    changed_files: tuple[str, ...]
    workflows_scanned: int
    matched_workflows: tuple[str, ...]
    possible_actions_run_count: int | None
    manual_trigger_available: bool
    classification: str
    detail: str
    target_head_before: str = ""


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    text: str


def _logical_lines(text: str) -> list[_Line]:
    lines: list[_Line] = []
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if "\t" in raw:
            raise WorkflowModelError(f"line {number}: tabs are unsupported")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in {"---", "..."}:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append(_Line(number, indent, stripped))
    return lines


def _key_value(line: _Line) -> tuple[str, str]:
    key, separator, value = line.text.partition(":")
    if not separator or not key.strip() or key.strip().startswith("-"):
        raise WorkflowModelError(f"line {line.number}: expected a mapping entry")
    key = key.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        key = key[1:-1]
    return key, value.strip()


def _unquote(value: str, line_number: int) -> str:
    value = value.strip()
    if not value:
        raise WorkflowModelError(f"line {line_number}: empty filter item")
    if value[0] in {"'", '"'}:
        if len(value) < 2 or value[-1] != value[0]:
            raise WorkflowModelError(f"line {line_number}: unterminated quoted value")
        return value[1:-1]
    if value.startswith(("&", "*", "!")):
        raise WorkflowModelError(f"line {line_number}: YAML alias/tag/negation is unsupported")
    return value


def _split_inline(value: str, line_number: int) -> list[str]:
    if not value.startswith("[") or not value.endswith("]"):
        raise WorkflowModelError(f"line {line_number}: expected an inline sequence")
    body = value[1:-1].strip()
    if not body:
        raise WorkflowModelError(f"line {line_number}: empty filter sequence")
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in body:
        if quote:
            current.append(character)
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            current.append(character)
        elif character == ",":
            item = "".join(current).strip()
            if not item:
                raise WorkflowModelError(f"line {line_number}: empty filter item")
            parts.append(item)
            current = []
        else:
            current.append(character)
    if quote:
        raise WorkflowModelError(f"line {line_number}: unterminated inline sequence")
    item = "".join(current).strip()
    if not item:
        raise WorkflowModelError(f"line {line_number}: empty filter item")
    parts.append(item)
    return [_unquote(part, line_number) for part in parts]


def _filter_values(value: str, lines: list[_Line], index: int, end: int) -> tuple[tuple[str, ...], int]:
    if value:
        return tuple(_split_inline(value, lines[index - 1].number)), index

    values: list[str] = []
    while index < end and lines[index].indent > 4:
        line = lines[index]
        if line.indent != 6 or not line.text.startswith("- "):
            raise WorkflowModelError(f"line {line.number}: unsupported filter sequence")
        values.append(_unquote(line.text[2:].strip(), line.number))
        index += 1
    if not values:
        raise WorkflowModelError(f"line {lines[index - 1].number}: empty filter mapping")
    return tuple(values), index


def parse_workflow(text: str, path: str = "<memory>") -> Workflow:
    """Parse only workflow trigger policy; unsupported syntax fails closed."""

    lines = _logical_lines(text)
    top_level = [line for line in lines if line.indent == 0]
    on_lines = [line for line in top_level if _key_value(line)[0] == "on"]
    if len(on_lines) != 1:
        raise WorkflowModelError(f"{path}: expected exactly one top-level on mapping")
    on_line = on_lines[0]
    _, on_value = _key_value(on_line)
    if on_value:
        raise WorkflowModelError(f"{path}:{on_line.number}: inline on syntax is unsupported")

    on_index = lines.index(on_line)
    end = next((index for index in range(on_index + 1, len(lines)) if lines[index].indent == 0), len(lines))
    triggers: dict[str, Trigger] = {}
    index = on_index + 1
    while index < end:
        event_line = lines[index]
        if event_line.indent != 2:
            raise WorkflowModelError(f"{path}:{event_line.number}: event indentation is unsupported")
        event, event_value = _key_value(event_line)
        if event not in SUPPORTED_EVENTS:
            raise WorkflowModelError(f"{path}:{event_line.number}: unsupported event {event!r}")
        if event in triggers:
            raise WorkflowModelError(f"{path}:{event_line.number}: duplicate event {event!r}")
        if event_value and event_value not in {"{}", "null", "~"}:
            raise WorkflowModelError(f"{path}:{event_line.number}: inline event mapping is unsupported")
        index += 1
        filters: dict[str, tuple[str, ...]] = {}
        while index < end and lines[index].indent > 2:
            filter_line = lines[index]
            if filter_line.indent != 4:
                raise WorkflowModelError(f"{path}:{filter_line.number}: nested trigger syntax is unsupported")
            filter_name, filter_value = _key_value(filter_line)
            if filter_name not in SUPPORTED_FILTERS:
                raise WorkflowModelError(f"{path}:{filter_line.number}: unsupported trigger key {filter_name!r}")
            if filter_name in filters:
                raise WorkflowModelError(f"{path}:{filter_line.number}: duplicate trigger key {filter_name!r}")
            index += 1
            values, index = _filter_values(filter_value, lines, index, end)
            if any("!" in value for value in values):
                raise WorkflowModelError(f"{path}:{filter_line.number}: negated patterns are unsupported")
            filters[filter_name] = values
        triggers[event] = Trigger(event, filters)

    if not triggers:
        raise WorkflowModelError(f"{path}: empty on mapping")
    return Workflow(path, triggers)


def _branch_name(target_ref: str) -> str:
    value = target_ref.strip()
    if value.startswith("refs/heads/"):
        value = value[len("refs/heads/") :]
    if not value or value.startswith("refs/") or "\n" in value:
        raise WorkflowModelError(f"unsupported target ref {target_ref!r}")
    return value


def _pattern_matches(pattern: str, value: str) -> bool:
    if not pattern or pattern.startswith("!"):
        raise WorkflowModelError("empty or negated patterns are unsupported")
    return fnmatch.fnmatchcase(value, pattern)


def _filter_match(trigger: Trigger, target_ref: str, changed_files: tuple[str, ...]) -> bool:
    filters = trigger.filters
    if "branches" in filters and "branches-ignore" in filters:
        raise WorkflowModelError(f"{trigger.event}: branches and branches-ignore are ambiguous")
    if "paths" in filters and "paths-ignore" in filters:
        raise WorkflowModelError(f"{trigger.event}: paths and paths-ignore are ambiguous")

    branch = _branch_name(target_ref)
    if "branches" in filters and not any(_pattern_matches(pattern, branch) for pattern in filters["branches"]):
        return False
    if "branches-ignore" in filters and any(
        _pattern_matches(pattern, branch) for pattern in filters["branches-ignore"]
    ):
        return False

    if not changed_files:
        raise WorkflowModelError("push evaluation requires a non-empty changed file set")
    if "paths" in filters and not any(
        _pattern_matches(pattern, path) for pattern in filters["paths"] for path in changed_files
    ):
        return False
    if "paths-ignore" in filters and all(
        any(_pattern_matches(pattern, path) for pattern in filters["paths-ignore"])
        for path in changed_files
    ):
        return False
    return True


def scan_workflows(
    workflow_texts: Mapping[str, str],
    *,
    target_ref: str,
    event_type: str,
    proposed_head: str,
    changed_files: Iterable[str],
    target_head_before: str | None = None,
) -> ScanResult:
    if event_type not in SUPPORTED_EVENTS:
        raise WorkflowModelError(f"unsupported event type {event_type!r}")
    changed = tuple(sorted({path.replace("\\", "/") for path in changed_files if path}))
    if not workflow_texts:
        return ScanResult(
            target_ref,
            event_type,
            proposed_head,
            changed,
            0,
            (),
            None,
            False,
            "UNKNOWN",
            "no workflow files were found",
            target_head_before or target_ref,
        )

    workflows: list[Workflow] = []
    try:
        workflows = [parse_workflow(text, path) for path, text in sorted(workflow_texts.items())]
        manual = any("workflow_dispatch" in workflow.triggers for workflow in workflows)
        if event_type == "pull_request":
            return ScanResult(
                target_ref,
                event_type,
                proposed_head,
                changed,
                len(workflows),
                (),
                None,
                manual,
                "UNKNOWN",
                "pull_request merge/ref semantics are outside this bounded model",
                target_head_before or target_ref,
            )
        if event_type == "workflow_dispatch":
            matched = tuple(
                workflow.path for workflow in workflows if "workflow_dispatch" in workflow.triggers
            )
            return ScanResult(
                target_ref,
                event_type,
                proposed_head,
                changed,
                len(workflows),
                matched,
                len(matched),
                manual,
                "ACTIONS_POSSIBLE" if matched else "PROVEN_ZERO_ACTIONS",
                "manual dispatch is modeled separately from ordinary pushes",
                target_head_before or target_ref,
            )

        matched = tuple(
            workflow.path
            for workflow in workflows
            if "push" in workflow.triggers and _filter_match(workflow.triggers["push"], target_ref, changed)
        )
    except WorkflowModelError as exc:
        return ScanResult(
            target_ref,
            event_type,
            proposed_head,
            changed,
            len(workflows),
            (),
            None,
            any("workflow_dispatch" in workflow.triggers for workflow in workflows),
            "UNKNOWN",
            str(exc),
            target_head_before or target_ref,
        )

    return ScanResult(
        target_ref,
        event_type,
        proposed_head,
        changed,
        len(workflows),
        matched,
        len(matched),
        manual,
        "ACTIONS_POSSIBLE" if matched else "PROVEN_ZERO_ACTIONS",
        "all workflow triggers were understood and no unsupported construct was found",
        target_head_before or target_ref,
    )


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _full_commit(repo: Path, revision: str) -> str:
    value = _git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()
    if len(value) != FULL_SHA_LENGTH:
        raise WorkflowModelError(f"revision did not resolve to a full commit: {revision}")
    return value


def _workflow_texts_at(repo: Path, revision: str) -> dict[str, str]:
    commit = _full_commit(repo, revision)
    paths = _git(repo, "ls-tree", "-r", "--name-only", commit, "--", ".github/workflows").splitlines()
    workflow_paths = tuple(
        path for path in paths if path.endswith((".yml", ".yaml")) and path.startswith(".github/workflows/")
    )
    return {path: _git(repo, "show", f"{commit}:{path}") for path in workflow_paths}


def compare_trigger_policy(
    reference_workflows: Mapping[str, str],
    candidate_workflows: Mapping[str, str],
    *,
    candidate_ref: str,
) -> str:
    """Classify trigger drift without treating job-body drift as trigger drift."""

    reference = {path: parse_workflow(text, path) for path, text in reference_workflows.items()}
    candidate = {path: parse_workflow(text, path) for path, text in candidate_workflows.items()}
    changed = ("research-lab/STATE.json",)
    semantic_difference = False
    for path in sorted(set(reference) | set(candidate)):
        reference_workflow = reference.get(path)
        candidate_workflow = candidate.get(path)
        if reference_workflow is None or candidate_workflow is None:
            semantic_difference = True
            candidate_matches = bool(
                candidate_workflow
                and "push" in candidate_workflow.triggers
                and _filter_match(candidate_workflow.triggers["push"], candidate_ref, changed)
            )
            reference_matches = bool(
                reference_workflow
                and "push" in reference_workflow.triggers
                and _filter_match(reference_workflow.triggers["push"], candidate_ref, changed)
            )
        else:
            if reference_workflow.triggers == candidate_workflow.triggers:
                continue
            semantic_difference = True
            candidate_matches = bool(
                "push" in candidate_workflow.triggers
                and _filter_match(candidate_workflow.triggers["push"], candidate_ref, changed)
            )
            reference_matches = bool(
                "push" in reference_workflow.triggers
                and _filter_match(reference_workflow.triggers["push"], candidate_ref, changed)
            )
        if candidate_matches and not reference_matches:
            return "UNSAFE_DIVERGENCE"
    return "SAFE_DIVERGENCE" if semantic_difference else "NONE"


def scan_git_state(
    repo: Path,
    target_ref: str,
    proposed_head: str,
    event_type: str,
    target_head_before: str | None = None,
) -> ScanResult:
    proposed = _full_commit(repo, proposed_head)
    diff_base = target_head_before or target_ref
    _full_commit(repo, diff_base)
    changed = _git(repo, "diff", "--name-only", diff_base, proposed).splitlines()
    texts = _workflow_texts_at(repo, proposed)
    return scan_workflows(
        texts,
        target_ref=target_ref,
        event_type=event_type,
        proposed_head=proposed,
        changed_files=changed,
        target_head_before=diff_base,
    )


def _print_result(result: ScanResult) -> None:
    print(f"TARGET_REF={result.target_ref}")
    print(f"TARGET_HEAD_BEFORE={result.target_head_before}")
    print(f"EVENT_TYPE={result.event_type}")
    print(f"PROPOSED_HEAD={result.proposed_head}")
    print(f"WORKFLOWS_SCANNED={result.workflows_scanned}")
    print("MATCHED_WORKFLOWS=" + (",".join(result.matched_workflows) or "NONE"))
    count = "UNKNOWN" if result.possible_actions_run_count is None else str(result.possible_actions_run_count)
    print(f"POSSIBLE_ACTIONS_RUN_COUNT={count}")
    print(f"MANUAL_TRIGGER_AVAILABLE={'YES' if result.manual_trigger_available else 'NO'}")
    print(f"INTENDED_CHANGED_FILES={','.join(result.changed_files) or 'NONE'}")
    print(f"CLASSIFICATION={result.classification}")
    print(f"DETAIL={result.detail}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--target-ref", required=True)
    parser.add_argument("--target-head-before")
    parser.add_argument("--proposed-head", default="HEAD")
    parser.add_argument("--reference-ref")
    parser.add_argument("--event", dest="event_type", default="push", choices=sorted(SUPPORTED_EVENTS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = scan_git_state(
            args.repo_root.resolve(),
            args.target_ref,
            args.proposed_head,
            args.event_type,
            args.target_head_before,
        )
    except (OSError, subprocess.CalledProcessError, WorkflowModelError) as exc:
        print(f"CLASSIFICATION=UNKNOWN")
        print(f"DETAIL={exc}")
        return 1
    if args.reference_ref:
        try:
            reference = _workflow_texts_at(args.repo_root.resolve(), args.reference_ref)
            candidate = _workflow_texts_at(args.repo_root.resolve(), args.proposed_head)
            print(
                "WORKFLOW_TRIGGER_DRIFT="
                + compare_trigger_policy(reference, candidate, candidate_ref=args.target_ref)
            )
        except (OSError, subprocess.CalledProcessError, WorkflowModelError) as exc:
            print("WORKFLOW_TRIGGER_DRIFT=UNKNOWN")
            print(f"DRIFT_DETAIL={exc}")
            return 1
    _print_result(result)
    return 0 if result.classification == "PROVEN_ZERO_ACTIONS" else 1


if __name__ == "__main__":
    sys.exit(main())
