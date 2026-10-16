"""Build a dependency-free local VSIX archive; this never publishes or installs it."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_EXTENSION_ROOT = _REPOSITORY_ROOT / "ecosystem" / "editors" / "vscode-s3"
_FILES = (
    "README.md",
    "client.js",
    "extension.js",
    "language-configuration.json",
    "package.json",
    "positions.js",
    "syntaxes/s3.tmLanguage.json",
)


def package_vsix(output: str | Path | None = None) -> Path:
    target = Path(output) if output is not None else _EXTENSION_ROOT / "dist" / "s3-language-0.1.0.vsix"
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(_EXTENSION_ROOT / "[Content_Types].xml", "[Content_Types].xml")
        archive.write(_EXTENSION_ROOT / "extension.vsixmanifest", "extension.vsixmanifest")
        for relative in _FILES:
            archive.write(_EXTENSION_ROOT / relative, f"extension/{relative}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(prog="s3-vsix-packager")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(package_vsix(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
