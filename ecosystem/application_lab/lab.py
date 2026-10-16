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
import re
import shutil
import subprocess
import sys
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


def _application_relative_path(value: object, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ApplicationLabError(f"{field} must be a non-empty relative path")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts or ":" in path.parts[0]:
        raise ApplicationLabError(f"{field} must stay inside its application")
    return path


def _validate_ffi_manifest(value: object, app_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != "s3.ffi-app.v1":
        raise ApplicationLabError(f"{app_name} requires an s3.ffi-app.v1 contract")
    _application_relative_path(value.get("source"), field="FFI source")
    symbol = value.get("symbol")
    if not isinstance(symbol, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol) is None:
        raise ApplicationLabError("FFI symbol must be a C identifier")
    library_filename = value.get("library_filename")
    if (
        not isinstance(library_filename, str)
        or "/" in library_filename
        or "\\" in library_filename
        or not library_filename.endswith(".so")
        or library_filename in {".so", "..so"}
    ):
        raise ApplicationLabError("FFI library_filename must be a simple .so filename")
    if value.get("parameters") != ["i64", "i64"] or value.get("result") != "i64":
        raise ApplicationLabError("the first qualified FFI contract must be (i64, i64) -> i64")
    if value.get("calling_convention") != "sysv-amd64":
        raise ApplicationLabError("the qualified FFI calling convention must be sysv-amd64")
    if value.get("supported_os") != "Linux" or value.get("supported_arch") != "x86_64":
        raise ApplicationLabError("the qualified FFI platform must be Linux x86_64")
    timeout_ms = value.get("timeout_ms", 10000)
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= 30000:
        raise ApplicationLabError("FFI timeout_ms must be between 1 and 30000")
    cases = value.get("cases")
    if not isinstance(cases, list) or not 5 <= len(cases) <= 32:
        raise ApplicationLabError("FFI contract requires between 5 and 32 test cases")
    names: set[str] = set()
    lower, upper = -(1 << 63), (1 << 63) - 1
    for case in cases:
        if not isinstance(case, dict):
            raise ApplicationLabError("each FFI case must be a table")
        name = case.get("name")
        arguments = case.get("arguments")
        expected = case.get("expected")
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]+", name) is None or name in names:
            raise ApplicationLabError("FFI case names must be unique identifiers")
        names.add(name)
        if (
            not isinstance(arguments, list)
            or len(arguments) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) or not lower <= item <= upper for item in arguments)
        ):
            raise ApplicationLabError(f"FFI case {name!r} requires two signed i64 arguments")
        if isinstance(expected, bool) or not isinstance(expected, int) or not lower <= expected <= upper:
            raise ApplicationLabError(f"FFI case {name!r} expected result must be signed i64")
    return value


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
    if app["execution_mode"] in {"HOSTED_EXECUTION", "NATIVE_EXECUTION"} and (
        not isinstance(expected, int) or isinstance(expected, bool)
    ):
        raise ApplicationLabError(f"{name} expected_output must be an integer")
    if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool)):
        raise ApplicationLabError(f"{name} expected_output must be an integer")
    fixtures = app.get("fixtures", [])
    if not isinstance(fixtures, list) or any(not isinstance(item, str) for item in fixtures):
        raise ApplicationLabError(f"{name} fixtures must be a list of relative paths")
    if app["execution_mode"] == "FFI_INTEGRATION":
        _validate_ffi_manifest(app.get("ffi"), name)
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


