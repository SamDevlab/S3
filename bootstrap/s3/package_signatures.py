"""Package signature and provenance verification boundary for M1.87."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Protocol

from .results import Result


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class SignatureErrorCode(Enum):
    INVALID_ENVELOPE = "invalid_envelope"
    DIGEST_MISMATCH = "digest_mismatch"
    UNKNOWN_KEY = "unknown_key"
    PUBLISHER_MISMATCH = "publisher_mismatch"
    INVALID_PROVENANCE = "invalid_provenance"
    INVALID_SIGNATURE = "invalid_signature"
    VERIFIER_FAILURE = "verifier_failure"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class SignatureError:
    code: SignatureErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class PackageSignatureEnvelope:
    name: str
    version: str
    digest: str
    publisher: str
    key_id: str
    signature: bytes
    provenance: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class TrustedPublicKey:
    key_id: str
    publisher: str
    public_key: bytes


class VettedSignatureVerifier(Protocol):
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class VerifiedPackage:
    envelope: PackageSignatureEnvelope
    body: bytes
    signing_payload: bytes


class PublicTrustStore:
    def __init__(self, *, max_keys: int = 128) -> None:
        if isinstance(max_keys, bool) or not isinstance(max_keys, int) or max_keys <= 0:
            raise ValueError("max_keys must be a positive integer")
        self._max_keys = max_keys
        self._keys: dict[str, TrustedPublicKey] = {}

    def add(self, key: TrustedPublicKey) -> Result[None, SignatureError]:
        if not key.key_id or not key.publisher or not isinstance(key.public_key, bytes) or not key.public_key:
            return Result.err(SignatureError(SignatureErrorCode.INVALID_ENVELOPE, "trust_store", "public key record is invalid"))
        if key.key_id in self._keys:
            return Result.err(SignatureError(SignatureErrorCode.INVALID_ENVELOPE, "trust_store", "duplicate public key identity"))
        if len(self._keys) >= self._max_keys:
            return Result.err(SignatureError(SignatureErrorCode.LIMIT, "trust_store", "public key limit exceeded"))
        self._keys[key.key_id] = key
        return Result.ok(None)

    def resolve(self, key_id: str) -> TrustedPublicKey | None:
        return self._keys.get(key_id)


class PackageSignatureService:
    def __init__(self, trust_store: PublicTrustStore, verifier: VettedSignatureVerifier, *, max_provenance: int = 32) -> None:
        if isinstance(max_provenance, bool) or not isinstance(max_provenance, int) or max_provenance <= 0:
            raise ValueError("max_provenance must be a positive integer")
        self.trust_store = trust_store
        self.verifier = verifier
        self.max_provenance = max_provenance

    def verify(self, envelope: PackageSignatureEnvelope, body: bytes) -> Result[VerifiedPackage, SignatureError]:
        if not isinstance(body, bytes) or not envelope.name or not envelope.version or not envelope.publisher or not envelope.key_id or not isinstance(envelope.signature, bytes):
            return Result.err(SignatureError(SignatureErrorCode.INVALID_ENVELOPE, "verify", "signature envelope is invalid"))
        if not _DIGEST.fullmatch(envelope.digest) or hashlib.sha256(body).hexdigest() != envelope.digest:
            return Result.err(SignatureError(SignatureErrorCode.DIGEST_MISMATCH, "verify", "package bytes do not match signed digest"))
        if len(envelope.provenance) > self.max_provenance or any(not isinstance(key, str) or not key or not isinstance(value, str) for key, value in envelope.provenance):
            return Result.err(SignatureError(SignatureErrorCode.INVALID_PROVENANCE, "verify", "provenance is not bounded string metadata"))
        key = self.trust_store.resolve(envelope.key_id)
        if key is None:
            return Result.err(SignatureError(SignatureErrorCode.UNKNOWN_KEY, "verify", envelope.key_id))
        if key.publisher != envelope.publisher:
            return Result.err(SignatureError(SignatureErrorCode.PUBLISHER_MISMATCH, "verify", "key publisher differs from envelope publisher"))
        payload = canonical_signing_payload(envelope)
        try:
            valid = self.verifier.verify(key.public_key, payload, envelope.signature)
        except Exception as error:
            return Result.err(SignatureError(SignatureErrorCode.VERIFIER_FAILURE, "verify", type(error).__name__))
        if valid is not True:
            return Result.err(SignatureError(SignatureErrorCode.INVALID_SIGNATURE, "verify", "vetted verifier rejected signature"))
        return Result.ok(VerifiedPackage(envelope, body, payload))


def canonical_signing_payload(envelope: PackageSignatureEnvelope) -> bytes:
    document = {
        "digest": envelope.digest,
        "name": envelope.name,
        "provenance": {key: value for key, value in sorted(envelope.provenance)},
        "publisher": envelope.publisher,
        "version": envelope.version,
    }
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
