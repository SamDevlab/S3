"""Package signature and provenance verification boundary for M1.87."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Protocol

from .results import Result
from .registry_security import canonical_https_origin


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
    source: str = "https://registry.fixture"


@dataclass(frozen=True, slots=True)
class TrustedPublicKey:
    key_id: str
    publisher: str
    public_key: bytes


class VettedSignatureVerifier(Protocol):
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class CryptographyEd25519Verifier:
    """Ed25519 verifier backed by the vetted ``cryptography`` provider.

    The dependency is optional so the bootstrap compiler remains usable in
    minimal/offline environments.  Production signature verification fails
    closed when the provider is unavailable; no home-grown crypto fallback is
    provided.
    """

    algorithm = "Ed25519"
    provider = "cryptography"

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError as error:  # pragma: no cover - environment dependent
            raise RuntimeError("cryptography optional dependency is required for Ed25519 verification") from error
        try:
            key = Ed25519PublicKey.from_public_bytes(public_key)
            key.verify(signature, message)
            return True
        except (InvalidSignature, ValueError):
            return False


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
        if (
            not isinstance(key.key_id, str)
            or not key.key_id
            or len(key.key_id) > 128
            or not key.key_id.isascii()
            or any(character.isspace() for character in key.key_id)
            or not isinstance(key.publisher, str)
            or not key.publisher
            or len(key.publisher) > 256
            or not isinstance(key.public_key, bytes)
            or not key.public_key
            or len(key.public_key) > 4096
        ):
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
    def __init__(
        self,
        trust_store: PublicTrustStore,
        verifier: VettedSignatureVerifier | None = None,
        *,
        max_provenance: int = 32,
        max_signature_bytes: int = 4096,
    ) -> None:
        if isinstance(max_provenance, bool) or not isinstance(max_provenance, int) or max_provenance <= 0:
            raise ValueError("max_provenance must be a positive integer")
        if isinstance(max_signature_bytes, bool) or not isinstance(max_signature_bytes, int) or max_signature_bytes <= 0:
            raise ValueError("max_signature_bytes must be a positive integer")
        self.trust_store = trust_store
        self.verifier = verifier or CryptographyEd25519Verifier()
        self.max_provenance = max_provenance
        self.max_signature_bytes = max_signature_bytes

    @property
    def provider_identity(self) -> str:
        return f"{getattr(self.verifier, 'provider', type(self.verifier).__name__)}:{getattr(self.verifier, 'algorithm', 'unknown')}"

    @property
    def provider_is_vetted(self) -> bool:
        return isinstance(self.verifier, CryptographyEd25519Verifier)

    @property
    def provider_is_available(self) -> bool:
        if not self.provider_is_vetted:
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: F401
        except ImportError:
            return False
        return True

    def verify(self, envelope: PackageSignatureEnvelope, body: bytes) -> Result[VerifiedPackage, SignatureError]:
        if not _valid_envelope(envelope, body, self.max_signature_bytes):
            return Result.err(SignatureError(SignatureErrorCode.INVALID_ENVELOPE, "verify", "signature envelope is invalid or exceeds bounds"))
        if not _DIGEST.fullmatch(envelope.digest) or hashlib.sha256(body).hexdigest() != envelope.digest:
            return Result.err(SignatureError(SignatureErrorCode.DIGEST_MISMATCH, "verify", "package bytes do not match signed digest"))
        if (
            len(envelope.provenance) > self.max_provenance
            or len({key for key, _value in envelope.provenance}) != len(envelope.provenance)
            or any(
                not isinstance(key, str)
                or not key
                or len(key) > 128
                or not isinstance(value, str)
                or len(value) > 1024
                for key, value in envelope.provenance
            )
        ):
            return Result.err(SignatureError(SignatureErrorCode.INVALID_PROVENANCE, "verify", "provenance is not unique bounded string metadata"))
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
    """Canonical immutable material signed by M1.87.

    The key id and registry/source identity are included in addition to package
    identity, digest, publisher, and provenance.  This prevents a valid
    signature from being replayed under an unrelated trust/source record.
    """

    document = {
        "digest": envelope.digest,
        "key_id": envelope.key_id,
        "name": envelope.name,
        "provenance": {key: value for key, value in sorted(envelope.provenance)},
        "publisher": envelope.publisher,
        "source": envelope.source,
        "version": envelope.version,
    }
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _valid_envelope(envelope: PackageSignatureEnvelope, body: bytes, max_signature_bytes: int) -> bool:
    return (
        isinstance(body, bytes)
        and isinstance(envelope.name, str)
        and 0 < len(envelope.name) <= 256
        and isinstance(envelope.version, str)
        and 0 < len(envelope.version) <= 128
        and isinstance(envelope.publisher, str)
        and 0 < len(envelope.publisher) <= 256
        and isinstance(envelope.key_id, str)
        and 0 < len(envelope.key_id) <= 128
        and isinstance(envelope.source, str)
        and _valid_source(envelope.source)
        and len(envelope.source) <= 2048
        and isinstance(envelope.signature, bytes)
        and 0 < len(envelope.signature) <= max_signature_bytes
    )


def _valid_source(source: str) -> bool:
    try:
        canonical_https_origin(source)
    except ValueError:
        return False
    return True
