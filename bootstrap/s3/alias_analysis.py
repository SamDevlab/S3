"""Alias Analysis infrastructure for S3 IR memory objects."""

from __future__ import annotations

from enum import Enum
from typing import Optional


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
