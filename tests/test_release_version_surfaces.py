from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION
from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.wasm_target import artifact_identity


ROOT = Path(__file__).resolve().parents[1]


def _distribution_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_release_candidate_distribution_and_compiler_identity_are_synchronized() -> None:
    distribution_version = _distribution_version()
    assert distribution_version == "1.0.0"

    compiler_default = inspect.signature(artifact_identity).parameters[
        "compiler_version"
    ].default
    assert compiler_default == f"s3-bootstrap-{distribution_version}"


def test_stable_1_0_does_not_silently_bump_language_or_artifact_contracts() -> None:
    mode_default = inspect.signature(compile_source).parameters["mode"].default
    assert mode_default is SyntaxMode.V0_6
    assert IR_FORMAT_VERSION == "0.6.0"
    assert ASSEMBLY_FORMAT_VERSION == "0.7.0"
    assert DIAGNOSTIC_SCHEMA_VERSION == "1.0.0"
