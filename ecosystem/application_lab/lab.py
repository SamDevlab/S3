"""Reproducible application validation layered on S3's own project and test APIs.

Package ``source`` paths are deliberately repository-root-relative, offline, and
contained by the checkout. The package resolver remains responsible for package
identity and graph checks; the S3 test runner remains responsible for compilation,
hosted execution, limits, and expected integer-result comparison.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from bootstrap.s3.package_dependencies import (
    PackageDependencyError,
    PackageLock,
    PackageManifest,
    parse_package_manifest,
)
from bootstrap.s3.project_container import ProjectContainerError, ProjectTooling
from bootstrap.s3.stdlib import standard_library_sources
from bootstrap.s3.test_runner import TestRunnerError, run_test_manifest


PINNED_COMPILER_REVISION = "2eab8a43f07b7fc842c4036ea0fb0203a9d41d6c"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_APPLICATIONS_ROOT = _REPOSITORY_ROOT / "examples" / "applications"
_APPLICATION_MANIFEST = "s3-app.toml"


class ApplicationLabError(ValueError):
    """Raised when an application or its offline package graph is invalid."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_repository_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ApplicationLabError(f"{field} must be a non-empty repository-relative path")
    candidate = PurePosixPath(value.replace("\\", "/"))
    if (
        candidate.is_absolute()
        or not candidate.parts
        or ".." in candidate.parts
        or ":" in candidate.parts[0]
    ):
        raise ApplicationLabError(f"{field} must stay inside the repository")
    path = (_REPOSITORY_ROOT / Path(*candidate.parts)).resolve()
    try:
        path.relative_to(_REPOSITORY_ROOT.resolve())
    except ValueError as error:
        raise ApplicationLabError(f"{field} escapes the repository") from error
    return path


def _load_application(path: Path) -> tuple[dict[str, Any], ProjectTooling]:
    manifest_path = path / _APPLICATION_MANIFEST
    try:
        raw = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ApplicationLabError(f"cannot read {manifest_path.relative_to(_REPOSITORY_ROOT)}") from error
    app = raw.get("application")
    if not isinstance(app, dict) or app.get("schema") != "s3.application.v1":
        raise ApplicationLabError("application manifest requires schema s3.application.v1")
    name = app.get("name")
    if not isinstance(name, str) or not name:
        raise ApplicationLabError("application name is required")
    if app.get("compiler_revision") != PINNED_COMPILER_REVISION:
        raise ApplicationLabError(
            f"{name} must pin compiler revision {PINNED_COMPILER_REVISION}"
        )
    if app.get("execution_mode") not in {
        "COMPILE_ONLY",
        "HOSTED_EXECUTION",
        "NATIVE_EXECUTION",
        "FFI_INTEGRATION",
    }:
        raise ApplicationLabError(f"{name} has an unsupported execution mode")
    expected = app.get("expected_output")
    if app["execution_mode"] != "COMPILE_ONLY" and (
        not isinstance(expected, int) or isinstance(expected, bool)
    ):
        raise ApplicationLabError(f"{name} expected_output must be an integer")
    if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)):
        raise ApplicationLabError(f"{name} expected_output must be an integer")
    fixtures = app.get("fixtures", [])
    if not isinstance(fixtures, list) or any(not isinstance(item, str) for item in fixtures):
        raise ApplicationLabError(f"{name} fixtures must be a list of relative paths")
    tooling = ProjectTooling(path)
    tooling.check()
    return app, tooling


def discover_applications() -> list[dict[str, str]]:
    """Return valid application candidates in stable name order."""

    if not _APPLICATIONS_ROOT.is_dir():
        return []
    found = []
    for manifest in sorted(_APPLICATIONS_ROOT.glob(f"*/{_APPLICATION_MANIFEST}")):
        app, _tooling = _load_application(manifest.parent)
        found.append(
            {
                "name": app["name"],
                "kind": str(app.get("kind", "unspecified")),
                "path": manifest.parent.relative_to(_REPOSITORY_ROOT).as_posix(),
                "execution_mode": app["execution_mode"],
            }
        )
    return found


