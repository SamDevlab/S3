# Contributing to S3

S3 is an experimental systems-language project. Contributions are welcome when they preserve the project's central rule: **semantic correctness comes before optimization or feature count**.

## Development setup

```bash
python -m venv .venv
```

Activate the environment and install the project in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Run the default suite:

```bash
python -m pytest
```

Also validate repository goldens when your change affects parser output, IR, Assembly or diagnostics:

```bash
python tools/golden_inspect.py check
```

## Before opening a contribution

A change should answer these questions:

1. What semantic contract is being added or changed?
2. Which layer owns that contract: parser, semantic analysis, typed IR, verifier, optimizer, Assembly, emulator or native backend?
3. What evidence proves the same behavior end-to-end?
4. Does the change preserve deterministic serialization/output where required?
5. If this is an optimization, what proves observable equivalence with the unoptimized path?

## Tests

The suite uses explicit categories such as:

```text
s3_fast
s3_contract
s3_differential
s3_native
s3_slow
s3_benchmark
```

Choose tests according to the capability being changed. New language behavior normally requires more than a parser-only test.

Prefer coverage that crosses the relevant path:

```text
source
→ parser
→ semantic analysis
→ typed IR
→ verifier
→ Assembly
→ emulator / native backend
```

## Optimizations

Do not introduce an optimization only because it looks locally valid.

An optimization must preserve the observable semantics of the input program and must continue to pass the verifier and applicable differential tests.

## Native backend

The reference native target is Linux x86-64 / System V AMD64.

Changes to calling convention, register use, memory layout or floating-point lowering should include targeted native tests whenever possible.

## Documentation

Update the appropriate documentation when a change affects:

- public syntax or semantics;
- normative contracts;
- CLI behavior;
- serialization formats;
- Assembly format;
- roadmap/milestone claims;
- architectural decisions.

Use `spec/` for normative language contracts and `docs/decisions/` for architectural decisions that need a durable rationale.

## Scope discipline

S3 deliberately avoids claiming a capability before its end-to-end gate exists.

A partial implementation should be documented as partial/experimental rather than promoted as complete.
