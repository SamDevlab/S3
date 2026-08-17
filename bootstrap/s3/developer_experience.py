"""Deterministic source and project ergonomics for M1.59."""

from __future__ import annotations

from pathlib import Path

from .diagnostics import S3Error
from .project_container import ProjectContainerError, ProjectTooling


class DeveloperExperienceError(ValueError):
    """Raised when a developer-experience operation cannot be completed."""


def format_source(source: str) -> str:
    """Apply the deliberately small, semantics-preserving S3 source policy."""

    if not isinstance(source, str):
        raise DeveloperExperienceError("source must be text")
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip(" \t") for line in lines).rstrip("\n") + "\n"


def format_diagnostic(error: S3Error, *, file: str | None = None) -> str:
    location = getattr(error, "location", None)
    line = location.line if location is not None else 1
    column = location.column if location is not None else 1
    code = getattr(getattr(error, "diagnostic_code", None), "value", "S3E_INTERNAL")
    phase = getattr(getattr(error, "diagnostic_phase", None), "value", "internal")
    prefix = f"{file}:" if file else ""
    return f"{prefix}{line}:{column}: {phase}: [{code}] {error}"


def init_project(root: str | Path, name: str, *, overwrite: bool = False) -> Path:
    """Create a minimal valid hosted S3 project and return its manifest path."""

    path = Path(root)
    manifest = path / "s3.toml"
    if manifest.exists() and not overwrite:
        raise DeveloperExperienceError(f"project manifest already exists: {manifest}")
    path.mkdir(parents=True, exist_ok=True)
    (path / "src").mkdir(exist_ok=True)
    manifest.write_text(
        "[project]\n"
        f"name = {name!r}\n"
        "version = '0.1.0'\n"
        "entrypoint = 'main'\n"
        "source_roots = ['src']\n"
        "profile = 'hosted'\n"
        "dependencies = []\n"
        "foreign_libraries = []\n"
        "external_executables = []\n"
        "services = []\n",
        encoding="utf-8",
        newline="\n",
    )
    source = path / "src" / "main.s3"
    if overwrite or not source.exists():
        source.write_text("fn main() -> i64:\n    return 0\n", encoding="utf-8", newline="\n")
    return manifest


def project_summary(root: str | Path) -> dict[str, object]:
    """Return stable human/tooling summary for a valid project."""

    try:
        tooling = ProjectTooling(Path(root))
        manifest = tooling.check()
    except ProjectContainerError:
        raise
    return {
        "name": manifest.name,
        "version": manifest.version,
        "entrypoint": manifest.entrypoint,
        "profile": manifest.profile,
        "source_roots": manifest.source_roots,
        "sources": tuple(sorted(tooling._sources())),
        "dependencies": manifest.dependencies,
    }
