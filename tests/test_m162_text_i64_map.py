from __future__ import annotations

import platform
import re

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.backends.x86_64 import NativeToolchain
from bootstrap.s3.dynamic import (
    BufferFullError,
    DynamicText,
    DynamicTextMap,
)


@pytest.fixture(scope="module")
def native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("text map native proof requires Linux x86-64")
    return NativeToolchain.detect()


def test_text_map_compares_utf8_bytes_and_preserves_owned_key() -> None:
    values = DynamicTextMap(2)
    key = DynamicText("café", capacity=32)
    values.put(key, 41)
    key.append_static("-changed")

    lookup = DynamicText.from_static("café")
    assert values.contains(lookup) == -1
    assert values.get(lookup) == 41
    assert values.key_at(0).to_string() == "café"


def test_text_map_is_ordered_bounded_and_clones_independently() -> None:
    values = DynamicTextMap(1)
    values.put(DynamicText.from_static("first"), 7)
    clone = values.clone()
    clone.put(DynamicText.from_static("first"), 9)
    assert values.value_at(0) == 7
    assert clone.value_at(0) == 9
    with pytest.raises(BufferFullError):
        values.put(DynamicText.from_static("second"), 8)


def test_generic_text_map_round_trips_through_hosted_ir() -> None:
    source = """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(2)
    key: text = text_from_static("alpha")
    discard map_put<text, i64>(&mut values, &key, 73)
    return map_get<text, i64>(&values, &key)
"""
    compilation = compile_source(source)
    assert run_source(source, optimization="O0") == 73
    assert run_source(source, optimization="O1") == 73
    native = X8664Backend().generate(compilation.assembly)
    assert "__s3_builtin_text_i64_map_new" in native
    assert "__s3_builtin_text_i64_map_put" in native
    assert "__s3_builtin_text_i64_map_get" in native


def test_generic_text_map_runs_on_linux_x86_64(
    native_toolchain: NativeToolchain, tmp_path
) -> None:
    source = """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(2)
    key: text = text_from_static("alpha")
    discard map_put<text, i64>(&mut values, &key, 91)
    return map_get<text, i64>(&values, &key)
"""
    assembly = X8664Backend().generate(compile_source(source).assembly)
    executable = native_toolchain.build(assembly, tmp_path / "text-map")
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert re.fullmatch(r"program returned: 91\n", completed.stdout)


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        (
            "equal-utf8-bytes",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(2)
    first: text = text_from_static("café")
    second: text = text_from_static("café")
    discard map_put<text, i64>(&mut values, &first, 17)
    return map_get<text, i64>(&values, &second)
""",
            17,
        ),
        (
            "replace-preserves-order",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(3)
    alpha: text = text_from_static("alpha")
    beta: text = text_from_static("beta")
    discard map_put<text, i64>(&mut values, &alpha, 1)
    discard map_put<text, i64>(&mut values, &beta, 2)
    discard map_put<text, i64>(&mut values, &alpha, 9)
    return map_value_at<text, i64>(&values, 0) * 10 + map_value_at<text, i64>(&values, 1)
""",
            92,
        ),
        (
            "remove-compacts",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(3)
    alpha: text = text_from_static("alpha")
    beta: text = text_from_static("beta")
    discard map_put<text, i64>(&mut values, &alpha, 1)
    discard map_put<text, i64>(&mut values, &beta, 2)
    discard map_remove<text, i64>(&mut values, &alpha)
    return map_len<text, i64>(&values) * 10 + map_get<text, i64>(&values, &beta)
""",
            12,
        ),
        (
            "clone-is-independent",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(2)
    alpha: text = text_from_static("alpha")
    discard map_put<text, i64>(&mut values, &alpha, 7)
    mut copy: map<text, i64> = map_clone<text, i64>(&values)
    discard map_put<text, i64>(&mut copy, &alpha, 9)
    return map_get<text, i64>(&values, &alpha) * 10 + map_get<text, i64>(&copy, &alpha)
""",
            79,
        ),
        (
            "contains-distinguishes-missing",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(2)
    alpha: text = text_from_static("alpha")
    beta: text = text_from_static("beta")
    discard map_put<text, i64>(&mut values, &alpha, 7)
    return to_i64(map_contains<text, i64>(&values, &beta))
""",
            0,
        ),
        (
            "reserve-and-capacity",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(1)
    discard map_reserve<text, i64>(&mut values, 2)
    return map_capacity<text, i64>(&values) * 10 + map_len<text, i64>(&values)
""",
            20,
        ),
        (
            "key-at-returns-owned-text",
            """\
fn main() -> i64:
    mut values: map<text, i64> = map_new<text, i64>(1)
    key: text = text_from_static("alpha")
    discard map_put<text, i64>(&mut values, &key, 7)
    stored: text = map_key_at<text, i64>(&values, 0)
    return text_len(&stored)
""",
            5,
        ),
    ],
)
def test_text_map_native_matrix(
    native_toolchain: NativeToolchain,
    tmp_path,
    name: str,
    source: str,
    expected: int,
) -> None:
    assert run_source(source, optimization="O0") == expected
    assert run_source(source, optimization="O1") == expected
    assembly = X8664Backend().generate(compile_source(source).assembly)
    executable = native_toolchain.build(assembly, tmp_path / name)
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n"
