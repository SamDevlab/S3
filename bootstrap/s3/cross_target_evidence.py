"""Deterministic classification of cross-target execution evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Iterable


class CrossTargetEvidenceError(ValueError):
    """Raised when cross-target evidence is malformed or ambiguous."""


class CrossTarget(StrEnum):
    LINUX_X86_64 = "linux-x86-64"
    LINUX_AARCH64 = "linux-aarch64"
    MACOS_ARM64 = "macos-arm64"


class EvidenceClass(StrEnum):
    NATIVE = "NATIVE"
    EMULATED = "EMULATED"
    STRUCTURAL_ONLY = "STRUCTURAL_ONLY"
    DEFERRED = "DEFERRED"


_MODES = {"NATIVE", "EMULATED", "STRUCTURAL_ONLY", "DEFERRED"}
_STATUSES = {"PASS", "FAIL", "NOT_RUN"}


@dataclass(frozen=True, slots=True)
class CrossTargetObservation:
    target: str
    execution_mode: str
    target_host_match: bool
    correctness: str
    structural: str

    def validate(self) -> None:
        try:
            CrossTarget(self.target)
        except ValueError as error:
            raise CrossTargetEvidenceError(f"unsupported target: {self.target!r}") from error
        if self.execution_mode not in _MODES:
            raise CrossTargetEvidenceError(
                f"invalid execution mode: {self.execution_mode!r}"
            )
        if not isinstance(self.target_host_match, bool):
            raise CrossTargetEvidenceError("target_host_match must be boolean")
        if self.correctness not in _STATUSES:
            raise CrossTargetEvidenceError(f"invalid correctness status: {self.correctness!r}")
        if self.structural not in _STATUSES:
            raise CrossTargetEvidenceError(f"invalid structural status: {self.structural!r}")


@dataclass(frozen=True, slots=True)
class CrossTargetEvidence:
    target: str
    classification: EvidenceClass
    correctness: str
    structural: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_target_observation(
    observation: CrossTargetObservation,
) -> CrossTargetEvidence:
    """Classify one observation without upgrading structural output to native."""

    observation.validate()
    if observation.execution_mode == "NATIVE":
        if not observation.target_host_match:
            return _deferred(observation, "native_target_host_mismatch")
        if observation.correctness != "PASS":
            return _deferred(observation, "native_correctness_not_pass")
        if observation.structural != "PASS":
            return _deferred(observation, "native_structural_not_pass")
        return CrossTargetEvidence(
            observation.target,
            EvidenceClass.NATIVE,
            observation.correctness,
            observation.structural,
            "native_target_execution_verified",
        )
    if observation.execution_mode == "EMULATED":
        if observation.correctness != "PASS":
            return _deferred(observation, "emulated_correctness_not_pass")
        return CrossTargetEvidence(
            observation.target,
            EvidenceClass.EMULATED,
            observation.correctness,
            observation.structural,
            "hosted_emulation_verified",
        )
    if observation.execution_mode == "STRUCTURAL_ONLY":
        if observation.structural != "PASS":
            return _deferred(observation, "structural_validation_not_pass")
        return CrossTargetEvidence(
            observation.target,
            EvidenceClass.STRUCTURAL_ONLY,
            observation.correctness,
            observation.structural,
            "artifact_structure_verified_without_native_execution",
        )
    return _deferred(observation, "execution_evidence_deferred")


def analyze_cross_target_evidence(
    observations: Iterable[CrossTargetObservation],
) -> dict[str, Any]:
    """Build a deterministic report with explicit entries for missing targets."""

    indexed: dict[str, CrossTargetEvidence] = {}
    for observation in observations:
        evidence = classify_target_observation(observation)
        if evidence.target in indexed:
            raise CrossTargetEvidenceError(
                f"duplicate target evidence: {evidence.target}"
            )
        indexed[evidence.target] = evidence
    entries = []
    for target in CrossTarget:
        evidence = indexed.get(target.value)
        if evidence is None:
            evidence = CrossTargetEvidence(
                target.value,
                EvidenceClass.DEFERRED,
                "NOT_RUN",
                "NOT_RUN",
                "target_evidence_missing",
            )
        entries.append(evidence.to_dict())
    counts = {
        evidence_class.value: sum(
            entry["classification"] == evidence_class.value for entry in entries
        )
        for evidence_class in EvidenceClass
    }
    return {
        "targets": entries,
        "counts": counts,
        "native_pass": counts[EvidenceClass.NATIVE.value],
        "structural_output_is_native": False,
    }


def _deferred(
    observation: CrossTargetObservation,
    reason: str,
) -> CrossTargetEvidence:
    return CrossTargetEvidence(
        observation.target,
        EvidenceClass.DEFERRED,
        observation.correctness,
        observation.structural,
        reason,
    )

