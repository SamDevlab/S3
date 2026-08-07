from __future__ import annotations

import pytest

import bootstrap.s3.pipeline as pipeline
from bootstrap.s3 import CompilationCache
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode


SOURCE = "fn main() -> tryte:\n    return 6\n"


def test_cache_reuses_identical_compilation(monkeypatch) -> None:
    calls = 0
    original = pipeline._compile_source_with_context

    def compile_once(source, context):
        nonlocal calls
        calls += 1
        return original(source, context)

    monkeypatch.setattr(pipeline, "_compile_source_with_context", compile_once)
    cache = CompilationCache()

    first = cache.compile(SOURCE)
    second = cache.compile(SOURCE)

    assert first is second
    assert calls == 1
    assert cache.info() == pipeline.CompilationCacheInfo(1, 1, 128, 1)


def test_cache_key_separates_source_optimization_and_syntax() -> None:
    cache = CompilationCache()

    default = cache.compile(SOURCE)
    o1 = cache.compile(SOURCE, "O1")
    other_source = cache.compile("fn main() -> tryte:\n    return 5\n")
    legacy = cache.compile(
        "fn main() -> tryte {\n    return 6;\n}\n",
        mode=SyntaxMode.V0_5,
    )

    assert len({id(default), id(o1), id(other_source), id(legacy)}) == 4
    assert cache.info().current_entries == 4
    assert cache.info().misses == 4


def test_cache_uses_lru_eviction(monkeypatch) -> None:
    calls = 0
    original = pipeline._compile_source_with_context

    def count_compilations(source, context):
        nonlocal calls
        calls += 1
        return original(source, context)

    monkeypatch.setattr(pipeline, "_compile_source_with_context", count_compilations)
    cache = CompilationCache(max_entries=2)
    first = SOURCE
    second = "fn main() -> tryte:\n    return 5\n"
    third = "fn main() -> tryte:\n    return 4\n"

    cache.compile(first)
    cache.compile(second)
    cache.compile(first)
    cache.compile(third)
    cache.compile(second)

    assert calls == 4
    assert cache.info() == pipeline.CompilationCacheInfo(1, 4, 2, 2)


def test_failed_compilation_is_not_cached(monkeypatch) -> None:
    calls = 0
    original = pipeline._compile_source_with_context

    def count_failures(source, context):
        nonlocal calls
        calls += 1
        return original(source, context)

    monkeypatch.setattr(pipeline, "_compile_source_with_context", count_failures)
    cache = CompilationCache()

    for _ in range(2):
        with pytest.raises(ParseError):
            cache.compile("fn main() -> tryte:\n    return\n")

    assert calls == 2
    assert cache.info() == pipeline.CompilationCacheInfo(0, 2, 128, 0)


def test_clear_removes_entries_and_resets_counters() -> None:
    cache = CompilationCache(max_entries=1)
    cache.compile(SOURCE)
    cache.compile(SOURCE)

    cache.clear()

    assert cache.info() == pipeline.CompilationCacheInfo(0, 0, 1, 0)


@pytest.mark.parametrize("value", [0, -1])
def test_cache_requires_positive_capacity(value) -> None:
    with pytest.raises(ValueError, match="max_entries must be positive"):
        CompilationCache(value)


@pytest.mark.parametrize("value", [True, 1.5, "2"])
def test_cache_requires_integer_capacity(value) -> None:
    with pytest.raises(TypeError, match="max_entries must be an integer"):
        CompilationCache(value)  # type: ignore[arg-type]


def test_regular_compile_source_remains_uncached(monkeypatch) -> None:
    calls = 0
    original = pipeline._compile_source_with_context

    def count_compilations(source, context):
        nonlocal calls
        calls += 1
        return original(source, context)

    monkeypatch.setattr(pipeline, "_compile_source_with_context", count_compilations)

    first = pipeline.compile_source(SOURCE)
    second = pipeline.compile_source(SOURCE)

    assert first is not second
    assert calls == 2
