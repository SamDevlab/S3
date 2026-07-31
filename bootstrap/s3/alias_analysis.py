"""Alias Analysis infrastructure for S3 IR memory objects."""

from __future__ import annotations

from enum import Enum
from typing import Optional


CellIndex = int | str | None


class AliasResult(Enum):
    NO_ALIAS = "NoAlias"
    MUST_ALIAS = "MustAlias"
    MAY_ALIAS = "MayAlias"


class AliasAnalysis:
    """Provides memory alias query capabilities for S3 IR optimization passes."""

    @staticmethod
    def alias(mem1: Optional[int], mem2: Optional[int]) -> AliasResult:
        """Determines the alias relationship between two memory object indices."""
        if mem1 is None or mem2 is None:
            return AliasResult.MAY_ALIAS
        if mem1 == mem2:
            return AliasResult.MUST_ALIAS
        return AliasResult.NO_ALIAS

    @classmethod
    def may_alias(cls, mem1: Optional[int], mem2: Optional[int]) -> bool:
        """Returns True if mem1 and mem2 may refer to the same memory location."""
        return cls.alias(mem1, mem2) != AliasResult.NO_ALIAS

    @classmethod
    def must_alias(cls, mem1: Optional[int], mem2: Optional[int]) -> bool:
        """Returns True if mem1 and mem2 definitely refer to the same memory location."""
        return cls.alias(mem1, mem2) == AliasResult.MUST_ALIAS

    @classmethod
    def alias_cell(
        cls,
        mem1: Optional[int],
        index1: CellIndex,
        mem2: Optional[int],
        index2: CellIndex,
    ) -> AliasResult:
        """Determines aliasing between frame-local memory cells.

        Integer indices are proven constants. String indices identify the exact
        SSA value used as an index. Distinct SSA values may still hold the same
        runtime value, so they conservatively MayAlias.
        """
        memory_alias = cls.alias(mem1, mem2)
        if memory_alias is AliasResult.NO_ALIAS:
            return AliasResult.NO_ALIAS
        if memory_alias is AliasResult.MAY_ALIAS:
            return AliasResult.MAY_ALIAS
        if index1 is None or index2 is None:
            return AliasResult.MAY_ALIAS
        if index1 == index2:
            return AliasResult.MUST_ALIAS
        if isinstance(index1, int) and isinstance(index2, int):
            return AliasResult.NO_ALIAS
        return AliasResult.MAY_ALIAS

    @classmethod
    def may_alias_cell(
        cls,
        mem1: Optional[int],
        index1: CellIndex,
        mem2: Optional[int],
        index2: CellIndex,
    ) -> bool:
        """Returns True if two memory cells may refer to the same location."""
        return cls.alias_cell(mem1, index1, mem2, index2) != AliasResult.NO_ALIAS

    @classmethod
    def must_alias_cell(
        cls,
        mem1: Optional[int],
        index1: CellIndex,
        mem2: Optional[int],
        index2: CellIndex,
    ) -> bool:
        """Returns True if two memory cells definitely refer to the same location."""
        return cls.alias_cell(mem1, index1, mem2, index2) == AliasResult.MUST_ALIAS
