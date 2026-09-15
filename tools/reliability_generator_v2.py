"""Deterministic grammar-aware source generation for Reliability Lab v2 R2."""

from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    GENERATOR_PROTOCOL,
    WORKER_REQUEST_SCHEMA,
    derive_case_seed,
    make_case_id,
    sha256_hex,
)

GENERATOR_VERSION = "s3.reliability.generator.v2.0.0"
_MASK64 = (1 << 64) - 1

CASE_KINDS = ("valid", "malformed", "mutated")
EXPECTED_SUCCESS = "SUCCESS"
EXPECTED_REJECTION = "REJECTION"

# R2 intentionally targets representative single-source 1.0 compositions.
# Multi-source module/import generation needs a future source-bundle transport;
# the frozen R0 worker request carries one exact source byte string.
REQUIRED_VALID_FEATURES = frozenset(
    {
        "aggregate.enum",
        "aggregate.record",
        "array.static",
        "control.match",
        "control.while",
        "function.call",
        "numeric.f64",
        "numeric.i64",
        "numeric.tryte",
        "reference.mutable",
    }
)


class SplitMix64:
    """Tiny fully specified PRNG; independent of Python's ``random`` module."""

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        if seed < 0 or seed > _MASK64:
            raise ValueError("seed must be in [0, 2^64-1]")
        self._state = seed

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK64
        return (value ^ (value >> 31)) & _MASK64

    def bounded(self, lower: int, upper: int) -> int:
        if lower > upper:
            raise ValueError("lower must not exceed upper")
        width = upper - lower + 1
        return lower + self.next_u64() % width

    def choose(self, values: Sequence[str]) -> str:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self.next_u64() % len(values)]


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    campaign_id: str
    case_index: int
    case_seed: int
    case_id: str
    case_kind: str
    family: str
    generator_version: str
    source: bytes
    source_sha256: str
    source_bytes: int
    expected_behavior: str
    features: tuple[str, ...]
    mutation: str | None = None

    def metadata(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "case_index": self.case_index,
            "case_seed": self.case_seed,
            "case_id": self.case_id,
            "case_kind": self.case_kind,
            "family": self.family,
            "generator_version": self.generator_version,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "expected_behavior": self.expected_behavior,
            "features": list(self.features),
            "mutation": self.mutation,
        }

    def worker_request(
        self,
        compiler_head: str,
        *,
        operation: str = "CHECK",
        optimization: str = "O0",
        backend: str = "hosted",
        options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if (
            not isinstance(compiler_head, str)
            or len(compiler_head) != 40
            or any(ch not in "0123456789abcdef" for ch in compiler_head)
        ):
            raise ValueError("compiler_head must be lowercase 40-hex")
        return {
            "schema": WORKER_REQUEST_SCHEMA,
            "case_id": self.case_id,
            "compiler_head": compiler_head,
            "source_b64": base64.b64encode(self.source).decode("ascii"),
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "operation": operation,
            "optimization": optimization,
            "backend": backend,
            "options": dict(options or {}),
        }


Renderer = Callable[[SplitMix64], tuple[bytes, tuple[str, ...]]]


def _render_scalar_call(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    left = rng.bounded(-20, 20)
    right = rng.bounded(-20, 20)
    source = (
        "fn add(a: tryte, b: tryte) -> tryte:\n"
        "    return a + b\n\n"
        "fn main() -> tryte:\n"
        f"    return add({left}, {right})\n"
    )
    return source.encode("utf-8"), ("function.call", "numeric.tryte")


def _render_i64_loop(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    limit = rng.bounded(1, 12)
    base = rng.bounded(-50, 50)
    source = (
        "fn main() -> i64:\n"
        "    mut i: i64 = 0\n"
        f"    mut total: i64 = {base}\n"
        f"    while i < {limit}:\n"
        "        total = total + i\n"
        "        i = i + 1\n"
        "    return total\n"
    )
    return source.encode("utf-8"), ("control.while", "numeric.i64")


def _render_trit_match(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    negative = rng.bounded(-40, -1)
    zero = rng.bounded(0, 20)
    positive = rng.bounded(21, 40)
    selected = rng.choose(("-1", "0", "1"))
    source = (
        "fn classify(value: trit) -> tryte:\n"
        "    match value:\n"
        "        -1:\n"
        f"            return {negative}\n"
        "        0:\n"
        f"            return {zero}\n"
        "        1:\n"
        f"            return {positive}\n\n"
        "fn main() -> tryte:\n"
        f"    return classify({selected})\n"
    )
    return source.encode("utf-8"), (
        "control.match",
        "function.call",
        "numeric.tryte",
    )


def _render_static_array(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    values = [rng.bounded(-8, 8) for _ in range(4)]
    index = rng.bounded(0, 3)
    replacement = rng.bounded(-8, 8)
    rendered_values = ", ".join(str(value) for value in values)
    source = (
        "fn main() -> tryte:\n"
        f"    mut values: tryte[4] = [{rendered_values}]\n"
        f"    values[{index}] = {replacement}\n"
        "    return values[0] + values[1] + values[2] + values[3]\n"
    )
    return source.encode("utf-8"), ("array.static", "numeric.tryte")


def _render_record(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    left = rng.bounded(-20, 20)
    right = rng.bounded(-20, 20)
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n\n"
        "fn make() -> Pair:\n"
        f"    return Pair(left={left}, right={right})\n\n"
        "fn main() -> tryte:\n"
        "    return make().left + make().right\n"
    )
    return source.encode("utf-8"), (
        "aggregate.record",
        "function.call",
        "numeric.tryte",
    )


def _render_enum(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    ok_value = rng.bounded(1, 40)
    error_code = rng.bounded(1, 20)
    flag = rng.choose(("-1", "0", "1"))
    source = (
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte)\n\n"
        "fn parse(flag: trit) -> Result:\n"
        "    match flag:\n"
        "        -1:\n"
        f"            return Result.Err(code={error_code})\n"
        "        0:\n"
        f"            return Result.Ok(value={ok_value})\n"
        "        1:\n"
        f"            return Result.Ok(value={ok_value + 1})\n\n"
        "fn unwrap(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(code):\n"
        "            return 0 - code\n\n"
        "fn main() -> tryte:\n"
        f"    return unwrap(parse({flag}))\n"
    )
    return source.encode("utf-8"), (
        "aggregate.enum",
        "control.match",
        "function.call",
        "numeric.tryte",
    )


def _render_mutable_reference(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    initial = rng.bounded(-20, 20)
    replacement = rng.bounded(-20, 20)
    source = (
        "fn main() -> tryte:\n"
        f"    mut value: tryte = {initial}\n"
        "    ref: &mut tryte = &mut value\n"
        f"    *ref = {replacement}\n"
        "    return *ref\n"
    )
    return source.encode("utf-8"), ("numeric.tryte", "reference.mutable")


def _render_f64(rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    left = rng.bounded(1, 9)
    right = rng.bounded(1, 9)
    source = (
        "fn score(left: f64, right: f64) -> f64:\n"
        "    return left * 1.5 + right / 2.0\n\n"
        "fn main() -> trit:\n"
        f"    return score({left}.0, {right}.0) > -100.0\n"
    )
    return source.encode("utf-8"), ("function.call", "numeric.f64")


_VALID_RENDERERS: tuple[tuple[str, Renderer], ...] = (
    ("scalar-call", _render_scalar_call),
    ("i64-loop", _render_i64_loop),
    ("trit-match", _render_trit_match),
    ("static-array", _render_static_array),
    ("record", _render_record),
    ("enum", _render_enum),
    ("mutable-reference", _render_mutable_reference),
    ("f64", _render_f64),
)
VALID_FAMILIES = tuple(name for name, _renderer in _VALID_RENDERERS)


def _malformed_invalid_character(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> trit:\n    return 0\n@\n",
        ("adversarial.lexing",),
    )


def _malformed_missing_colon(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> trit\n    return 0\n",
        ("adversarial.parsing",),
    )


def _malformed_unclosed_expression(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> tryte:\n    return (1 + 2\n",
        ("adversarial.parsing",),
    )


def _malformed_unknown_name(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> tryte:\n    return missing_value\n",
        ("adversarial.semantic",),
    )


def _malformed_trit_range(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> trit:\n    return 2\n",
        ("adversarial.semantic",),
    )


def _malformed_unknown_function(_rng: SplitMix64) -> tuple[bytes, tuple[str, ...]]:
    return (
        b"fn main() -> tryte:\n    return missing_function()\n",
        ("adversarial.semantic", "function.call"),
    )


_MALFORMED_RENDERERS: tuple[tuple[str, Renderer], ...] = (
    ("lex-invalid-character", _malformed_invalid_character),
    ("parse-missing-colon", _malformed_missing_colon),
    ("parse-unclosed-expression", _malformed_unclosed_expression),
    ("semantic-unknown-name", _malformed_unknown_name),
    ("semantic-trit-range", _malformed_trit_range),
    ("semantic-unknown-function", _malformed_unknown_function),
)
MALFORMED_FAMILIES = tuple(name for name, _renderer in _MALFORMED_RENDERERS)


_MUTATIONS = (
    "prefix-invalid-character",
    "append-invalid-character",
    "remove-first-block-colon",
    "replace-first-arrow",
)


def mutate_valid_source(source: bytes, case_seed: int) -> tuple[bytes, str]:
    """Apply one deterministic bounded mutation that forces rejection."""

    rng = SplitMix64(case_seed ^ 0xA0761D6478BD642F)
    mutation = _MUTATIONS[rng.next_u64() % len(_MUTATIONS)]

    if mutation == "prefix-invalid-character":
        mutated = b"@\n" + source
    elif mutation == "append-invalid-character":
        mutated = source + b"\n@\n"
    elif mutation == "remove-first-block-colon":
        marker = b":\n"
        position = source.find(marker)
        if position < 0:
            raise AssertionError("valid generator source has no block colon")
        mutated = source[:position] + b"\n" + source[position + len(marker) :]
    else:
        marker = b" -> "
        position = source.find(marker)
        if position < 0:
            raise AssertionError("valid generator source has no function arrow")
        mutated = source[:position] + b" => " + source[position + len(marker) :]

    if len(mutated) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("mutated source exceeds frozen source_max_bytes")
    return mutated, mutation


def _render_valid(case_index: int, case_seed: int) -> tuple[str, bytes, tuple[str, ...]]:
    family, renderer = _VALID_RENDERERS[case_index % len(_VALID_RENDERERS)]
    source, features = renderer(SplitMix64(case_seed))
    return family, source, tuple(sorted(set(features)))


def _render_malformed(
    case_index: int,
    case_seed: int,
) -> tuple[str, bytes, tuple[str, ...]]:
    family, renderer = _MALFORMED_RENDERERS[
        case_index % len(_MALFORMED_RENDERERS)
    ]
    source, features = renderer(SplitMix64(case_seed))
    return family, source, tuple(sorted(set(features)))


def generate_case(
    campaign_id: str,
    campaign_seed: int,
    case_index: int,
    case_kind: str,
) -> GeneratedCase:
    if not campaign_id or any(
        ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for ch in campaign_id
    ):
        raise ValueError("campaign_id must match the R0 portable identifier contract")
    if case_kind not in CASE_KINDS:
        raise ValueError(f"unsupported case_kind: {case_kind}")
    if isinstance(case_index, bool) or not isinstance(case_index, int) or case_index < 0:
        raise ValueError("case_index must be a non-negative integer")

    case_seed = derive_case_seed(
        campaign_seed,
        case_index,
        GENERATOR_VERSION,
        case_kind,
    )
    mutation: str | None = None

    if case_kind == "valid":
        family, source, features = _render_valid(case_index, case_seed)
        expected_behavior = EXPECTED_SUCCESS
    elif case_kind == "malformed":
        family, source, features = _render_malformed(case_index, case_seed)
        expected_behavior = EXPECTED_REJECTION
    else:
        origin_family, valid_source, origin_features = _render_valid(
            case_index,
            case_seed,
        )
        source, mutation = mutate_valid_source(valid_source, case_seed)
        family = f"{origin_family}:{mutation}"
        features = tuple(
            sorted(set(origin_features) | {"adversarial.mutation", f"mutation.{mutation}"})
        )
        expected_behavior = EXPECTED_REJECTION

    if len(source) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("generated source exceeds frozen source_max_bytes")
    source_sha = sha256_hex(source)
    case_id = make_case_id(
        campaign_id,
        case_index,
        case_seed,
        GENERATOR_VERSION,
        case_kind,
        source_sha,
    )
    return GeneratedCase(
        campaign_id=campaign_id,
        case_index=case_index,
        case_seed=case_seed,
        case_id=case_id,
        case_kind=case_kind,
        family=family,
        generator_version=GENERATOR_VERSION,
        source=source,
        source_sha256=source_sha,
        source_bytes=len(source),
        expected_behavior=expected_behavior,
        features=features,
        mutation=mutation,
    )


def generate_cases(
    campaign_id: str,
    campaign_seed: int,
    case_kind: str,
    count: int,
    *,
    start_index: int = 0,
) -> tuple[GeneratedCase, ...]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if count > DEFAULT_RESOURCE_POLICY.campaign_max_cases:
        raise ValueError("count exceeds frozen campaign_max_cases")
    if (
        isinstance(start_index, bool)
        or not isinstance(start_index, int)
        or start_index < 0
    ):
        raise ValueError("start_index must be a non-negative integer")
    return tuple(
        generate_case(campaign_id, campaign_seed, start_index + offset, case_kind)
        for offset in range(count)
    )


def coverage_summary(cases: Iterable[GeneratedCase]) -> dict[str, object]:
    materialized = tuple(cases)
    kinds = Counter(case.case_kind for case in materialized)
    families = Counter(case.family for case in materialized)
    features = Counter(feature for case in materialized for feature in case.features)
    return {
        "total": len(materialized),
        "kinds": {key: kinds[key] for key in sorted(kinds)},
        "families": {key: families[key] for key in sorted(families)},
        "features": {key: features[key] for key in sorted(features)},
    }


def valid_coverage_gaps(cases: Iterable[GeneratedCase]) -> tuple[str, ...]:
    observed = {
        feature
        for case in cases
        if case.case_kind == "valid"
        for feature in case.features
    }
    return tuple(sorted(REQUIRED_VALID_FEATURES - observed))


def generator_manifest() -> dict[str, object]:
    return {
        "protocol": GENERATOR_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "prng": "splitmix64-v1",
        "case_kinds": list(CASE_KINDS),
        "valid_families": list(VALID_FAMILIES),
        "malformed_families": list(MALFORMED_FAMILIES),
        "mutations": list(_MUTATIONS),
        "required_valid_features": sorted(REQUIRED_VALID_FEATURES),
        "source_max_bytes": DEFAULT_RESOURCE_POLICY.source_max_bytes,
        "multi_source_modules": "deferred-source-bundle-transport",
    }
