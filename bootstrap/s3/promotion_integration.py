"""Candidate metadata integration for the fail-closed promotion framework."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from .canonical_serialization import CanonicalSerializationError, serialize_canonical
from .differential import DifferentialResult
from .experiment_promotion import (
    PromotionContract,
    PromotionDecision,
    PromotionFrameworkError,
    resolve_promotion,
)


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class CandidatePromotionError(PromotionFrameworkError):
    """Raised when candidate metadata cannot support a promotion decision."""


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Canonical evidence binding a candidate to one source and one diff case."""

    component_id: str
    source_lock_sha: str
    provenance: Mapping[str, object]
    differential_result: DifferentialResult
    eligible: bool = True
    structural_evidence: str = "PASS"
    fallback_available: bool = True
    default_enabled: bool = False

    def validate(self) -> None:
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise CandidatePromotionError("component_id must be non-empty")
        if not isinstance(self.provenance, Mapping) or not self.provenance:
            raise CandidatePromotionError("provenance must be a non-empty mapping")
        if not isinstance(self.differential_result, DifferentialResult):
            raise CandidatePromotionError("differential_result has an invalid type")
        result = self.differential_result
        if not isinstance(result.case_id, str) or not result.case_id:
            raise CandidatePromotionError("differential case_id must be non-empty")
        if not isinstance(result.input_json, str) or not result.input_json:
            raise CandidatePromotionError("differential input_json must be non-empty")
        if not _DIGEST.fullmatch(result.input_sha256):
            raise CandidatePromotionError("differential input digest is invalid")
        if hashlib.sha256(result.input_json.encode("utf-8")).hexdigest() != result.input_sha256:
            raise CandidatePromotionError("differential input digest does not match")
        try:
            decoded_input = json.loads(result.input_json)
            canonical_input = serialize_canonical(decoded_input)
        except (CanonicalSerializationError, TypeError, ValueError) as error:
            raise CandidatePromotionError("differential input is not canonical") from error
        if canonical_input != result.input_json:
            raise CandidatePromotionError("differential input is not canonical")
        try:
            expected_provenance = serialize_canonical(dict(self.provenance))
            recorded_provenance = json.loads(result.provenance_json)
            recorded_canonical = serialize_canonical(recorded_provenance)
        except (CanonicalSerializationError, TypeError, ValueError) as error:
            raise CandidatePromotionError("differential provenance is not canonical") from error
        if recorded_canonical != result.provenance_json or recorded_canonical != expected_provenance:
            raise CandidatePromotionError("differential provenance does not match metadata")
        if recorded_provenance.get("component_id") != self.component_id:
            raise CandidatePromotionError("differential provenance component mismatch")
        if recorded_provenance.get("source_lock_sha") != self.source_lock_sha:
            raise CandidatePromotionError("differential provenance source mismatch")
        if not isinstance(result.match, bool):
            raise CandidatePromotionError("differential match must be boolean")

    def to_contract(self) -> PromotionContract:
        """Convert validated evidence into the shared promotion contract."""

        self.validate()
        return PromotionContract(
            component_id=self.component_id,
            source_lock_sha=self.source_lock_sha,
            eligible=self.eligible,
            correctness_evidence="PASS" if self.differential_result.match else "FAIL",
            structural_evidence=self.structural_evidence,
            fallback_available=self.fallback_available,
            default_enabled=self.default_enabled,
        )


def resolve_candidate_promotion(
    metadata: CandidateMetadata,
    *,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
) -> PromotionDecision:
    """Resolve canonical candidate evidence through the shared framework."""

    return resolve_promotion(
        metadata.to_contract(),
        observed_source_sha=observed_source_sha,
        explicit_opt_in=explicit_opt_in,
    )
