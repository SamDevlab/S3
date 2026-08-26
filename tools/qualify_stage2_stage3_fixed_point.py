"""Strict Stage1->Stage2->Stage3 fixed-point certification harness.

This tool is deliberately dormant until a machine-readable Stage1 certification
exists. Python is the external orchestrator only: Stage1/Stage2 compiler
processes run with a sanitized environment and are traced with strace. Any
compiler descendant execve blocks certification. Stage2 and Stage3 are built
with the same host object and deterministic linker recipe, then compared as
exact ELF bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
DEFAULT_HOST_IO = ROOT / "selfhost" / "compiler" / "stage1_host_io.c"
DEFAULT_STAGE1_CERT = ROOT / "reports" / "selfhost" / "stage1" / "stage1-certification-gate.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage2" / "stage2-stage3-fixed-point.json"

_STAGE1_CERT_SCHEMA = "s3.selfhost.stage1-certification-gate.v1"


class FixedPointError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(command: list[str], *, cwd: Path, input_bytes: bytes | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        env=env,
    )


def _require_ok(completed: subprocess.CompletedProcess[bytes], label: str) -> None:
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace") or completed.stdout.decode("utf-8", errors="replace")
        raise FixedPointError(f"{label} failed with status {completed.returncode}: {detail.strip()}")


def _canonical_source(manifest_path: Path) -> tuple[Path, bytes, dict[str, object]]:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "s3.compiler.sources.v1":
        raise FixedPointError("canonical compiler source manifest schema mismatch")
    sources = document.get("sources")
    if not isinstance(sources, list) or len(sources) != 1 or document.get("source_count") != 1:
        raise FixedPointError("strict harness currently requires exactly one canonical compiler source; add a real multi-source Stage driver before widening this contract")
    entry = sources[0]
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
        raise FixedPointError("canonical source manifest entry is malformed")
    source_path = (ROOT / entry["path"]).resolve()
    try:
        source_path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise FixedPointError("canonical source path escapes repository root") from error
    data = source_path.read_bytes()
    digest = _sha256(data)
    if digest != entry["sha256"]:
        raise FixedPointError(f"canonical source SHA mismatch: manifest={entry['sha256']} actual={digest}")
    if document.get("total_bytes") != len(data):
        raise FixedPointError("canonical source byte count differs from manifest")
    return source_path, data, document


def validate_stage1_certification(document: dict[str, object], canonical_sha: str) -> None:
    if document.get("schema") != _STAGE1_CERT_SCHEMA:
        raise FixedPointError(f"Stage1 certification must use schema {_STAGE1_CERT_SCHEMA}")
    canonical = document.get("canonical_source")
    qualification = document.get("qualification")
    if not isinstance(canonical, dict) or not isinstance(qualification, dict):
        raise FixedPointError("Stage1 certification lacks canonical_source/qualification sections")
    if canonical.get("sha256") != canonical_sha:
        raise FixedPointError("Stage1 certification canonical SHA does not match current manifest")
    required = {
        "stage1_certified_for_stage2": True,
        "self_emit": "PASS",
        "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
        "verifier_v2": "PASS",
        "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
    }
    for field, expected in required.items():
        if qualification.get(field) != expected:
            raise FixedPointError(f"Stage1 certification prerequisite {field} is not {expected!r}")


def _sanitized_compiler_env(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": "/nonexistent",
        "PYTHONPATH": "",
        "PYTHONHOME": "",
        "PYTHONSAFEPATH": "1",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "SOURCE_DATE_EPOCH": "0",
        "HOME": str(home),
        "TMPDIR": str(home),
    }


def _execve_lines(trace_path: Path) -> list[str]:
    if not trace_path.exists():
        return []
    return [line for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if "execve(" in line]


def _trace_compiler(compiler: Path, source: bytes, *, cwd: Path, trace_path: Path, strace: str) -> dict[str, object]:
    env = _sanitized_compiler_env(cwd / "sandbox-home")
    completed = _run(
        [strace, "-f", "-qq", "-e", "trace=execve", "-o", str(trace_path), str(compiler.resolve())],
        cwd=cwd,
        input_bytes=source,
        env=env,
    )
    execves = _execve_lines(trace_path)
    strict_single_exec = len(execves) == 1
    python_exec = any(re.search(r"python(?:3(?:\.\d+)?)?", line, flags=re.IGNORECASE) for line in execves)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "trace_path": str(trace_path),
        "execve_lines": execves,
        "execve_count": len(execves),
        "strict_single_exec": strict_single_exec,
        "python_exec_seen": python_exec,
        "sanitized_environment": env,
    }


def _compile_host_object(cc: str, host_io: Path, workspace: Path) -> Path:
    output = workspace / "host.o"
    completed = _run(
        [
            cc, "-std=c11", "-ffreestanding", "-fno-builtin", "-fno-pie",
            "-fno-stack-protector", "-fno-asynchronous-unwind-tables",
            "-c", str(host_io.resolve()), "-o", str(output),
        ],
        cwd=workspace,
    )
    _require_ok(completed, "host object build")
    return output


def _assemble_link(assembly: bytes, *, cc: str, host_object: Path, directory: Path, output_name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    assembly_path = directory / "compiler.s"
    object_path = directory / "compiler.o"
    output = directory / output_name
    assembly_path.write_bytes(assembly)
    assembled = _run([cc, "-x", "assembler", "-c", str(assembly_path), "-o", str(object_path)], cwd=directory)
    _require_ok(assembled, f"assemble {output_name}")
    linked = _run(
        [cc, "-nostdlib", "-no-pie", "-s", "-Wl,--build-id=none", str(object_path), str(host_object), "-o", str(output)],
        cwd=directory,
    )
    _require_ok(linked, f"link {output_name}")
    return output


def _compile_stage(compiler: Path, source: bytes, *, cc: str, host_object: Path, directory: Path, output_name: str, strace: str) -> tuple[Path, dict[str, object]]:
    directory.mkdir(parents=True, exist_ok=True)
    trace = _trace_compiler(compiler, source, cwd=directory, trace_path=directory / "compiler.execve.trace", strace=strace)
    if trace["returncode"] != 0 or trace["stderr"] != b"" or not trace["strict_single_exec"] or trace["python_exec_seen"]:
        raise FixedPointError(
            f"{output_name} compiler invocation failed strict Pythonless gate: "
            f"returncode={trace['returncode']} stderr_bytes={len(trace['stderr'])} "
            f"execves={trace['execve_count']} python_exec={trace['python_exec_seen']}"
        )
    assembly = trace["stdout"]
    if not assembly:
        raise FixedPointError(f"{output_name} compiler emitted empty assembly")
    artifact = _assemble_link(assembly, cc=cc, host_object=host_object, directory=directory, output_name=output_name)
    trace["assembly_sha256"] = _sha256(assembly)
    trace["assembly_bytes"] = len(assembly)
    trace["artifact_sha256"] = _sha256(artifact.read_bytes())
    trace["artifact_bytes"] = artifact.stat().st_size
    trace.pop("stdout")
    trace.pop("stderr")
    return artifact, trace


def _run_program(path: Path) -> subprocess.CompletedProcess[bytes]:
    return _run([str(path.resolve())], cwd=path.parent, env={"PATH": "/nonexistent", "LANG": "C", "LC_ALL": "C"})


def _stage2_conformance(stage2: Path, *, cc: str, host_object: Path, workspace: Path, strace: str) -> dict[str, object]:
    fixtures = [
        ("literal_return", "fn main() -> tryte:\n    return 7\n", 7),
        ("scalar_local", "fn main() -> tryte:\n    mut x: i64 = 3\n    x = x + 4\n    return to_tryte(x)\n", 7),
        ("internal_call", "fn add(a: i64, b: i64) -> i64:\n    return a + b\n\nfn main() -> tryte:\n    return to_tryte(add(3, 4))\n", 7),
        ("while_branch", "fn main() -> tryte:\n    mut x: i64 = 0\n    while x < 3:\n        x += 1\n    return to_tryte(x)\n", 3),
        ("fixed_array", "fn main() -> tryte:\n    mut values: i64[2] = [2, 5]\n    values[0] = values[0] + values[1]\n    return to_tryte(values[0])\n", 7),
    ]
    results: list[dict[str, object]] = []
    all_pass = True
    for name, source, expected in fixtures:
        directory = workspace / "conformance" / name
        directory.mkdir(parents=True, exist_ok=True)
        trace = _trace_compiler(stage2, source.encode("utf-8"), cwd=directory, trace_path=directory / "compiler.execve.trace", strace=strace)
        compile_pass = trace["returncode"] == 0 and trace["stderr"] == b"" and trace["strict_single_exec"] and not trace["python_exec_seen"] and bool(trace["stdout"])
        run_exit: int | None = None
        run_stdout = b""
        run_stderr = b""
        if compile_pass:
            program = _assemble_link(trace["stdout"], cc=cc, host_object=host_object, directory=directory, output_name="program")
            executed = _run_program(program)
            run_exit = executed.returncode
            run_stdout = executed.stdout
            run_stderr = executed.stderr
        passed = compile_pass and run_exit == expected and run_stdout == b"" and run_stderr == b""
        all_pass = all_pass and passed
        results.append({
            "name": name,
            "compile_pass": compile_pass,
            "compiler_execve_count": trace["execve_count"],
            "python_exec_seen": trace["python_exec_seen"],
            "expected_exit": expected,
            "actual_exit": run_exit,
            "runtime_stdout_bytes": len(run_stdout),
            "runtime_stderr_bytes": len(run_stderr),
            "pass": passed,
        })

    invalid = b"fn main() -> tryte:\n    return\n"
    invalid_dir = workspace / "conformance" / "invalid_source"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    first = _trace_compiler(stage2, invalid, cwd=invalid_dir, trace_path=invalid_dir / "first.execve.trace", strace=strace)
    second = _trace_compiler(stage2, invalid, cwd=invalid_dir, trace_path=invalid_dir / "second.execve.trace", strace=strace)
    invalid_pass = (
        first["returncode"] != 0
        and second["returncode"] == first["returncode"]
        and first["stdout"] == second["stdout"]
        and first["stderr"] == second["stderr"]
        and first["strict_single_exec"] and second["strict_single_exec"]
        and not first["python_exec_seen"] and not second["python_exec_seen"]
    )
    all_pass = all_pass and invalid_pass
    results.append({
        "name": "invalid_source",
        "deterministic_failure": invalid_pass,
        "returncode": first["returncode"],
        "stdout_sha256": _sha256(first["stdout"]),
        "stderr_sha256": _sha256(first["stderr"]),
        "pass": invalid_pass,
    })
    return {"status": "PASS" if all_pass else "FAIL", "fixtures": results}


def qualify(*, stage1: Path, stage1_certification: Path, manifest: Path, host_io: Path, report: Path, workspace: Path, stage4: bool = False) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise FixedPointError("strict Stage2/Stage3 certification requires Linux x86-64")
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    strace = shutil.which("strace")
    if cc is None:
        raise FixedPointError("host assembler/linker driver cc/gcc/clang is unavailable")
    if strace is None:
        raise FixedPointError("strace is required for strict Pythonless compiler-process certification")
    stage1 = stage1.resolve()
    if not stage1.is_file() or not os.access(stage1, os.X_OK):
        raise FixedPointError("Stage1 executable is missing or not executable")

    source_path, source, source_manifest = _canonical_source(manifest.resolve())
    canonical_sha = _sha256(source)
    certification = json.loads(stage1_certification.resolve().read_text(encoding="utf-8"))
    if not isinstance(certification, dict):
        raise FixedPointError("Stage1 certification document must be a JSON object")
    validate_stage1_certification(certification, canonical_sha)

    workspace = workspace.resolve()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    host_object = _compile_host_object(cc, host_io.resolve(), workspace)
    host_sha = _sha256(host_object.read_bytes())

    stage2, stage2_build = _compile_stage(stage1, source, cc=cc, host_object=host_object, directory=workspace / "stage2", output_name="s3c-stage2", strace=strace)
    stage2_bytes = stage2.read_bytes()
    stage2_conformance = _stage2_conformance(stage2, cc=cc, host_object=host_object, workspace=workspace, strace=strace)
    if stage2_conformance["status"] != "PASS":
        raise FixedPointError("Stage2 representative conformance failed")

    stage3, stage3_build = _compile_stage(stage2, source, cc=cc, host_object=host_object, directory=workspace / "stage3", output_name="s3c-stage3", strace=strace)
    stage3_bytes = stage3.read_bytes()
    elf_equal = stage2_bytes == stage3_bytes
    sha_equal = _sha256(stage2_bytes) == _sha256(stage3_bytes)
    assembly_equal = stage2_build["assembly_sha256"] == stage3_build["assembly_sha256"] and stage2_build["assembly_bytes"] == stage3_build["assembly_bytes"]

    stage4_result: dict[str, object] = {"status": "NOT_RUN"}
    if stage4:
        stage4_artifact, stage4_build = _compile_stage(stage3, source, cc=cc, host_object=host_object, directory=workspace / "stage4", output_name="s3c-stage4", strace=strace)
        stage4_bytes = stage4_artifact.read_bytes()
        stage4_result = {
            "status": "PASS" if stage4_bytes == stage3_bytes else "FAIL",
            "sha256": _sha256(stage4_bytes),
            "bytes": len(stage4_bytes),
            "stage3_stage4_bytes_equal": stage4_bytes == stage3_bytes,
            "build": stage4_build,
        }

    full_self_hosting = bool(elf_equal and sha_equal and stage2_conformance["status"] == "PASS" and stage2_build["strict_single_exec"] and stage3_build["strict_single_exec"] and not stage2_build["python_exec_seen"] and not stage3_build["python_exec_seen"] and (not stage4 or stage4_result["status"] == "PASS"))
    result = {
        "schema": "s3.selfhost.stage2-stage3-fixed-point.v1",
        "platform": {"system": platform.system(), "machine": platform.machine(), "cc": cc, "strace": strace},
        "canonical_source": {"path": str(source_path), "sha256": canonical_sha, "bytes": len(source), "manifest": source_manifest},
        "stage1": {"path": str(stage1), "sha256": _sha256(stage1.read_bytes()), "certification_path": str(stage1_certification.resolve())},
        "host_object": {"path": str(host_object), "sha256": host_sha, "reused_for_stage2_stage3": True},
        "stage2": {"path": str(stage2), "sha256": _sha256(stage2_bytes), "bytes": len(stage2_bytes), "build": stage2_build, "conformance": stage2_conformance},
        "stage3": {"path": str(stage3), "sha256": _sha256(stage3_bytes), "bytes": len(stage3_bytes), "build": stage3_build},
        "fixed_point": {
            "stage2_stage3_assembly_equal_diagnostic": assembly_equal,
            "stage2_stage3_sha256_equal": sha_equal,
            "stage2_stage3_bytes_equal": elf_equal,
        },
        "stage4": stage4_result,
        "qualification": {
            "stage1_to_stage2": "PASS",
            "stage2_pythonless_compiler": "PASS_STRICT_EXECVE_TRACE",
            "stage2_conformance": stage2_conformance["status"],
            "stage2_to_stage3": "PASS",
            "stage2_stage3_exact_elf_fixed_point": elf_equal and sha_equal,
            "full_self_hosting": full_self_hosting,
            "next": "FULL_SELF_HOSTING_CERTIFICATION_READY" if full_self_hosting else "REPAIR_STAGE2_STAGE3_DETERMINISM",
        },
    }
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage1-certification", type=Path, default=DEFAULT_STAGE1_CERT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--workspace", type=Path, default=Path(tempfile.gettempdir()) / "s3-stage2-stage3-fixed-point")
    parser.add_argument("--stage4", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = qualify(stage1=args.stage1, stage1_certification=args.stage1_certification, manifest=args.manifest, host_io=args.host_io, report=args.report, workspace=args.workspace, stage4=args.stage4)
    except FixedPointError as error:
        parser.exit(2, f"fixed-point certification blocked: {error}\n")
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"STAGE2_SHA256={result['stage2']['sha256']}")
    print(f"STAGE3_SHA256={result['stage3']['sha256']}")
    print(f"STAGE2_STAGE3_BYTES_EQUAL={result['fixed_point']['stage2_stage3_bytes_equal']}")
    print(f"STAGE2_PYTHONLESS_COMPILER={qualification['stage2_pythonless_compiler']}")
    print(f"STAGE2_CONFORMANCE={qualification['stage2_conformance']}")
    print(f"FULL_SELF_HOSTING={qualification['full_self_hosting']}")
    print(f"NEXT={qualification['next']}")
    return 0 if qualification["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
