"""Public numeric emulator facade for the M1.32 typed IR boundary."""

from __future__ import annotations

from .numeric import NumericValue
from .numeric_ir import NumericIRFunction, evaluate_numeric_ir


class NumericEmulator:
    """Execute the supported numeric IR using the canonical evaluator."""

    def execute(self, function: NumericIRFunction) -> NumericValue:
        return evaluate_numeric_ir(function)

