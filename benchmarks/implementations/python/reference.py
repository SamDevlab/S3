"""Reference implementations for portable and S3-specific benchmark cases."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from bootstrap.s3.assembly_frontend_candidate import analyze_bounded_assembly
from bootstrap.s3.assembly_parser_kernel import parse_all_events
from bootstrap.s3.assembly_tokenizer import next_assembly_token
from bootstrap.s3.bounded_text import TextCursor, encode_ascii
from bootstrap.s3.pipeline import compile_source

ASSEMBLY_ROOT = REPOSITORY_ROOT / "benchmarks" / "workloads" / "assembly"


def scalar_accumulate() -> int:
    a = 10
    b = 20
    return a + b + 12


def branch_state_machine() -> int:
    def check(value: int) -> int:
        if value < 0:
            return 10
        if value == 0:
            return 20
        return 30

    return 1 if check(1) + check(5) == 60 else 0


def call_chain() -> int:
    def a() -> int:
        return 1

    def b() -> int:
        return a() + 1

    def c() -> int:
        return b() + 1

    def d() -> int:
        return c() + 1

    def e() -> int:
        return d() + 1

    return e() + e()


def bounded_recursion(value: int = 10) -> int:
    if value <= 1:
        return value
    return bounded_recursion(value - 1) + bounded_recursion(value - 2)


def array_sum() -> int:
    values = [10, 20, 30]
    return sum(values)


def array_copy() -> int:
    source = [1, 2, 3, 4, 5]
    copied = list(source)
    return sum(copied)


def bounded_text_scan() -> int:
    value = b"identifier_0123456789"
    accepted = sum(
        1 for unit in value
        if 48 <= unit <= 57 or 65 <= unit <= 90 or 97 <= unit <= 122 or unit == 95
    )
    return accepted


def tokenizer_valid() -> int:
    text = _assembly_text("valid-multi-result.s3asm")
    cursor = TextCursor(0)
    token_count = 0
    while True:
        result = next_assembly_token(text, cursor)
        if result.variant == "error":
            raise RuntimeError(f"tokenizer error: {result.error}")
        if result.variant == "end":
            return text.length if token_count else -1
        token_count += 1
        assert result.token is not None
        cursor = result.token.next_cursor


def parser_valid() -> int:
    text = _assembly_text("valid-multi-result.s3asm")
    result = parse_all_events(text)
    if result.variant != "end":
        raise RuntimeError(f"parser error: {result.error}")
    return text.length


def parser_invalid() -> int:
    result = parse_all_events(_assembly_text("invalid-version.s3asm"))
    if result.variant != "error" or result.error is None:
        raise RuntimeError("invalid parser input was accepted")
    return int(result.error.code)


def frontend_valid() -> int:
    result = analyze_bounded_assembly(_assembly_text("valid-multi-result.s3asm"))
    if result.variant != "summary" or result.summary is None:
        raise RuntimeError(f"frontend error: {result.error}")
    summary = result.summary
    return (
        summary.version + summary.function_count + summary.declaration_count
        + summary.block_count + summary.call_count + summary.return_count
        + summary.max_result_width + int(summary.ended)
    )


def frontend_invalid() -> int:
    result = analyze_bounded_assembly(_assembly_text("invalid-version.s3asm"))
    if result.variant != "error" or result.error is None:
        raise RuntimeError("invalid frontend input was accepted")
    return int(result.error.code)


def compiler_pipeline() -> int:
    source = (REPOSITORY_ROOT / "benchmarks" / "workloads" / "optimizer_stress.s3").read_text(encoding="utf-8")
    compilation = compile_source(source, "O1")
    return 0 if compilation.assembly.functions else -1


def _assembly_text(name: str):
    encoded = encode_ascii((ASSEMBLY_ROOT / name).read_text(encoding="utf-8"))
    if encoded.error is not None or encoded.text is None:
        raise RuntimeError(f"bounded input encoding failed: {encoded.error}")
    return encoded.text


WORKLOADS = {
    "runtime.scalar.accumulate.v1": scalar_accumulate,
    "runtime.scalar.branch.v1": branch_state_machine,
    "runtime.call.chain.v1": call_chain,
    "runtime.recursion.bounded.v1": bounded_recursion,
    "runtime.array.sum.tryte.v1": array_sum,
    "runtime.array.copy.tryte.v1": array_copy,
    "runtime.text.scan.v1": bounded_text_scan,
    "frontend.tokenizer.valid.v1": tokenizer_valid,
    "frontend.parser.valid.v1": parser_valid,
    "frontend.parser.invalid.v1": parser_invalid,
    "frontend.candidate.valid.v1": frontend_valid,
    "frontend.candidate.invalid.v1": frontend_invalid,
    "compiler.end_to_end.v1": compiler_pipeline,
}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in WORKLOADS:
        print("usage: reference.py <benchmark-id> <loops>", file=sys.stderr)
        return 2
    loops = int(argv[2])
    if loops <= 0:
        print("loops must be positive", file=sys.stderr)
        return 2
    checksum = 0
    workload = WORKLOADS[argv[1]]
    for _ in range(loops):
        checksum = workload()
    print(f"checksum={checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
