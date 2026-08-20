"""Canonical signed registry index trust policy for M1.96."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Mapping, Protocol

from .package_signatures import PublicTrustStore, TrustedPublicKey
from .results import Result


class SignedIndexErrorCode(Enum):
    INVALID_ENVELOPE = "invalid_envelope"
    UNKNOWN_KEY = "unknown_key"
    PUBLISHER_MISMATCH = "publisher_mismatch"
    ORIGIN_MISMATCH = "origin_mismatch"
    REVOKED_KEY = "revoked_key"
    DOWNGRADE = "downgrade"
    INVALID_SIGNATURE = "invalid_signature"
    VERIFIER_FAILURE = "verifier_failure"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class SignedIndexError:
    code: SignedIndexErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class SignedIndexEnvelope:
    origin: str
    publisher: str
    key_id: str
    generation: int
    index: bytes
    signature: bytes


@dataclass(frozen=True, slots=True)
class VerifiedRegistryIndex:
    envelope: SignedIndexEnvelope
    document: Mapping[str, object]
    signing_payload: bytes


class SignedIndexVerifier(Protocol):
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class SignedRegistryIndexTrust:
    def __init__(
        self,
        trust_store: PublicTrustStore,
        verifier: SignedIndexVerifier,
        *,
        expected_origin: str,
        max_index_bytes: int = 1 << 20,
        max_signature_bytes: int = 4096,
    ) -> None:
        if not isinstance(expected_origin, str) or not expected_origin.startswith("https://") or expected_origin.endswith("/"):
            raise ValueError("expected registry origin must be canonical HTTPS")
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (max_index_bytes, max_signature_bytes)):
            raise ValueError("signed index limits must be positive integers")
        self.trust_store = trust_store
        self.verifier = verifier
        self.expected_origin = expected_origin.lower()
        self.max_index_bytes = max_index_bytes
        self.max_signature_bytes = max_signature_bytes
        self._revoked: set[str] = set()
        self._highest_generation = -1

    @property
    def highest_generation(self) -> int:
        return self._highest_generation

    def revoke(self, key_id: str) -> Result[None, SignedIndexError]:
        if not isinstance(key_id, str) or not key_id:
            return Result.err(SignedIndexError(SignedIndexErrorCode.INVALID_ENVELOPE, "revoke", "key id is invalid"))
        self._revoked.add(key_id)
        return Result.ok(None)

    def verify(self, envelope: SignedIndexEnvelope) -> Result[VerifiedRegistryIndex, SignedIndexError]:
        if (
            not isinstance(envelope.origin, str)
            or envelope.origin.lower() != self.expected_origin
            or not isinstance(envelope.publisher, str)
            or not envelope.publisher
            or not isinstance(envelope.key_id, str)
            or not envelope.key_id
            or isinstance(envelope.generation, bool)
            or not isinstance(envelope.generation, int)
            or envelope.generation < 0
            or not isinstance(envelope.index, bytes)
            or not 0 < len(envelope.index) <= self.max_index_bytes
            or not isinstance(envelope.signature, bytes)
            or not 0 < len(envelope.signature) <= self.max_signature_bytes
        ):
            return Result.err(SignedIndexError(SignedIndexErrorCode.INVALID_ENVELOPE, "verify", "signed index envelope is invalid or exceeds limits"))
        if envelope.generation <= self._highest_generation:
            return Result.err(SignedIndexError(SignedIndexErrorCode.DOWNGRADE, "verify", "index generation is not newer than the accepted generation"))
        if envelope.key_id in self._revoked:
            return Result.err(SignedIndexError(SignedIndexErrorCode.REVOKED_KEY, "verify", envelope.key_id))
        key = self.trust_store.resolve(envelope.key_id)
        if key is None:
            return Result.err(SignedIndexError(SignedIndexErrorCode.UNKNOWN_KEY, "verify", envelope.key_id))
        if key.publisher != envelope.publisher:
            return Result.err(SignedIndexError(SignedIndexErrorCode.PUBLISHER_MISMATCH, "verify", "trusted key publisher differs"))
        try:
            document = json.loads(envelope.index.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(SignedIndexError(SignedIndexErrorCode.INVALID_ENVELOPE, "verify", "index is not valid UTF-8 JSON"))
        if not isinstance(document, dict) or document.get("format") != "s3.registry.index.v2" or str(document.get("origin", "")).lower() != self.expected_origin:
            return Result.err(SignedIndexError(SignedIndexErrorCode.ORIGIN_MISMATCH, "verify", "index document origin or format is invalid"))
        payload = canonical_signed_index_payload(envelope)
        try:
            valid = self.verifier.verify(key.public_key, payload, envelope.signature)
        except Exception as error:
            return Result.err(SignedIndexError(SignedIndexErrorCode.VERIFIER_FAILURE, "verify", type(error).__name__))
        if valid is not True:
            return Result.err(SignedIndexError(SignedIndexErrorCode.INVALID_SIGNATURE, "verify", "trusted provider rejected signature"))
        self._highest_generation = envelope.generation
        return Result.ok(VerifiedRegistryIndex(envelope, document, payload))


def canonical_signed_index_payload(envelope: SignedIndexEnvelope) -> bytes:
    header = {
        "generation": envelope.generation,
        "index_sha256": hashlib.sha256(envelope.index).hexdigest(),
        "key_id": envelope.key_id,
        "origin": envelope.origin.lower(),
        "publisher": envelope.publisher,
    }
    return (json.dumps(header, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8") + envelope.index
