"""Observable platform crypto-provider capabilities without custom primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
import ssl


@dataclass(frozen=True, slots=True)
class CryptoProviderInventory:
    tls_provider: str
    ed25519_provider: str
    tls_available: bool
    ed25519_available: bool

    @property
    def json(self) -> str:
        return json.dumps(
            {
                "ed25519_available": self.ed25519_available,
                "ed25519_provider": self.ed25519_provider,
                "tls_available": self.tls_available,
                "tls_provider": self.tls_provider,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"


def discover_crypto_providers() -> CryptoProviderInventory:
    """Report actual imports/versions; absence is never silently downgraded."""

    tls_provider = str(getattr(ssl, "OPENSSL_VERSION", "")).strip()
    tls_available = bool(tls_provider)
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: F401
        from cryptography import __version__ as cryptography_version
    except ImportError:
        ed25519_provider = "unavailable"
        ed25519_available = False
    else:
        ed25519_provider = f"cryptography:{cryptography_version}:Ed25519"
        ed25519_available = True
    return CryptoProviderInventory(
        tls_provider or "unavailable",
        ed25519_provider,
        tls_available,
        ed25519_available,
    )
