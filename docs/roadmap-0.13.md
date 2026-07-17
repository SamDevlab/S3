# S3 0.13 Roadmap

Status: open

## Objective

Advance from the passed `first` fixture to `simple_call`, starting practical
coverage for Assembly output with function and call structure.

S3 0.13 should remain implementation-focused. It should answer how the project
moves from an isolated static output to the next real fixture without migrating
the whole compiler to S3 or implementing the complete renderer at once.

## Principles

- Each PR should move `simple_call` closer to real actual output.
- Do not migrate the full compiler to S3.
- Do not implement the complete renderer in one step.
- Use the `first` path as the minimum pattern.
- Preserve `first` as available and passed.
- Keep `sign` blocked until `simple_call` is stable.
- Keep `python tools/compare_assembly_renderer.py --check` blocked while the
  required fixture coverage is incomplete.
- Avoid isolated new contracts without real output work.
- Preserve deterministic LF, byte count, line count, and SHA-256 metadata.

## Proposed 0.13 sequence

### 0.13-A: simple_call output investigation and in-memory probe

Status: complete

Objective:

Investigate `examples/simple_call.s3` and
`tests/golden/inspect/simple_call.assembly.txt`, then add an in-memory probe for
the expected `simple_call` output using the existing deterministic text
infrastructure.

Acceptance:

- no versioned actual output is created yet;
- the in-memory probe compares against the LF-normalized golden;
- `simple_call` remains `not_implemented` in the actual-output contract;
- `--check` remains blocked.

Notes:

0.13-A adds an in-memory `simple_call` fixture probe using the deterministic
static text path. It validates LF-normalized bytes, line count, byte count, and
SHA-256 against the inspect golden without creating a versioned actual output
or changing the actual-output contracts. This prepares 0.13-B to create the
real candidate actual output.

### 0.13-B: simple_call actual output

Status: complete

Objective:

Create the versioned candidate actual output for `simple_call`, if 0.13-A
confirms the path.

Acceptance:

- `simple_call` advances to available;
- `first` remains passed;
- `sign` remains blocked and `not_implemented`;
- `--check` remains blocked.

Notes:

0.13-B creates
`tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt` from
`build_simple_call_fixture_assembly_text()`. The actual-output contract now
marks `simple_call` as available with `comparison_status: pending`; `first`
remains passed, `sign` remains blocked and absent, and `--check` remains
blocked. 0.13-C should formalize the byte-for-byte `simple_call` comparison.

### 0.13-C: simple_call byte-for-byte comparison

Objective:

Formalize byte-for-byte comparison for `simple_call`.

Acceptance:

- `simple_call` advances to `comparison_status: passed`;
- `first` remains passed;
- `sign` remains blocked and `not_implemented`;
- `--candidate-compare-available` covers `first` and `simple_call`;
- `--check` remains blocked if `sign` is still blocked.

0.13 can close after A/B/C if `simple_call` is stable.
