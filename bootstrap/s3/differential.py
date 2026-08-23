"""Deterministic hosted reference-versus-candidate differential harness."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .canonical_serialization import (
    CanonicalSerializationError,
    serialize_canonical,
)


class DifferentialCaseError(ValueError):
    """Raised when a differential case or observation cannot be certified."""


@dataclass(frozen=True, slots=True)
class DifferentialResult:
    case_id: str
    input_json: str
    input_sha256: str
    provenance_json: str
    reference_output: str | None
    candidate_output: str | None
    reference_error: str | None
    candidate_error: str | None
    match: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "input_json": self.input_json,
            "input_sha256": self.input_sha256,
            "provenance_json": self.provenance_json,
            "reference_output": self.reference_output,
            "candidate_output": self.candidate_output,
            "reference_error": self.reference_error,
            "candidate_error": self.candidate_error,
            "match": self.match,
        }


class DifferentialHarness:
    """Run one exact-input differential case with deterministic evidence."""

    def __init__(self, *, max_bytes: int = 16_777_216) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
            raise TypeError("max_bytes must be an integer")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.max_bytes = max_bytes

    def run(
        self,
        case_id: str,
        input_value: object,
        reference: Callable[[object], object],
        candidate: Callable[[object], object],
        *,
        provenance: Mapping[str, object],
    ) -> DifferentialResult:
        if not isinstance(case_id, str) or not case_id:
            raise DifferentialCaseError("case_id must be a non-empty string")
        if not callable(reference) or not callable(candidate):
            raise TypeError("reference and candidate must be callable")
        if not isinstance(provenance, Mapping) or not provenance:
            raise DifferentialCaseError("provenance must be a non-empty mapping")
        input_json = self._canonical(input_value, "input")
        provenance_json = self._canonical(dict(provenance), "provenance")
        exact_input = json.loads(input_json)
        reference_output, reference_error = self._observe(reference, exact_input)
        candidate_output, candidate_error = self._observe(
            candidate,
            json.loads(input_json),
        )
        return DifferentialResult(
            case_id=case_id,
            input_json=input_json,
            input_sha256=_sha256(input_json),
            provenance_json=provenance_json,
            reference_output=reference_output,
            candidate_output=candidate_output,
            reference_error=reference_error,
            candidate_error=candidate_error,
            match=(
                reference_output == candidate_output
                and reference_error == candidate_error
            ),
        )

    def _observe(
        self,
        function: Callable[[object], object],
        input_value: object,
    ) -> tuple[str | None, str | None]:
        try:
            output = function(input_value)
        except Exception as error:
            return None, self._canonical(
                {"message": str(error), "type": type(error).__name__},
                "error",
            )
        return self._canonical(output, "output"), None

    def _canonical(self, value: object, kind: str) -> str:
        try:
            return serialize_canonical(value, max_bytes=self.max_bytes)
        except (CanonicalSerializationError, TypeError, ValueError) as error:
            raise DifferentialCaseError(
                f"differential {kind} is not canonically serializable"
            ) from error


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
