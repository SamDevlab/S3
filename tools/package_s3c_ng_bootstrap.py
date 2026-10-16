"""Create a deterministic, unpublished release archive from a qualified candidate."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

from bootstrap.s3.native_compiler import inspect_s3c_ng_executable
from tools.native_s3c_ng import compiler_source_graph_sha256, compiler_source_set


_COMPILER_INPUTS = (
    "bootstrap/s3",
    "selfhost/compiler_ng",
    "tools/native_s3c_ng.py",
    "tools/native_selfhost_driver.c",
)


def _git(repository: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"git {' '.join(arguments)} failed: {error}") from error
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _validate_source_provenance(repository: Path, manifest: dict[str, object]) -> None:
    source_commit = manifest.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or _git(repository, "rev-parse", "HEAD") != source_commit
    ):
        raise ValueError("candidate source commit does not match the packaging checkout HEAD")
    if _git(repository, "status", "--porcelain", "--", *_COMPILER_INPUTS):
        raise ValueError("compiler source inputs must be clean before bootstrap packaging")
    sources = compiler_source_set(repository)
    if manifest.get("source_graph_sha256") != compiler_source_graph_sha256(sources):
        raise ValueError("candidate source graph does not match the packaging checkout")

    toolchain = manifest.get("toolchain")
    if not isinstance(toolchain, dict) or any(
        not isinstance(toolchain.get(key), str) or not toolchain[key].strip()
        for key in ("compiler", "version", "assembler", "linker")
    ):
        raise ValueError("candidate manifest is missing complete toolchain provenance")


def _archive(executable: bytes, manifest: bytes) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, contents, mode in (
                ("s3c-ng", executable, 0o755),
                ("s3c-ng.manifest.json", manifest, 0o644),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(contents)
                info.mode = mode
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(contents))
    return raw.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    availability = inspect_s3c_ng_executable(args.executable)
    if not availability.available:
        parser.error(availability.reason or "candidate is not a valid Linux x86-64 S3C-NG artifact")
    manifest_path = args.executable.with_suffix(".manifest.json")
    executable = args.executable.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        parser.error(f"candidate manifest is invalid: {error}")
    if not isinstance(manifest, dict):
        parser.error("candidate manifest must be a JSON object")
    bootstrap_parent = manifest.get("bootstrap_parent")
    if (
        not isinstance(bootstrap_parent, dict)
        or bootstrap_parent.get("kind") != "python-reference-stage0"
    ):
        parser.error("candidate manifest does not identify the qualified V7 bootstrap parent")
    try:
        _validate_source_provenance(Path(__file__).resolve().parents[1], manifest)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    archive = _archive(executable, manifest_bytes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(archive)
    print(
        json.dumps(
            {
                "asset": str(args.output),
                "asset_bytes": len(archive),
                "asset_sha256": hashlib.sha256(archive).hexdigest(),
                "artifact_sha256": hashlib.sha256(executable).hexdigest(),
                "artifact_bytes": len(executable),
                "source_commit": manifest["source_commit"],
                "source_graph_sha256": manifest["source_graph_sha256"],
                "target": manifest["target"],
                "toolchain": manifest["toolchain"],
                "publication_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