def _package_graph(application_path: Path) -> tuple[PackageLock, dict[str, Path], dict[str, PackageManifest]]:
    root_manifest = parse_package_manifest(str(application_path / "package.toml"))
    manifests: dict[str, PackageManifest] = {root_manifest.name: root_manifest}
    paths: dict[str, Path] = {root_manifest.name: application_path}
    pending = list(root_manifest.dependencies)
    while pending:
        dependency = pending.pop(0)
        package_path = _safe_repository_path(dependency.source, field="dependency source")
        if not package_path.is_dir():
            raise PackageDependencyError(f"local package directory is missing: {dependency.source}")
        package = parse_package_manifest(str(package_path / "package.toml"))
        if package.name != dependency.name:
            raise PackageDependencyError(
                f"dependency {dependency.name!r} resolves to package {package.name!r}"
            )
        previous = paths.get(package.name)
        if previous is not None and previous.resolve() != package_path.resolve():
            raise PackageDependencyError(f"package {package.name!r} has conflicting local identities")
        if package.name not in manifests:
            manifests[package.name] = package
            paths[package.name] = package_path
            pending.extend(package.dependencies)
    lock = PackageLock.resolve(root_manifest.name, manifests)
    return lock, paths, manifests


def _application_sources(
    application_path: Path,
    app: dict[str, Any],
    tooling: ProjectTooling,
    lock: PackageLock,
    package_paths: dict[str, Path],
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    sources: dict[str, str] = {}
    package_hashes: dict[str, str] = {}
    fixture_names: list[str] = []

    app_sources = tooling.inspect()["sources"]
    for relative in app_sources:
        path = (application_path / relative).resolve()
        try:
            path.relative_to(application_path.resolve())
        except ValueError as error:
            raise ApplicationLabError(f"application source escapes project: {relative}") from error
        if not path.is_file() or path.suffix != ".s3":
            raise ApplicationLabError(f"application source must be an existing S3 file: {relative}")
        logical = Path(relative).as_posix()
        sources[f"sources/{lock.root}/{logical}"] = path.read_text(encoding="utf-8")

    for fixture in app.get("fixtures", []):
        path = (application_path / fixture).resolve()
        try:
            path.relative_to(application_path.resolve())
        except ValueError as error:
            raise ApplicationLabError(f"fixture escapes application: {fixture}") from error
        if not path.is_file() or path.suffix != ".s3":
            raise ApplicationLabError(f"fixture must be an existing S3 source: {fixture}")
        logical = f"sources/{lock.root}/fixtures/{Path(fixture).name}"
        sources[logical] = path.read_text(encoding="utf-8")
        fixture_names.append(logical)

    stdlib_modules = app.get("stdlib_modules", [])
    if not isinstance(stdlib_modules, list) or any(not isinstance(item, str) for item in stdlib_modules):
        raise ApplicationLabError("stdlib_modules must be a list of module identities")
    try:
        stdlib_sources = standard_library_sources(modules=stdlib_modules)
    except ValueError as error:
        raise ApplicationLabError(f"invalid standard-library selection: {error}") from error
    for relative, content in stdlib_sources.items():
        sources[f"sources/__stdlib__/{relative}"] = content

    for package_name in lock.topological_order:
        if package_name == lock.root:
            continue
        package_root = package_paths[package_name]
        source_root = package_root / "src"
        if not source_root.is_dir():
            raise PackageDependencyError(f"package {package_name!r} has no src directory")
        package_paths_payload: list[bytes] = []
        for path in sorted(source_root.rglob("*.s3")):
            resolved = path.resolve()
            try:
                resolved.relative_to(package_root.resolve())
            except ValueError as error:
                raise PackageDependencyError(f"package source escapes {package_name!r}") from error
            relative = path.relative_to(source_root).as_posix()
            logical = f"sources/{package_name}/{relative}"
            content = path.read_text(encoding="utf-8")
            sources[logical] = content
            package_paths_payload.extend((logical.encode("utf-8"), b"\0", content.encode("utf-8"), b"\0"))
        if not package_paths_payload:
            raise PackageDependencyError(f"package {package_name!r} contains no S3 source files")
        package_hashes[package_name] = _sha256(b"".join(package_paths_payload))

    if not sources:
        raise ApplicationLabError("application has no S3 sources")
    return dict(sorted(sources.items())), sorted(fixture_names), package_hashes


def _fixture_digest(sources: dict[str, str], fixture_names: list[str]) -> str:
    payload = b"".join(
        name.encode("utf-8") + b"\0" + sources[name].encode("utf-8") + b"\0"
        for name in sorted(fixture_names)
    )
    return _sha256(payload)


def _verify_compiler_pin() -> None:
    reference = subprocess.run(
        ["git", "rev-parse", "--verify", f"{PINNED_COMPILER_REVISION}^{{commit}}"],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if reference.returncode != 0:
        raise ApplicationLabError("pinned compiler commit is unavailable in this checkout")
    changed = subprocess.run(
        ["git", "diff", "--quiet", PINNED_COMPILER_REVISION, "--", "bootstrap/s3"],
        cwd=_REPOSITORY_ROOT,
        check=False,
    )
    untracked = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", "bootstrap/s3"],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if changed.returncode != 0 or untracked.stdout.strip():
        raise ApplicationLabError("bootstrap/s3 differs from the pinned compiler revision")


def _source_digest(sources: dict[str, str]) -> str:
    payload = b"".join(
        name.encode("utf-8") + b"\0" + content.encode("utf-8") + b"\0"
        for name, content in sorted(sources.items())
    )
    return _sha256(payload)


def _temporary_test_manifest(
    root: Path,
    sources: dict[str, str],
    *,
    entry_module: str,
    expected: int,
) -> Path:
    for relative, content in sorted(sources.items()):
        target = root / Path(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    escaped_sources = ", ".join(json.dumps(name) for name in sorted(sources))
    manifest = root / "s3-test.toml"
    manifest.write_text(
        "[runner]\nmode = \"hosted\"\noptimization = \"O0\"\n"
        "timeout_ms = 10000\nmax_frames = 1024\nmax_instructions = 100000\n\n"
        "[[test]]\nname = \"application\"\n"
        f"sources = [{escaped_sources}]\n"
        f"entry = {json.dumps(entry_module)}\nexpected = {expected}\ncapabilities = []\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _compile_only(sources: dict[str, str], entry_module: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="s3-application-compile-") as temporary:
        root = Path(temporary)
        for relative, content in sorted(sources.items()):
            target = root / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        (root / "s3.toml").write_text(
            "[project]\nname = \"application-lab-check\"\nversion = \"0.1.0\"\n"
            f"entrypoint = {json.dumps(entry_module)}\nsource_roots = [\"sources\"]\n"
            "profile = \"hosted\"\ndependencies = []\nforeign_libraries = []\n"
            "external_executables = []\nservices = []\n",
            encoding="utf-8",
            newline="\n",
        )
        compilation = ProjectTooling(root).build()
        compilation.require_ordinary_artifacts()
        return {"compiled_sources": len(sources), "status": "PASS"}


def run_application(path: str | Path, *, mode: str = "hosted") -> dict[str, Any]:
    """Validate one application and run it through the existing S3 test runner."""

    raw_path = Path(path)
    if raw_path.is_absolute():
        try:
            relative_path = raw_path.resolve().relative_to(_REPOSITORY_ROOT.resolve()).as_posix()
        except ValueError as error:
            raise ApplicationLabError("application path is outside the repository") from error
    else:
        relative_path = raw_path.as_posix()
    application_path = _safe_repository_path(relative_path, field="application path")
    if application_path != _APPLICATIONS_ROOT and _APPLICATIONS_ROOT not in application_path.parents:
        raise ApplicationLabError("application must be under examples/applications")
    app: dict[str, Any] = {}
    try:
        _verify_compiler_pin()
        app, tooling = _load_application(application_path)
        package_lock, package_paths, _manifests = _package_graph(application_path)
        sources, fixture_names, package_hashes = _application_sources(
            application_path, app, tooling, package_lock, package_paths
        )
        result: dict[str, Any]
        if mode == "ffi":
            return {
                "name": app["name"],
                "status": "UNSUPPORTED_ENVIRONMENT",
                "execution_mode": "FFI_INTEGRATION",
                "reason": "no application in this lab declares a qualified FFI fixture",
                "compiler_revision": PINNED_COMPILER_REVISION,
            }
        if mode == "compile-only":
            compile_report = _compile_only(sources, str(app.get("entry_module", "main")))
            return {
                "name": app["name"],
                "kind": app.get("kind"),
                "status": "PASS",
                "execution_mode": "COMPILE_ONLY",
                "compiler_revision": PINNED_COMPILER_REVISION,
                "source_sha256": _source_digest(sources),
                "fixture_sources": fixture_names,
                "fixture_sha256": _fixture_digest(sources, fixture_names),
                "compile_report": compile_report,
            }
        if mode == "native":
            from bootstrap.s3.backends.x86_64 import NativePlatformError, NativeToolchain

            try:
                NativeToolchain.detect()
            except NativePlatformError as error:
                return {
                    "name": app["name"],
                    "status": "UNSUPPORTED_ENVIRONMENT",
                    "execution_mode": "UNSUPPORTED_ENVIRONMENT",
                    "reason": str(error),
                    "compiler_revision": PINNED_COMPILER_REVISION,
                }
        elif mode != "hosted":
            raise ApplicationLabError(f"unsupported application-lab mode {mode!r}")

        with tempfile.TemporaryDirectory(prefix="s3-application-lab-") as temporary:
            manifest = _temporary_test_manifest(
                Path(temporary),
                sources,
                entry_module=str(app.get("entry_module", "main")),
                expected=app["expected_output"],
            )
            result = run_test_manifest(manifest, mode=mode)
        test = result["tests"][0]
        outcome = test.get("hosted" if mode == "hosted" else "native", {})
        return {
            "name": app["name"],
            "kind": app.get("kind"),
            "status": test["status"],
            "execution_mode": "HOSTED_EXECUTION" if mode == "hosted" else "NATIVE_EXECUTION",
            "compiler_revision": PINNED_COMPILER_REVISION,
            "project": tooling.inspect(),
            "package_lock": package_lock.payload,
            "package_lock_sha256": package_lock.sha256,
            "package_source_sha256": package_hashes,
            "source_sha256": _source_digest(sources),
            "fixture_sources": fixture_names,
            "fixture_sha256": _fixture_digest(sources, fixture_names),
            "expected_output": app["expected_output"],
            "actual_output": outcome.get("value"),
            "exit_status": outcome.get("exit_status", test["exit_status"]),
            "failure_class": test.get("failure_class"),
            "reason": outcome.get("error", outcome.get("reason")),
            "host_environment": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            "test_report": {
                "schema": result["schema"],
                "schema_version": result["schema_version"],
                "mode": result["mode"],
                "summary": result["summary"],
                "test": test,
            },
        }
    except (ApplicationLabError, PackageDependencyError, ProjectContainerError, TestRunnerError) as error:
        return {
            "name": app.get("name", application_path.name),
            "status": "CONFIGURATION_FAILURE",
            "execution_mode": "UNSUPPORTED_ENVIRONMENT" if mode != "hosted" else mode,
            "compiler_revision": PINNED_COMPILER_REVISION,
            "reason": f"{type(error).__name__}: {error}",
        }
