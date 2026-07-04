"""Mathematical reference model for balanced trits and six-trit trytes."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
)

TRIT_MIN = -1
TRIT_MAX = 1
TRYTE_TRITS = 6
TRYTE_MIN = -364
TRYTE_MAX = 364


class TernaryRangeError(ValueError):
    """Raised when a value cannot be represented by the requested width."""

    diagnostic_category = DiagnosticCategory.OVERFLOW
    diagnostic_code = DiagnosticCode.TERNARY_RANGE
    diagnostic_phase = DiagnosticPhase.VERIFICATION

    def __init__(
        self,
        message: str,
        *,
        value: int | None = None,
        lower_bound: int | None = None,
        upper_bound: int | None = None,
    ) -> None:
        self.value = value
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.diagnostic_context = {
            "value": value,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
        }
        super().__init__(message)


class TernaryWidth(Enum):
    TRIT = "trit"
    TRYTE = "tryte"

    @property
    def trit_count(self) -> int:
        return 1 if self is TernaryWidth.TRIT else TRYTE_TRITS

    @property
    def minimum(self) -> int:
        return TRIT_MIN if self is TernaryWidth.TRIT else TRYTE_MIN

    @property
    def maximum(self) -> int:
        return TRIT_MAX if self is TernaryWidth.TRIT else TRYTE_MAX


def validate_trit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TernaryRangeError(f"trit must be an integer, got {value!r}")
    if not TRIT_MIN <= value <= TRIT_MAX:
        raise TernaryRangeError(
            f"trit value {value} is outside [{TRIT_MIN}, {TRIT_MAX}]",
            value=value,
            lower_bound=TRIT_MIN,
            upper_bound=TRIT_MAX,
        )
    return value


def validate_tryte(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TernaryRangeError(f"tryte must be an integer, got {value!r}")
    if not TRYTE_MIN <= value <= TRYTE_MAX:
        raise TernaryRangeError(
            f"tryte value {value} is outside [{TRYTE_MIN}, {TRYTE_MAX}]",
            value=value,
            lower_bound=TRYTE_MIN,
            upper_bound=TRYTE_MAX,
        )
    return value


def validate(value: int, width: TernaryWidth) -> int:
    return validate_trit(value) if width is TernaryWidth.TRIT else validate_tryte(value)


def decimal_to_trits(value: int) -> tuple[int, ...]:
    """Convert a tryte value to six least-significant-trit-first digits."""

    validate_tryte(value)
    remaining = value
    digits: list[int] = []
    for _ in range(TRYTE_TRITS):
        remaining, remainder = divmod(remaining, 3)
        if remainder == 2:
            remainder = -1
            remaining += 1
        digits.append(remainder)
    if remaining != 0:  # Defensive; validate_tryte should make this impossible.
        raise TernaryRangeError(f"value {value} needs more than six trits")
    return tuple(digits)


def trits_to_decimal(trits: Iterable[int]) -> int:
    """Convert exactly six least-significant-trit-first digits to a tryte."""

    digits = tuple(trits)
    if len(digits) != TRYTE_TRITS:
        raise TernaryRangeError(
            f"a tryte requires exactly {TRYTE_TRITS} trits, got {len(digits)}"
        )
    total = 0
    power = 1
    for digit in digits:
        validate_trit(digit)
        total += digit * power
        power *= 3
    return validate_tryte(total)


def _to_width_trits(value: int, width: TernaryWidth) -> tuple[int, ...]:
    validate(value, width)
    if width is TernaryWidth.TRIT:
        return (value,)
    return decimal_to_trits(value)


def _from_width_trits(trits: tuple[int, ...], width: TernaryWidth) -> int:
    if width is TernaryWidth.TRIT:
        if len(trits) != 1:
            raise TernaryRangeError("a trit requires exactly one digit")
        return validate_trit(trits[0])
    return trits_to_decimal(trits)


def invert(value: int, width: TernaryWidth) -> int:
    validate(value, width)
    return validate(-value, width)


def add(left: int, right: int, width: TernaryWidth) -> int:
    validate(left, width)
    validate(right, width)
    result = left + right
    try:
        return validate(result, width)
    except TernaryRangeError as error:
        raise TernaryRangeError(
            f"{width.value} overflow: {left} + {right} = {result}",
            value=result,
            lower_bound=width.minimum,
            upper_bound=width.maximum,
        ) from error


def tritwise_min(left: int, right: int, width: TernaryWidth) -> int:
    left_digits = _to_width_trits(left, width)
    right_digits = _to_width_trits(right, width)
    result = tuple(min(a, b) for a, b in zip(left_digits, right_digits, strict=True))
    return _from_width_trits(result, width)


def tritwise_max(left: int, right: int, width: TernaryWidth) -> int:
    left_digits = _to_width_trits(left, width)
    right_digits = _to_width_trits(right, width)
    result = tuple(max(a, b) for a, b in zip(left_digits, right_digits, strict=True))
    return _from_width_trits(result, width)


def compare(left: int, right: int, width: TernaryWidth) -> int:
    validate(left, width)
    validate(right, width)
    return (left > right) - (left < right)


def invert_trit(value: int) -> int:
    return invert(value, TernaryWidth.TRIT)


def invert_tryte(value: int) -> int:
    return invert(value, TernaryWidth.TRYTE)


def add_trit(left: int, right: int) -> int:
    return add(left, right, TernaryWidth.TRIT)


def add_tryte(left: int, right: int) -> int:
    return add(left, right, TernaryWidth.TRYTE)


def min_trit(left: int, right: int) -> int:
    return tritwise_min(left, right, TernaryWidth.TRIT)


def min_tryte(left: int, right: int) -> int:
    return tritwise_min(left, right, TernaryWidth.TRYTE)


def max_trit(left: int, right: int) -> int:
    return tritwise_max(left, right, TernaryWidth.TRIT)


def max_tryte(left: int, right: int) -> int:
    return tritwise_max(left, right, TernaryWidth.TRYTE)


def compare_trit(left: int, right: int) -> int:
    return compare(left, right, TernaryWidth.TRIT)


def compare_tryte(left: int, right: int) -> int:
    return compare(left, right, TernaryWidth.TRYTE)
