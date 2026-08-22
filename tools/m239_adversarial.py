"""Small deterministic mutation corpus for M2.39 parser hardening."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class MutationCase:
    name: str
    payload: bytes


def bounded_mutations(
    corpus: Sequence[bytes],
    *,
    max_cases: int = 128,
    max_bytes: int = 4096,
) -> tuple[MutationCase, ...]:
    """Return a deterministic, bounded set of truncation and byte mutations."""

    if isinstance(max_cases, bool) or not isinstance(max_cases, int) or max_cases <= 0:
        raise ValueError("max_cases must be a positive integer")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    cases: list[MutationCase] = []
    seen: set[bytes] = set()
    for corpus_index, source in enumerate(corpus):
        if not isinstance(source, bytes):
            raise TypeError("mutation corpus entries must be bytes")
        payload = source[:max_bytes]
        candidates = (
            ("empty", b""),
            ("truncated", payload[: len(payload) // 2]),
            ("nul-prefix", b"\x00" + payload),
            ("high-byte-suffix", payload + b"\xff"),
            ("repeated", (payload + payload)[:max_bytes]),
        )
        for mutation_name, mutated in candidates:
            if len(cases) >= max_cases:
                return tuple(cases)
            mutated = mutated[:max_bytes]
            if mutated in seen:
                continue
            seen.add(mutated)
            cases.append(MutationCase(f"{corpus_index}:{mutation_name}", mutated))
    return tuple(cases)
