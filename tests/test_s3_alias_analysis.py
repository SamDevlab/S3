from __future__ import annotations

from bootstrap.s3.alias_analysis import AliasAnalysis, AliasResult


def test_alias_analysis_queries() -> None:
    # Distinct memory objects -> NoAlias
    assert AliasAnalysis.alias(0, 1) == AliasResult.NO_ALIAS
    assert not AliasAnalysis.may_alias(0, 1)
    assert not AliasAnalysis.must_alias(0, 1)

    # Identical memory objects -> MustAlias
    assert AliasAnalysis.alias(0, 0) == AliasResult.MUST_ALIAS
    assert AliasAnalysis.may_alias(0, 0)
    assert AliasAnalysis.must_alias(0, 0)

    # Unknown memory indices -> MayAlias
    assert AliasAnalysis.alias(None, 0) == AliasResult.MAY_ALIAS
    assert AliasAnalysis.may_alias(None, 0)
    assert not AliasAnalysis.must_alias(None, 0)


def test_alias_analysis_cell_queries() -> None:
    assert AliasAnalysis.alias_cell(0, 0, 1, 0) == AliasResult.NO_ALIAS
    assert AliasAnalysis.alias_cell(0, 0, 0, 0) == AliasResult.MUST_ALIAS
    assert AliasAnalysis.alias_cell(0, 0, 0, 1) == AliasResult.NO_ALIAS
    assert AliasAnalysis.alias_cell(0, "i_v0", 0, "i_v0") == AliasResult.MUST_ALIAS
    assert AliasAnalysis.alias_cell(0, "i_v0", 0, "i_v1") == AliasResult.MAY_ALIAS
    assert AliasAnalysis.alias_cell(0, None, 0, 0) == AliasResult.MAY_ALIAS
    assert AliasAnalysis.alias_cell(None, 0, 0, 0) == AliasResult.MAY_ALIAS
