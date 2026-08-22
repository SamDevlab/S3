from __future__ import annotations

import pytest

from bootstrap.s3.query_engine import QueryEngine, QueryEngineError, QueryKey


def _key(source: str = "source-a") -> QueryKey:
    return QueryKey(
        source=source,
        module="app",
        dependencies=("dep-a",),
        lock="lock-a",
        target="linux-x86_64",
        backend="assembly",
        optimization="O1",
        compiler="compiler-a",
        config="cfg-a",
        generic_args=("T=i64",),
    )


def test_query_key_is_complete_and_deterministic() -> None:
    assert _key().identity == _key().identity
    assert _key().identity != _key("source-b").identity
    payload = _key().payload
    payload["dependencies"] = ("dep-a",)
    payload["generic_args"] = ("T=i64",)
    assert QueryKey(**payload).identity == _key().identity  # type: ignore[arg-type]


def test_cold_and_incremental_queries_reuse_only_exact_identity() -> None:
    engine = QueryEngine()
    calls: list[str] = []
    cold = engine.query(_key(), lambda: calls.append("cold") or "result")
    warm = engine.query(_key(), lambda: calls.append("warm") or "wrong")
    changed = engine.query(_key("source-b"), lambda: calls.append("changed") or "new")
    assert cold.cache_hit is False
    assert warm.cache_hit is True and warm.value == "result"
    assert changed.cache_hit is False and changed.value == "new"
    assert calls == ["cold", "changed"]


def test_invalidation_is_transitive_and_fail_closed() -> None:
    engine = QueryEngine()
    source = _key()
    engine.query(source, lambda: "source")
    dependent = QueryKey(source="dependent", module="app")
    engine.query(dependent, lambda: "dependent", dependencies=(source.identity,))
    top = QueryKey(source="top", module="app")
    engine.query(top, lambda: "top", dependencies=(dependent.identity,))
    assert engine.invalidate(source.identity) == tuple(sorted((source.identity, dependent.identity, top.identity)))
    assert engine.snapshot()["queries"] == {}
    with pytest.raises(QueryEngineError, match="identity mismatch"):
        QueryEngine.from_snapshot({"format": "s3.query-engine.v1", "queries": {"bad": {"key": dependent.payload, "dependencies": []}}})


def test_query_inputs_and_dependencies_are_canonical() -> None:
    with pytest.raises(QueryEngineError, match="sorted and unique"):
        QueryKey(source="x", module="m", dependencies=("b", "a"))
    with pytest.raises(QueryEngineError, match="sorted and unique"):
        QueryEngine().query(QueryKey(source="x", module="m"), lambda: 1, dependencies=("b", "a"))
