"""Build a local Linux S3C-NG candidate from the Python reference seed."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from bootstrap.s3.native_compiler import NativeS3CTransportError
from tools.native_s3c_ng import (
    build_native_s3c,
    compile_reference_b_ir,
    compiler_source_graph_sha256,
    compiler_source_set,
    write_s3c_ng_candidate_manifest,
)


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        raise NativeS3CTransportError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _require_clean_compiler_inputs(repository: Path) -> None:
    paths = (
        "bootstrap/s3",
        "selfhost/compiler_ng",
        "tools/native_s3c_ng.py",
        "tools/native_selfhost_driver.c",
    )
    status = _git(repository, "status", "--porcelain", "--", *paths)
    if status:
        raise NativeS3CTransportError(
            "compiler inputs must be committed before candidate creation: "
            + status
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="candidate output directory (default: repository build/)",
    )
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    output_directory = (
        args.output_directory.resolve()
        if args.output_directory is not None
        else repository / "build"
    )
    _require_clean_compiler_inputs(repository)
    source_commit = _git(repository, "rev-parse", "HEAD")
    sources = compiler_source_set(repository)
    source_graph_sha256 = compiler_source_graph_sha256(sources)

    parent_ir = compile_reference_b_ir(repository)
    artifact = build_native_s3c(parent_ir, output_directory, label="s3c-ng")
    version_result = subprocess.run(
        [artifact.toolchain.compiler, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if version_result.returncode != 0:
        raise NativeS3CTransportError("could not identify native C toolchain version")
    toolchain_version = (version_result.stdout or version_result.stderr).splitlines()[0]

    manifest_path = artifact.executable.with_suffix(".manifest.json")
    write_s3c_ng_candidate_manifest(
        artifact,
        manifest_path,
        source_commit=source_commit,
        source_graph_sha256=source_graph_sha256,
        toolchain_version=toolchain_version,
        bootstrap_parent_ir_sha256=artifact.compiler_ir_sha256,
    )
    print(
        json.dumps(
            {
                "artifact": str(artifact.executable),
                "artifact_sha256": artifact.executable_sha256,
                "artifact_bytes": artifact.executable_bytes,
                "manifest": str(manifest_path),
                "source_commit": source_commit,
                "source_graph_sha256": source_graph_sha256,
                "bootstrap_parent": "python-reference-stage0",
                "candidate_default": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
