"""Shared helpers for internal SSA optimization passes."""

from __future__ import annotations

from ..ir import IROpcode, IRType
from ..ternary import TernaryWidth

_FOLDABLE_OPCODES = {
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
}

_PURE_REMOVABLE_OPCODES = {
    IROpcode.CONST,
    IROpcode.CONST_STR,
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
    IROpcode.LOAD,
}


def _width(type_name: IRType) -> TernaryWidth:
    return (
        TernaryWidth.TRIT
        if type_name is IRType.TRIT
        else TernaryWidth.TRYTE
    )