def _write_project_sources(root: Path, sources: dict[str, str], entry_module: str) -> None:
    for relative, content in sorted(sources.items()):
        target = root / Path(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    (root / "s3.toml").write_text(
        "[project]\nname = \"application-lab-native\"\nversion = \"0.1.0\"\n"
        f"entrypoint = {json.dumps(entry_module)}\nsource_roots = [\"sources\"]\n"
        "profile = \"hosted\"\ndependencies = []\nforeign_libraries = []\n"
        "external_executables = []\nservices = []\n",
        encoding="utf-8",
        newline="\n",
    )


def _version_line(executable: str | None) -> str | None:
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            check=False, shell=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (result.stdout or result.stderr).splitlines()
    return lines[0].strip() if result.returncode == 0 and lines else None


def _read_elf_header(binary: Path) -> dict[str, object]:
    readelf = shutil.which("readelf")
    if readelf is None:
        return {"verified": False, "reason": "readelf is unavailable"}
    result = subprocess.run(
        [readelf, "-h", str(binary)], capture_output=True, text=True,
        check=False, shell=False, timeout=5,
    )
    if result.returncode != 0:
        return {"verified": False, "reason": result.stderr.strip() or "readelf failed"}
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    elf_class = fields.get("Class")
    elf_type = fields.get("Type", "").split()[0] if fields.get("Type") else ""
    machine = fields.get("Machine", "")
    verified = elf_class == "ELF64" and elf_type in {"EXEC", "DYN"} and "X86-64" in machine
    return {
        "verified": verified,
        "format": elf_class,
        "type": elf_type,
        "machine": machine,
        "readelf": readelf,
    }


def _native_artifact_report(
    sources: dict[str, str], *, entry_module: str, expected: int,
) -> dict[str, object]:
    from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_native_assembly

    with tempfile.TemporaryDirectory(prefix="s3-native-artifact-") as temporary:
        root = Path(temporary)
        _write_project_sources(root, sources, entry_module)
        compilation = ProjectTooling(root).build()
        _, assembly = compilation.require_ordinary_artifacts()
        assembly_text = generate_native_assembly(assembly)
        toolchain = NativeToolchain.detect()
        executable = toolchain.build(assembly_text, root / "program")
        header = _read_elf_header(executable)
        runs: list[dict[str, object]] = []
        for _ in range(2):
            completed = toolchain.run(executable, timeout=10)
            match = re.fullmatch(r"program returned: (-?\d+)", completed.stdout.strip())
            value = int(match.group(1)) if match else None
            runs.append({
                "process_exit": completed.returncode,
                "actual_result": value,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            })
        deterministic = all(
            run["process_exit"] == 0 and run["actual_result"] == expected
            for run in runs
        ) and len({run["actual_result"] for run in runs}) == 1
        return {
            "status": "PASS" if deterministic and header.get("verified") else "FAIL",
            "artifact_path": "temporary/program (removed after hashing)",
            "artifact_sha256": _sha256(executable.read_bytes()),
            "elf": header,
            "entry_module": entry_module,
            "runs": runs,
            "deterministic_result": deterministic,
            "toolchain": {
                "compiler": toolchain.compiler,
                "compiler_version": _version_line(toolchain.compiler),
                "assembler": toolchain.assembler,
                "assembler_version": _version_line(toolchain.assembler),
                "linker": toolchain.linker,
                "linker_version": _version_line(toolchain.linker),
            },
        }


def _ffi_host_supported(system: str, machine: str) -> bool:
    return system == "Linux" and machine.lower() in {"x86_64", "amd64"}


def _ffi_source_signature_error(source: str, contract: dict[str, Any]) -> tuple[str, str] | None:
    from bootstrap.s3.pipeline import compile_source

    try:
        compilation = compile_source(source)
    except Exception as error:
        return "FFI_BUILD_FAILURE", f"S3 FFI source did not compile: {type(error).__name__}: {error}"
    exported = [
        function for function in compilation.ir.functions
        if function.name == contract["symbol"] and function.exported and not function.external
    ]
    if len(exported) != 1:
        return "FFI_ABI_FAILURE", "the manifest symbol must identify exactly one exported S3 function"
    function = exported[0]
    parameter_types = [parameter.type.value for parameter in function.parameters]
    result_type = function.return_type.value
    if parameter_types != contract["parameters"] or result_type != contract["result"]:
        return (
            "FFI_ABI_FAILURE",
            f"manifest signature {contract['parameters']} -> {contract['result']} does not match "
            f"S3 export {parameter_types} -> {result_type}",
        )
    return None


def _run_ffi_application(
    application_path: Path,
    app: dict[str, Any],
    sources: dict[str, str],
    package_lock: PackageLock,
    package_hashes: dict[str, str],
) -> dict[str, Any]:
    contract_data = _validate_ffi_manifest(app.get("ffi"), str(app["name"]))
    system, machine = platform.system(), platform.machine()
    base_report: dict[str, Any] = {
        "name": app["name"],
        "kind": app.get("kind"),
        "execution_mode": "FFI_INTEGRATION",
        "compiler_revision": PINNED_COMPILER_REVISION,
        "host_environment": {
            "system": system,
            "machine": machine,
            "kernel": platform.release(),
            "python": platform.python_version(),
        },
        "source_sha256": _source_digest(sources),
        "package_lock": package_lock.payload,
        "package_lock_sha256": package_lock.sha256,
        "package_source_sha256": package_hashes,
    }
    if not _ffi_host_supported(system, machine):
        return {
            **base_report,
            "status": "FFI_UNSUPPORTED_ENVIRONMENT",
            "reason": f"requires Linux x86_64; detected {system} {machine}",
        }

    from bootstrap.s3.ffi import FFIContract, FFIError, FFISignature, FFIType, validate_contract

    try:
        signature = FFISignature(
            symbol=contract_data["symbol"],
            parameters=tuple(FFIType(item) for item in contract_data["parameters"]),
            result=FFIType(contract_data["result"]),
        )
        abi = validate_contract(
            signature,
            FFIContract(calling_convention=contract_data["calling_convention"]),
        )
    except (FFIError, ValueError, TypeError) as error:
        return {
            **base_report,
            "status": "FFI_ABI_FAILURE",
            "reason": f"{type(error).__name__}: {error}",
        }

    source_relative = _application_relative_path(contract_data["source"], field="FFI source")
    source_path = (application_path / Path(*source_relative.parts)).resolve()
    try:
        source_path.relative_to(application_path.resolve())
    except ValueError:
        return {**base_report, "status": "CONFIGURATION_FAILURE", "reason": "FFI source escapes application root"}
    if not source_path.is_file() or source_path.suffix != ".s3":
        return {**base_report, "status": "CONFIGURATION_FAILURE", "reason": "FFI source is missing or not an S3 file"}
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return {**base_report, "status": "CONFIGURATION_FAILURE", "reason": f"cannot read FFI source: {error}"}
    signature_error = _ffi_source_signature_error(source_text, contract_data)
    if signature_error is not None:
        status, reason = signature_error
        return {**base_report, "status": status, "reason": reason}

    def build_and_call(root: Path) -> dict[str, Any]:
        from bootstrap.s3.ffi import build_shared_library

        library_path = root / contract_data["library_filename"]
        if library_path.exists():
            return {"status": "CONFIGURATION_FAILURE", "reason": "refusing to overwrite existing FFI artifact"}
        try:
            build_shared_library(source_text, library_path)
        except Exception as error:
            return {"status": "FFI_BUILD_FAILURE", "reason": f"{type(error).__name__}: {error}"}

        from shutil import which
        readelf = which("readelf")
        nm = which("nm")
        if readelf is None or nm is None:
            return {"status": "FFI_ABI_FAILURE", "reason": "readelf and nm are required to verify ELF and symbol"}
        elf_result = subprocess.run(
            [readelf, "-h", str(library_path)], capture_output=True, text=True,
            check=False, shell=False, timeout=5,
        )
        nm_result = subprocess.run(
            [nm, "-D", "--defined-only", str(library_path)], capture_output=True, text=True,
            check=False, shell=False, timeout=5,
        )
        elf_header = _read_elf_header(library_path)
        exported_symbols = [line.split()[-1] for line in nm_result.stdout.splitlines() if line.split()]
        symbol_exported = nm_result.returncode == 0 and contract_data["symbol"] in exported_symbols
        shared_object_verified = elf_header.get("verified") and elf_header.get("type") == "DYN"
        if elf_result.returncode != 0 or not shared_object_verified or not symbol_exported:
            return {
                "status": "FFI_ABI_FAILURE",
                "reason": "shared artifact is not verified ELF64 x86-64 or symbol is absent",
                "elf": elf_header,
                "symbol_exported": symbol_exported,
            }

        missing_library = root / "missing-library.so"
        if missing_library.exists():
            return {"status": "CONFIGURATION_FAILURE", "reason": "negative-test library path unexpectedly exists"}
        invocation = subprocess.run(
            [
                sys.executable, "-m", "ecosystem.application_lab.ffi_client",
                str(library_path), contract_data["symbol"],
                json.dumps(contract_data["cases"], separators=(",", ":")),
                "s3_symbol_that_does_not_exist", str(missing_library),
            ],
            cwd=_REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=contract_data["timeout_ms"] / 1000,
        )
        if invocation.returncode != 0:
            try:
                details = json.loads(invocation.stdout)
            except json.JSONDecodeError:
                details = {"error": invocation.stderr.strip() or invocation.stdout.strip()}
            return {"status": "FFI_LOAD_FAILURE", "reason": details.get("error", "external ctypes caller failed")}
        try:
            call_report = json.loads(invocation.stdout)
        except json.JSONDecodeError as error:
            return {"status": "FFI_LOAD_FAILURE", "reason": f"external caller returned invalid JSON: {error}"}
        expected_cases = contract_data["cases"]
        actual_cases = call_report.get("results", [])
        case_results = []
        for index, expected_case in enumerate(expected_cases):
            actual = actual_cases[index].get("actual") if index < len(actual_cases) else None
            case_results.append({
                "name": expected_case["name"],
                "arguments": expected_case["arguments"],
                "expected": expected_case["expected"],
                "actual": actual,
                "status": "PASS" if actual == expected_case["expected"] else "FFI_OUTPUT_MISMATCH",
            })
        negative_cases = {
            "invalid_signature_description": _negative_signature_rejected(),
            "missing_symbol": bool(call_report.get("missing_symbol_rejected")),
            "invalid_library_path": bool(call_report.get("missing_library_rejected")),
            "unsupported_abi": _negative_abi_rejected(),
            "incompatible_platform": not _ffi_host_supported("Windows", "AMD64"),
        }
        passed = (
            len(actual_cases) == len(expected_cases)
            and all(item["status"] == "PASS" for item in case_results)
            and all(negative_cases.values())
        )
        return {
            "status": "FFI_PASS" if passed else "FFI_OUTPUT_MISMATCH",
            "library_path": str(library_path),
            "library_sha256": _sha256(library_path.read_bytes()),
            "elf": elf_header,
            "exported_symbol": contract_data["symbol"],
            "symbol_exported": symbol_exported,
            "abi_contract": abi.payload,
            "cases": case_results,
            "negative_cases": negative_cases,
            "external_caller": "python ctypes subprocess",
            "external_caller_exit_status": invocation.returncode,
            "timeout_seconds": contract_data["timeout_ms"] / 1000,
            "artifact_lifetime": "temporary; removed after hash and call verification",
        }

    try:
        with tempfile.TemporaryDirectory(prefix="s3-ffi-qualification-") as temporary:
            return {**base_report, **build_and_call(Path(temporary))}
    except subprocess.TimeoutExpired:
        return {**base_report, "status": "TIMEOUT", "reason": "external FFI caller exceeded timeout"}
    except (OSError, subprocess.SubprocessError) as error:
        return {**base_report, "status": "INFRASTRUCTURE_FAILURE", "reason": f"{type(error).__name__}: {error}"}


def _negative_signature_rejected() -> bool:
    from bootstrap.s3.ffi import FFIError, FFISignature, FFIType

    try:
        FFISignature("invalid-symbol-name", (FFIType.I64, FFIType.I64), FFIType.I64)
    except FFIError:
        return True
    return False


def _negative_abi_rejected() -> bool:
    from bootstrap.s3.ffi import FFIContract, FFIError

    try:
        FFIContract(calling_convention="unsupported-abi")
    except FFIError:
        return True
    return False


def run_application(path: str | Path, *, mode: str = "hosted") -> dict[str, Any]:
    """Validate an application through the S3 test runner or qualified FFI harness."""

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
        if mode not in {"hosted", "compile-only", "native", "ffi"}:
            raise ApplicationLabError(f"unsupported application-lab mode {mode!r}")
        app_mode = app["execution_mode"]
        if app_mode == "FFI_INTEGRATION" and mode != "ffi":
            return {
                "name": app["name"],
                "status": "NOT_APPLICABLE",
                "execution_mode": app_mode,
                "reason": f"this fixture is qualified through mode={mode!r} only",
                "compiler_revision": PINNED_COMPILER_REVISION,
            }
        package_lock, package_paths, _manifests = _package_graph(application_path)
        sources, fixture_names, package_hashes = _application_sources(
            application_path, app, tooling, package_lock, package_paths
        )
        if mode == "ffi":
            if app_mode != "FFI_INTEGRATION":
                return {
                    "name": app["name"],
                    "status": "FFI_NOT_APPLICABLE",
                    "execution_mode": "FFI_INTEGRATION",
                    "compiler_revision": PINNED_COMPILER_REVISION,
                }
            return {
                **_run_ffi_application(
                    application_path, app, sources, package_lock, package_hashes
                ),
                "fixture_sources": fixture_names,
                "fixture_sha256": _fixture_digest(sources, fixture_names),
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
                "package_lock_sha256": package_lock.sha256,
                "package_source_sha256": package_hashes,
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
                    "execution_mode": "NATIVE_EXECUTION",
                    "reason": str(error),
                    "compiler_revision": PINNED_COMPILER_REVISION,
                }

        with tempfile.TemporaryDirectory(prefix="s3-application-lab-") as temporary:
            manifest = _temporary_test_manifest(
                Path(temporary),
                sources,
                entry_module=str(app.get("entry_module", "main")),
                expected=app["expected_output"],
            )
            result = run_test_manifest(manifest, mode=mode)
        test = result["tests"][0]
        outcome = test.get(mode if mode in {"hosted", "native"} else "hosted", {})
        native_artifact = None
        if mode == "native" and test["status"] == "PASS":
            native_artifact = _native_artifact_report(
                sources,
                entry_module=str(app.get("entry_module", "main")),
                expected=app["expected_output"],
            )
        return {
            "name": app["name"],
            "kind": app.get("kind"),
            "status": test["status"] if native_artifact is None or native_artifact["status"] == "PASS" else "FAIL",
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
            "native_artifact": native_artifact,
            "host_environment": {
                "system": platform.system(),
                "machine": platform.machine(),
                "kernel": platform.release(),
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
            "execution_mode": mode,
            "compiler_revision": PINNED_COMPILER_REVISION,
            "reason": f"{type(error).__name__}: {error}",
        }
    except subprocess.TimeoutExpired as error:
        return {
            "name": app.get("name", application_path.name),
            "status": "TIMEOUT",
            "execution_mode": mode,
            "compiler_revision": PINNED_COMPILER_REVISION,
            "reason": f"{type(error).__name__}: {error}",
        }
    except Exception as error:
        return {
            "name": app.get("name", application_path.name),
            "status": "INFRASTRUCTURE_FAILURE",
            "execution_mode": mode,
            "compiler_revision": PINNED_COMPILER_REVISION,
            "reason": f"{type(error).__name__}: {error}",
        }
