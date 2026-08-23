"""M2.68 composed self-hosted Assembly frontend candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly_frontend_candidate import (
    AssemblyFrontendResult,
    analyze_bounded_assembly,
)
from .bounded_text import BoundedText, encode_ascii
from .emulator import execute_assembly
from .pipeline import compile_sources


M268_MODULUS = 301
M268_TEXT_CAPACITY = 364
M268_MAX_INSTRUCTIONS = 500_000
_ROOT = Path(__file__).resolve().parents[2]
_CLOSURE_SOURCE = (
    _ROOT / "selfhost/frontend/assembly_frontend_closure.s3"
).read_text(encoding="utf-8")
_MODULE_PATHS = (
    "selfhost/text/bounded_text_types.s3",
    "selfhost/assembly/tokenizer_types.s3",
    "selfhost/assembly/assembly_tokenizer.s3",
    "selfhost/assembly/parser_types.s3",
    "selfhost/assembly/assembly_parser.s3",
    "selfhost/assembly/frontend_types.s3",
    "selfhost/assembly/assembly_frontend.s3",
)
_MODULE_SOURCES = {
    path: (_ROOT / path).read_text(encoding="utf-8") for path in _MODULE_PATHS
}


class AssemblyFrontendClosureError(ValueError):
    """Raised when the bounded composed frontend cannot be executed."""


@dataclass(frozen=True, slots=True)
class AssemblyFrontendClosureEvidence:
    source: str
    reference_fingerprint: int
    candidate_fingerprint: int

    @property
    def match(self) -> bool:
        return self.reference_fingerprint == self.candidate_fingerprint


def _mix_value(checksum: int, value: int) -> int:
    for _ in range(5):
        checksum = (checksum * 2) % M268_MODULUS
    return (checksum + value) % M268_MODULUS


def _summary_fingerprint(result: AssemblyFrontendResult) -> int:
    if result.variant == "error":
        return -1
    if result.summary is None:
        raise AssemblyFrontendClosureError("frontend result has no summary")
    values = (
        result.summary.version,
        result.summary.function_count,
        result.summary.declaration_count,
        result.summary.block_count,
        result.summary.call_count,
        result.summary.return_count,
        result.summary.max_result_width,
        int(result.summary.ended),
    )
    checksum = 0
    for value in values:
        checksum = _mix_value(checksum, value)
    return checksum


def reference_assembly_frontend_fingerprint(source: str) -> int:
    """Return the Python frontend candidate's deterministic result fingerprint."""

    encoded = encode_ascii(source)
    if encoded.error is not None or encoded.text is None:
        raise AssemblyFrontendClosureError("Assembly source exceeds the bounded text capacity")
    return _summary_fingerprint(analyze_bounded_assembly(encoded.text))


def _driver_source(source: str) -> str:
    encoded = encode_ascii(source)
    if encoded.error is not None or encoded.text is None:
        raise AssemblyFrontendClosureError("Assembly source exceeds the bounded text capacity")
    units = ", ".join(str(value) for value in encoded.text.units)
    return (
        "module main\n"
        "\n"
        "from bounded_text_types import BoundedText\n"
        "from selfhost.frontend.assembly_frontend_closure import assembly_frontend_fingerprint\n"
        "\n"
        "fn main() -> tryte:\n"
        f"    units: tryte[{M268_TEXT_CAPACITY}] = [{units}]\n"
        f"    text: BoundedText = BoundedText(length={encoded.text.length}, units=units)\n"
        "    return assembly_frontend_fingerprint(text)\n"
    )


def candidate_assembly_frontend_fingerprint(source: str) -> int:
    """Execute the composed S3 frontend through the hosted Assembly emulator."""

    sources = dict(_MODULE_SOURCES)
    sources["selfhost/frontend/assembly_frontend_closure.s3"] = _CLOSURE_SOURCE
    sources["main.s3"] = _driver_source(source)
    try:
        compilation = compile_sources(sources, entry_module="main")
        if compilation.assembly is None:
            raise AssemblyFrontendClosureError("composed frontend emitted no assembly")
        return execute_assembly(
            compilation.assembly,
            max_instructions=M268_MAX_INSTRUCTIONS,
        )
    except AssemblyFrontendClosureError:
        raise
    except Exception as error:
        raise AssemblyFrontendClosureError(
            "composed S3 Assembly frontend execution failed"
        ) from error


def run_assembly_frontend_closure(source: str) -> AssemblyFrontendClosureEvidence:
    """Compare the composed S3 frontend with its Python reference candidate."""

    reference = reference_assembly_frontend_fingerprint(source)
    candidate = candidate_assembly_frontend_fingerprint(source)
    return AssemblyFrontendClosureEvidence(source, reference, candidate)
