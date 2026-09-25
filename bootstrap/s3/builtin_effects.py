"""Conservative effect contracts for dynamic builtins used by optimizers."""

from __future__ import annotations

from enum import Enum


class BuiltinEffect(str, Enum):
    PURE = "pure"
    READ_ONLY = "read-only"
    MUTATES = "mutates"
    UNKNOWN = "unknown"


_PURE = frozenset({"sqrt"})
_READ_ONLY = frozenset(
    {
        "tryte_vector_len",
        "tryte_vector_capacity",
        "tryte_vector_get",
        "i64_vector_len",
        "i64_vector_capacity",
        "i64_vector_get",
        "f64_vector_len",
        "f64_vector_capacity",
        "f64_vector_get",
    }
)
_MUTATING = frozenset(
    {
        f"{element}_vector_{operation}"
        for element in ("tryte", "i64", "f64")
        for operation in ("reserve", "push", "pop", "set")
    }
)


def builtin_effect(name: str | None) -> BuiltinEffect:
    """Return a closed-world effect classification; unknown names stay unknown."""

    if name in _PURE:
        return BuiltinEffect.PURE
    if name in _READ_ONLY:
        return BuiltinEffect.READ_ONLY
    if name in _MUTATING:
        return BuiltinEffect.MUTATES
    return BuiltinEffect.UNKNOWN
