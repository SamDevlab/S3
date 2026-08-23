"""Deterministic impact-aware and resumable local pytest orchestration."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RUNNER_VERSION = "s3test.v1"
IMPACT_SCHEMA = "s3.test-impact.v1"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_STATE_DIR = ".s3-test-state"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_TIMEOUT = "TIMEOUT"


class T4TimeoutClass(str, Enum):
    DEFAULT = "DEFAULT"
    HEAVY_SELF_HOSTING = "HEAVY_SELF_HOSTING"
    HEAVY_RENDERER = "HEAVY_RENDERER"
    HEAVY_NATIVE_INTEGRATION = "HEAVY_NATIVE_INTEGRATION"


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    timeout_class: T4TimeoutClass
    seconds: int


class S3TestOrchestratorError(ValueError):
    """Raised when a local orchestration contract is invalid."""


@dataclass(frozen=True, slots=True)
class ImpactRule:
    pattern: str
    tests: tuple[str, ...]
    milestones: tuple[str, ...]
    shards: tuple[str, ...]
    native_required: bool
    environment_requirements: tuple[str, ...]
    global_impact: bool


@dataclass(frozen=True, slots=True)
class Selection:
    test: str
    reasons: tuple[str, ...]
    tiers: tuple[str, ...]
    native_required: bool
    environment_requirements: tuple[str, ...]
    milestones: tuple[str, ...]
    shards: tuple[str, ...]


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


class ImpactMap:
    def __init__(self, path: Path, data: Mapping[str, Any]) -> None:
        if data.get("schema") != IMPACT_SCHEMA:
            raise S3TestOrchestratorError("unsupported impact manifest schema")
        version = data.get("version")
        if not isinstance(version, int) or version < 1:
            raise S3TestOrchestratorError("impact manifest version must be positive")
        raw_rules = data.get("rules")
        if not isinstance(raw_rules, list):
            raise S3TestOrchestratorError("impact manifest rules must be a list")
        self.path = path
        self.version = version
        self.shards = {
            str(name): tuple(sorted(str(item) for item in tests))
            for name, tests in dict(data.get("shards", {})).items()
        }
        self.default = self._rule_from_data("<default>", data.get("default", {}))
        self.rules = tuple(
            self._rule_from_data(str(raw.get("pattern", "")), raw)
            for raw in raw_rules
        )
        raw_timeout_policy = data.get("timeout_policy", {})
        if not isinstance(raw_timeout_policy, Mapping):
            raise S3TestOrchestratorError("timeout_policy must be an object")
        raw_classes = raw_timeout_policy.get("classes", {
            T4TimeoutClass.DEFAULT.value: {"seconds": DEFAULT_TIMEOUT_SECONDS},
        })
        raw_assignments = raw_timeout_policy.get("assignments", {})
        if not isinstance(raw_classes, Mapping) or not isinstance(raw_assignments, Mapping):
            raise S3TestOrchestratorError("timeout_policy classes and assignments must be objects")
        self._timeout_policies: dict[T4TimeoutClass, int] = {}
        for raw_name, raw_config in raw_classes.items():
            try:
                timeout_class = T4TimeoutClass(str(raw_name))
            except ValueError as error:
                raise S3TestOrchestratorError(f"unknown timeout class {raw_name!r}") from error
            if not isinstance(raw_config, Mapping):
                raise S3TestOrchestratorError(f"timeout class {raw_name!r} must be an object")
            seconds = raw_config.get("seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 1:
                raise S3TestOrchestratorError(f"timeout class {raw_name!r} requires positive seconds")
            self._timeout_policies[timeout_class] = seconds
        if T4TimeoutClass.DEFAULT not in self._timeout_policies:
            raise S3TestOrchestratorError("timeout_policy must define DEFAULT")
        self._timeout_assignments: dict[str, T4TimeoutClass] = {}
        for raw_test, raw_name in raw_assignments.items():
            try:
                timeout_class = T4TimeoutClass(str(raw_name))
            except ValueError as error:
                raise S3TestOrchestratorError(f"unknown timeout class {raw_name!r}") from error
            if timeout_class not in self._timeout_policies:
                raise S3TestOrchestratorError(f"timeout class {raw_name!r} has no configured budget")
            self._timeout_assignments[_normalize_path(str(raw_test))] = timeout_class
        self.timeout_policy_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "classes": {
                        timeout_class.value: seconds
                        for timeout_class, seconds in sorted(
                            self._timeout_policies.items(), key=lambda item: item[0].value
                        )
                    },
                    "assignments": {
                        test: timeout_class.value
                        for test, timeout_class in sorted(self._timeout_assignments.items())
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def timeout_policy_for(self, test: str, default_seconds: int) -> TimeoutPolicy:
        timeout_class = self._timeout_assignments.get(_normalize_path(test), T4TimeoutClass.DEFAULT)
        seconds = default_seconds if timeout_class is T4TimeoutClass.DEFAULT else self._timeout_policies[timeout_class]
        return TimeoutPolicy(timeout_class, seconds)

    @classmethod
    def load(cls, path: str | Path) -> "ImpactMap":
        manifest_path = Path(path).resolve()
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise S3TestOrchestratorError(f"cannot read impact manifest: {error}") from error
        if not isinstance(data, Mapping):
            raise S3TestOrchestratorError("impact manifest must contain an object")
        return cls(manifest_path, data)

    @staticmethod
    def _rule_from_data(pattern: str, raw: Mapping[str, Any]) -> ImpactRule:
        if not pattern:
            raise S3TestOrchestratorError("impact rule pattern must be non-empty")
        tests = raw.get("tests", [])
        milestones = raw.get("milestones", [])
        shards = raw.get("shards", [])
        requirements = raw.get("environment_requirements", [])
        if not all(isinstance(items, list) for items in (tests, milestones, shards, requirements)):
            raise S3TestOrchestratorError(f"impact rule {pattern!r} lists must be arrays")
        native_required = raw.get("native_required", False)
        global_impact = raw.get("global_impact", False)
        if not isinstance(native_required, bool) or not isinstance(global_impact, bool):
            raise S3TestOrchestratorError(f"impact rule {pattern!r} flags must be boolean")
        return ImpactRule(
            pattern,
            _sorted_unique(str(item) for item in tests),
            _sorted_unique(str(item) for item in milestones),
            _sorted_unique(str(item) for item in shards),
            native_required,
            _sorted_unique(str(item) for item in requirements),
            global_impact,
        )

    def _matches(self, pattern: str, path: str) -> bool:
        if pattern.startswith("{") and pattern.endswith("}"):
            alternatives = pattern[1:-1].split(",")
            return any(self._matches(item, path) for item in alternatives)
        return fnmatch.fnmatchcase(path, pattern)

    def select(
        self,
        changed_files: Sequence[str],
        *,
        milestone: str | None = None,
        all_tests: Sequence[str] = (),
    ) -> tuple[Selection, ...]:
        normalized = tuple(sorted({_normalize_path(path) for path in changed_files if path}))
        matches: list[tuple[str, ImpactRule, str]] = []
        for changed in normalized:
            matched = [rule for rule in self.rules if self._matches(rule.pattern, changed)]
            if not matched:
                # A synthetic milestone selector must resolve through the
                # milestone metadata, not the generic default profile.
                matched = [] if milestone is not None and changed.startswith("milestone:") else [self.default]
            for rule in matched:
                if milestone is None or milestone in rule.milestones or "global" in rule.milestones:
                    matches.extend((changed, rule, "direct impact mapping") for _ in (0,))
        if milestone is not None and not matches:
            for rule in self.rules:
                if milestone in rule.milestones:
                    matches.append((f"milestone:{milestone}", rule, "milestone mapping"))
        selected: dict[str, dict[str, Any]] = {}
        for changed in normalized:
            if fnmatch.fnmatchcase(changed, "tests/test_*.py"):
                entry = selected.setdefault(
                    changed,
                    {"reasons": [], "tiers": [], "native": False, "env": [], "milestones": [], "shards": []},
                )
                entry["reasons"].append(f"changed test file: {changed}")
                entry["tiers"].append("T1")
        for changed, rule, reason in matches:
            tests = all_tests if rule.global_impact else rule.tests
            for test in tests:
                entry = selected.setdefault(
                    test,
                    {"reasons": [], "tiers": [], "native": False, "env": [], "milestones": [], "shards": []},
                )
                entry["reasons"].append(f"{reason}: {changed} -> {test}")
                entry["tiers"].append("T2" if milestone else "T1")
                entry["native"] = entry["native"] or rule.native_required
                entry["env"].extend(rule.environment_requirements)
                entry["milestones"].extend(rule.milestones)
                entry["shards"].extend(rule.shards)
        return tuple(
            Selection(
                test=test,
                reasons=tuple(sorted(set(values["reasons"]))),
                tiers=_sorted_unique(values["tiers"]),
                native_required=bool(values["native"]),
                environment_requirements=_sorted_unique(values["env"]),
                milestones=_sorted_unique(values["milestones"]),
                shards=_sorted_unique(values["shards"]),
            )
            for test, values in sorted(selected.items())
        )

    def shard_tests(self, name: str) -> tuple[str, ...]:
        try:
            return self.shards[name]
        except KeyError as error:
            raise S3TestOrchestratorError(f"unknown shard {name!r}") from error


def discover_tests(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in (root / "tests").glob("test_*.py")
            if path.is_file()
        )
    )


def changed_files(root: Path, base: str | None = None) -> tuple[str, ...]:
    names: set[str] = set()
    if base:
        output = _git(root, "diff", "--name-only", f"{base}...HEAD")
        names.update(line.strip() for line in output.splitlines() if line.strip())
    else:
        output = _git(root, "diff", "--name-only", "HEAD")
        cached = _git(root, "diff", "--cached", "--name-only")
        names.update(line.strip() for line in output.splitlines() if line.strip())
        names.update(line.strip() for line in cached.splitlines() if line.strip())
        untracked = _git(root, "ls-files", "--others", "--exclude-standard")
        names.update(line.strip() for line in untracked.splitlines() if line.strip())
    return tuple(sorted({_normalize_path(name) for name in names}))


def _dirty_payload(root: Path) -> bytes:
    parts = [
        _git(root, "diff", "--binary", "HEAD"),
        _git(root, "diff", "--cached", "--binary"),
    ]
    for name in changed_files(root):
        path = root / name
        if path.is_file() and not name.startswith(".s3-test-state/"):
            parts.append(f"UNTRACKED:{name}\n")
            parts.append(path.read_bytes().decode("utf-8", errors="surrogateescape"))
    return "\n".join(parts).encode("utf-8", errors="surrogateescape")


def execution_fingerprint(
    root: Path,
    selected_tests: Sequence[str],
    *,
    manifest_version: int,
    runner_version: str = RUNNER_VERSION,
    timeout_policy_fingerprint: str = "",
) -> str:
    head = _git(root, "rev-parse", "HEAD").strip()
    payload = {
        "head": head,
        "dirty_diff_sha256": hashlib.sha256(_dirty_payload(root)).hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "selected_tests": sorted(selected_tests),
        "impact_manifest_version": manifest_version,
        "runner_version": runner_version,
        "timeout_policy_fingerprint": timeout_policy_fingerprint,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class StateStore:
    def __init__(self, root: Path, relative: str = DEFAULT_STATE_DIR) -> None:
        self.path = root / relative

    @property
    def latest(self) -> Path:
        return self.path / "latest.json"

    def load(self) -> dict[str, Any] | None:
        if not self.latest.is_file():
            return None
        try:
            value = json.loads(self.latest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise S3TestOrchestratorError(f"cannot read saved test state: {error}") from error
        if not isinstance(value, dict):
            raise S3TestOrchestratorError("saved test state must be an object")
        return value

    def save(self, report: Mapping[str, Any]) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        fingerprint = str(report["fingerprint"])
        (self.path / f"{fingerprint}.json").write_text(rendered, encoding="utf-8", newline="\n")
        self.latest.write_text(rendered, encoding="utf-8", newline="\n")
        markdown = [
            "# S3 Smart Test Run",
            "",
            f"- Profile: {report['profile']}",
            f"- Fingerprint: {fingerprint}",
            f"- Status: {report['summary']['status']}",
            "",
            "| Test | Status | Tier | Reason |",
            "|---|---|---|---|",
        ]
        for item in report["tests"]:
            markdown.append(f"| {item['test']} | {item['status']} | {','.join(item['tiers'])} | {item['reason']} |")
        (self.path / "latest.md").write_text("\n".join(markdown) + "\n", encoding="utf-8", newline="\n")


def _terminate(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def run_pytest_file(root: Path, test: str, timeout_seconds: int) -> dict[str, Any]:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    start_new_session = os.name != "nt"
    process = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", test],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate(process)
        output, _ = process.communicate()
        return {"status": STATUS_TIMEOUT, "output": output[-4000:], "returncode": None}
    return {
        "status": STATUS_PASS if process.returncode == 0 else STATUS_FAIL,
        "output": output[-4000:],
        "returncode": process.returncode,
    }


def _profile_selection(
    root: Path,
    impact: ImpactMap,
    profile: str,
    argument: str | None,
    base: str | None,
) -> tuple[tuple[Selection, ...], tuple[str, ...]]:
    all_tests = discover_tests(root)
    if profile == "full":
        return tuple(
            Selection(test, ("full certification profile",), ("T4",), False, (), ("global",), ())
            for test in all_tests
        ), all_tests
    if profile == "sanity":
        tests = ("tests/test_m146_test_runner.py", "tests/test_cli_source_syntax.py")
        return tuple(
            Selection(test, ("T0 sanity profile",), ("T0",), False, (), ("sanity",), ("compiler",))
            for test in tests
        ), tests
    if profile == "milestone":
        if not argument:
            raise S3TestOrchestratorError("milestone requires an identifier")
        changed = [f"milestone:{argument}"]
        selected = impact.select(changed, milestone=argument, all_tests=all_tests)
        return selected, tuple(item.test for item in selected)
    if profile == "shard":
        if not argument:
            raise S3TestOrchestratorError("shard requires a name")
        tests = impact.shard_tests(argument)
        return tuple(
            Selection(test, (f"shard profile: {argument}",), ("T3",), False, (), (argument,), (argument,))
            for test in tests
        ), tests
    if profile == "level-c":
        tests = impact.shard_tests("m241-m249-level-c")
        if not tests:
            raise S3TestOrchestratorError("level-c integration shard is empty")
        return tuple(
            Selection(
                test,
                ("M2.41-M2.49 Level-C integration checkpoint",),
                ("LEVEL-C",),
                False,
                (),
                ("m250",),
                ("m241-m249-level-c",),
            )
            for test in tests
        ), tests
    if profile == "level-c-full":
        tests = impact.shard_tests("m241-m259-level-c")
        if not tests:
            raise S3TestOrchestratorError("level-c full-cycle shard is empty")
        return tuple(
            Selection(
                test,
                ("M2.41-M2.59 Level-C full-cycle checkpoint",),
                ("LEVEL-C",),
                False,
                (),
                ("m260",),
                ("m241-m259-level-c",),
            )
            for test in tests
        ), tests
    selected = impact.select(changed_files(root, base), all_tests=all_tests)
    return selected, tuple(item.test for item in selected)


def render_plan(
    selections: Sequence[Selection],
    changed: Sequence[str],
    *,
    timeout_policies: Mapping[str, TimeoutPolicy] | None = None,
) -> str:
    lines = ["S3 SMART TEST PLAN", *[f"CHANGED_FILE={item}" for item in changed]]
    for selection in selections:
        timeout_policy = (timeout_policies or {}).get(
            selection.test,
            TimeoutPolicy(T4TimeoutClass.DEFAULT, DEFAULT_TIMEOUT_SECONDS),
        )
        lines.extend(
            [
                f"SELECTED_TEST={selection.test}",
                f"REASON={' ; '.join(selection.reasons)}",
                f"TIER={','.join(selection.tiers)}",
                f"NATIVE_REQUIRED={'YES' if selection.native_required else 'NO'}",
                f"TIMEOUT_CLASS={timeout_policy.timeout_class.value}",
                f"TIMEOUT={timeout_policy.seconds}s",
            ]
        )
    if not selections:
        lines.append("SELECTED_TEST=NONE")
    return "\n".join(lines) + "\n"


def execute_profile(
    root: Path,
    impact: ImpactMap,
    profile: str,
    argument: str | None,
    base: str | None,
    timeout_seconds: int,
    state: StateStore,
) -> dict[str, Any]:
    previous = state.load() if profile == "resume" else None
    if profile == "resume":
        if previous is None:
            raise S3TestOrchestratorError("no resumable test state exists")
        saved_tests = tuple(
            str(item["test"])
            for item in previous.get("tests", [])
            if isinstance(item, Mapping) and isinstance(item.get("test"), str)
        )
        fingerprint = execution_fingerprint(
            root,
            saved_tests,
            manifest_version=impact.version,
            timeout_policy_fingerprint=impact.timeout_policy_fingerprint,
        )
        if previous.get("fingerprint") != fingerprint:
            raise S3TestOrchestratorError("saved state fingerprint is stale; refusing cache reuse")
        pending = {
            result["test"]
            for result in previous.get("tests", [])
            if isinstance(result, Mapping) and result.get("status") not in {STATUS_PASS, "SKIP"}
        }
        selections = tuple(
            Selection(test, ("resumed from persisted failure state",), ("T1",), False, (), (), ())
            for test in saved_tests
            if test in pending
        )
        tests = tuple(item.test for item in selections)
    else:
        selections, tests = _profile_selection(root, impact, profile, argument, base)
        fingerprint = execution_fingerprint(
            root,
            tests,
            manifest_version=impact.version,
            timeout_policy_fingerprint=impact.timeout_policy_fingerprint,
        )
    reports=[]
    for selection in selections:
        timeout_policy = impact.timeout_policy_for(selection.test, timeout_seconds)
        result = run_pytest_file(root, selection.test, timeout_policy.seconds)
        reports.append({
            "test": selection.test,
            "status": result["status"],
            "tiers": list(selection.tiers),
            "reason": "; ".join(selection.reasons),
            "native_required": selection.native_required,
            "environment_requirements": list(selection.environment_requirements),
            "output": result["output"],
            "returncode": result["returncode"],
            "timeout_class": timeout_policy.timeout_class.value,
            "timeout_seconds": timeout_policy.seconds,
        })
    statuses=[item["status"] for item in reports]
    overall=STATUS_TIMEOUT if STATUS_TIMEOUT in statuses else STATUS_FAIL if STATUS_FAIL in statuses else STATUS_PASS
    report={
        "schema": "s3.smart-test-report",
        "schema_version": "s3.smart-test-report.v1",
        "runner_version": RUNNER_VERSION,
        "profile": profile,
        "argument": argument,
        "base": base,
        "head": _git(root, "rev-parse", "HEAD").strip(),
        "fingerprint": fingerprint,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tests": reports,
        "summary": {
            "status": overall,
            "passed": statuses.count(STATUS_PASS),
            "failed": statuses.count(STATUS_FAIL),
            "timed_out": statuses.count(STATUS_TIMEOUT),
            "selected": len(reports),
        },
        "resume_eligible": overall == STATUS_PASS or any(status in {STATUS_FAIL, STATUS_TIMEOUT} for status in statuses),
        "environment_blocks": sorted({req for item in selections for req in item.environment_requirements}),
    }
    state.save(report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("plan", "sanity", "affected", "milestone", "shard", "level-c", "level-c-full", "resume", "full"))
    parser.add_argument("argument", nargs="?")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base")
    parser.add_argument("--impact", type=Path)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--state-dir", default=DEFAULT_STATE_DIR)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    impact_path = (args.impact or root / "tests" / "test-impact.json").resolve()
    impact = ImpactMap.load(impact_path)
    state = StateStore(root, args.state_dir)
    if args.timeout < 1:
        raise S3TestOrchestratorError("timeout must be positive")
    if args.profile == "plan":
        selections, _ = _profile_selection(root, impact, "affected", None, args.base)
        timeout_policies = {
            item.test: impact.timeout_policy_for(item.test, args.timeout)
            for item in selections
        }
        print(render_plan(selections, changed_files(root, args.base), timeout_policies=timeout_policies), end="")
        return 0
    if args.profile == "resume":
        report = execute_profile(root, impact, "resume", None, args.base, args.timeout, state)
    else:
        report = execute_profile(root, impact, args.profile, args.argument, args.base, args.timeout, state)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        timeout_policies = {
            item["test"]: TimeoutPolicy(T4TimeoutClass(item["timeout_class"]), int(item["timeout_seconds"]))
            for item in report["tests"]
        }
        print(render_plan(
            tuple(
                Selection(item["test"], (item["reason"],), tuple(item["tiers"]), item["native_required"], tuple(item["environment_requirements"]), (), ()
                ) for item in report["tests"]
            ),
            (),
            timeout_policies=timeout_policies,
        ), end="")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["status"] == STATUS_PASS else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except S3TestOrchestratorError as error:
        print(f"s3test: {error}", file=sys.stderr)
        raise SystemExit(2)
