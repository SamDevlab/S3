"""Create a deterministic, unpublished release archive from a qualified candidate."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from bootstrap.s3.native_compiler import inspect_s3c_ng_executable


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
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("bootstrap_parent", {}).get("kind") != "python-reference-stage0":
        parser.error("candidate manifest does not identify the qualified V7 bootstrap parent")
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
