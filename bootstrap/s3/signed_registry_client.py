"""End-to-end signed registry consumption over the bounded v2 resolver."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .package_signatures import (
    CryptographyEd25519Verifier,
    PackageSignatureEnvelope,
    PackageSignatureService,
    PublicTrustStore,
    VerifiedPackage,
)
from .registry_v2 import RegistryV2Client, RegistryV2Error, RegistryV2Limits, RegistryV2Lock
from .signed_registry_index import VerifiedRegistryIndex


class SignedRegistryErrorCode(Enum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_PACKAGE_ENVELOPE = "invalid_package_envelope"
    UNSIGNED_DOWNGRADE = "unsigned_downgrade"
    SIGNATURE_FAILURE = "signature_failure"
    REGISTRY_FAILURE = "registry_failure"


class SignedRegistryError(ValueError):
    def __init__(self, code: SignedRegistryErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True, slots=True)
class SignedRegistryPackage:
    lock: RegistryV2Lock
    envelope: PackageSignatureEnvelope


class SignedRegistryV2Client:
    """Read-only v2 registry client requiring vetted Ed25519 package proofs.

    The signed index is supplied as an already verified document. Every
    resolved package must carry a signature envelope in that document, and
    every fetched object is checked against both its content hash and its
    package signature before it is returned. The underlying v2 cache is safe
    for offline reuse because it only stores hash-checked bytes.
    """

    def __init__(
        self,
        resolver: RegistryV2Client,
        packages: Mapping[tuple[str, str, str], SignedRegistryPackage],
        signature_service: PackageSignatureService,
    ) -> None:
        if not signature_service.provider_is_vetted:
            raise SignedRegistryError(
                SignedRegistryErrorCode.PROVIDER_UNAVAILABLE,
                "signed registry requires the vetted Ed25519 provider",
            )
        if not signature_service.provider_is_available:
            raise SignedRegistryError(
                SignedRegistryErrorCode.PROVIDER_UNAVAILABLE,
                "vetted Ed25519 provider is unavailable",
            )
        self._resolver = resolver
        self._packages = dict(packages)
        self._signature_service = signature_service

    @classmethod
    def from_verified_index(
        cls,
        root: Path,
        verified_index: VerifiedRegistryIndex,
        trust_store: PublicTrustStore,
        *,
        limits: RegistryV2Limits | None = None,
    ) -> "SignedRegistryV2Client":
        if not isinstance(verified_index, VerifiedRegistryIndex):
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                "signed registry requires a verified index",
            )
        service = PackageSignatureService(trust_store, CryptographyEd25519Verifier())
        packages = _parse_signed_packages(
            verified_index.document,
            expected_source=verified_index.envelope.origin,
        )
        resolver = RegistryV2Client.from_verified_index(root, verified_index, limits=limits)
        return cls(resolver, packages, service)

    @property
    def read_only(self) -> bool:
        return True

    @property
    def provider_identity(self) -> str:
        return self._signature_service.provider_identity

    def resolve(self, name: str, version: str):
        return self._resolver.resolve(name, version)

    def fetch(self, lock: RegistryV2Lock) -> bytes:
        return self.fetch_verified(lock).body

    def fetch_verified(self, lock: RegistryV2Lock) -> VerifiedPackage:
        package = self._packages.get((lock.name, lock.version, lock.sha256))
        if package is None:
            raise SignedRegistryError(
                SignedRegistryErrorCode.UNSIGNED_DOWNGRADE,
                f"package {lock.name}@{lock.version} has no signed envelope",
            )
        try:
            body = self._resolver.fetch(lock)
        except RegistryV2Error as error:
            raise SignedRegistryError(
                SignedRegistryErrorCode.REGISTRY_FAILURE,
                str(error),
            ) from error
        verification = self._signature_service.verify(package.envelope, body)
        if verification.is_err:
            error = verification.error_or(None)
            assert error is not None
            raise SignedRegistryError(
                SignedRegistryErrorCode.SIGNATURE_FAILURE,
                f"{error.code.value}: {error.detail}",
            )
        verified = verification.value_or(None)
        assert verified is not None
        return verified


def _parse_signed_packages(
    document: Mapping[str, object],
    *,
    expected_source: str,
) -> dict[tuple[str, str, str], SignedRegistryPackage]:
    if not isinstance(document, Mapping) or not isinstance(expected_source, str):
        raise SignedRegistryError(
            SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
            "signed registry index document is invalid",
        )
    raw_packages = document.get("packages")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise SignedRegistryError(
            SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
            "signed registry index has no package list",
        )
    packages: dict[tuple[str, str, str], SignedRegistryPackage] = {}
    for raw_package in raw_packages:
        if not isinstance(raw_package, dict):
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                "signed registry package entry is not an object",
            )
        name = raw_package.get("name")
        version = raw_package.get("version")
        digest = raw_package.get("sha256")
        signature = raw_package.get("signature")
        if (
            not isinstance(name, str)
            or not isinstance(version, str)
            or not isinstance(digest, str)
            or not isinstance(signature, dict)
        ):
            raise SignedRegistryError(
                SignedRegistryErrorCode.UNSIGNED_DOWNGRADE,
                "every registry package must carry a signed envelope",
            )
        publisher = signature.get("publisher")
        key_id = signature.get("key_id")
        encoded_signature = signature.get("signature_b64")
        source = signature.get("source")
        raw_provenance = signature.get("provenance", {})
        if (
            not isinstance(publisher, str)
            or not isinstance(key_id, str)
            or not isinstance(encoded_signature, str)
            or not isinstance(source, str)
            or not isinstance(raw_provenance, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in raw_provenance.items())
        ):
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                f"package {name}@{version} signature metadata is invalid",
            )
        if source != expected_source:
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                f"package {name}@{version} signature source does not match the signed index",
            )
        try:
            raw_signature = base64.b64decode(encoded_signature.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError, binascii.Error) as error:
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                f"package {name}@{version} signature encoding is invalid",
            ) from error
        envelope = PackageSignatureEnvelope(
            name,
            version,
            digest,
            publisher,
            key_id,
            raw_signature,
            tuple(sorted(raw_provenance.items())),
            source,
        )
        try:
            lock = RegistryV2Lock(name, version, digest)
        except RegistryV2Error as error:
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                f"package {name}@{version} lock is invalid",
            ) from error
        identity = (name, version, digest)
        if identity in packages:
            raise SignedRegistryError(
                SignedRegistryErrorCode.INVALID_PACKAGE_ENVELOPE,
                f"duplicate signed package identity {name}@{version}",
            )
        packages[identity] = SignedRegistryPackage(lock, envelope)
    return packages
