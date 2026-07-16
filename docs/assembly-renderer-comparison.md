# Assembly Renderer Comparison Harness

## Purpose

This harness stabilizes the future comparison interface between the Python
Assembly renderer and a later S3 Assembly renderer.

The command exists now so tests can validate the blocked state deterministically
before the S3 renderer exists.

## Current status

The Python renderer remains the reference implementation. A compilable S3 stub
now exists, but the S3 renderer implementation is not available.

String literals are available only as front-end expressions. Runtime string
support is not implemented, so the renderer comparison remains blocked.

S3 0.10 closed with the candidate contracts and readiness gate in place. S3
0.11 is closed after establishing deterministic static text helpers. S3 0.12
opens practical actual-output work, starting with the `first` fixture; see
`docs/roadmap-0.10.md`, `docs/roadmap-0.11.md`, and `docs/roadmap-0.12.md`.

`python tools/compare_assembly_renderer.py --status` reports the current state
and exits successfully.

`python tools/compare_assembly_renderer.py --reference` validates the
Python/reference side of the comparison and exits successfully when the subset
manifest, AssemblyProgram contract, fixtures, and Assembly goldens are present.
The Assembly goldens must be non-empty and end with a final newline.

`python tools/compare_assembly_renderer.py --candidate` validates the S3
candidate manifest and confirms that the compilable candidate is still an
explicit stub. The candidate exists and compiles, but it does not implement
Assembly rendering. Its minimal API is `renderer_candidate_status() -> trit`,
where `-1` means stub.

`python tools/compare_assembly_renderer.py --candidate-symbols` prints the
deterministic directive/opcode symbol table for the candidate. The table is
derived from the candidate manifest and validated against the subset manifest,
including counts and scalar ID ranges. This prepares future dispatch work; it
does not mean the S3 renderer is implemented.

`python tools/check_assembly_renderer_candidate_symbols.py` checks the canonical
golden for that export at
`tests/golden/assembly_renderer_candidate_symbols.txt`. This locks the symbol
table text against accidental drift; it does not make the S3 renderer
implemented.

`tests/golden/assembly_renderer_candidate_fixtures.json` records the current
reference fixtures for a future renderer comparison. Check it with
`python tools/check_assembly_renderer_candidate_fixtures.py` and list it with
`python tools/compare_assembly_renderer.py --candidate-fixtures`. The contract
uses existing Assembly goldens as future byte-for-byte targets and excludes the
candidate stub itself; it does not mean the renderer is implemented.

`tests/golden/assembly_renderer_candidate_fixture_expectations.json` records the
expected Assembly output metadata for each candidate fixture. Check it with
`python tools/check_assembly_renderer_candidate_fixture_expectations.py` and
list it with
`python tools/compare_assembly_renderer.py --candidate-fixture-expectations`.
Each expectation locks the expected Assembly golden path, SHA-256, byte count,
and line count. This prepares a future byte-for-byte comparison; it does not
mean the renderer is implemented.

`tests/golden/assembly_renderer_candidate_comparison_plan.json` records the
future per-fixture comparison plan. Check it with
`python tools/check_assembly_renderer_candidate_comparison_plan.py` and list it
with `python tools/compare_assembly_renderer.py --candidate-comparison-plan`.
The plan links each fixture to its expected Assembly output while keeping the
candidate actual output status at `not_implemented`. This prepares a future
byte-for-byte comparison; it does not mean the renderer is implemented.

`tests/golden/assembly_renderer_candidate_actual_outputs.json` records the
blocked actual-output contract for the same fixture order. Check it with
`python tools/check_assembly_renderer_candidate_actual_outputs.py` and list it
with `python tools/compare_assembly_renderer.py --candidate-actual-outputs`.
The contract defines one `planned_actual_output` path per fixture under
`tests/golden/assembly_renderer_candidate_actual`, but requires those files to
be absent while the S3 renderer is unavailable. This reserves the future output
location; it does not mean the renderer is implemented, and `--check` remains
blocked.

S3 0.12 starts the work of turning the first planned actual output into real
deterministic output. The starting point is the `first` fixture.

0.12-A adds an in-memory probe for `first` that builds the expected Assembly
text with `StaticTextLineEmitter` and compares it byte-for-byte against the
LF-normalized inspect golden. This proves the deterministic text path for one
fixture, but it does not create a versioned actual output, change the
actual-output contracts, or implement the S3 renderer.

`python tools/check_assembly_renderer_candidate_readiness.py` is the single
readiness gate for the candidate stub. It validates the candidate manifest, the
symbol export golden, the fixture contract, the fixture expectations, the
comparison plan, the actual-output contract, the hosted
`s3_program_check.py check` opt-in, the
`--candidate`, `--candidate-symbols`, `--candidate-fixtures`,
`--candidate-fixture-expectations`, `--candidate-comparison-plan`, and
`--candidate-actual-outputs`, and `--candidate-run` modes, and the expected
blocked result from `--check`. This gate keeps the candidate consistent; it
does not implement rendering.

`python tools/compare_assembly_renderer.py --candidate-run` executes the
candidate stub through the hosted path and expects `main` to return `-1`. This
uses the same registered stub entry as `tools/s3_program_check.py check`, so the
candidate run and program inventory stay aligned. This only validates the status
API; it does not render Assembly.

The candidate stub is also covered by `tools/golden_inspect.py check`. Those
goldens lock the current compiler-facing IR and Assembly output for the stub;
they do not mean the S3 renderer is implemented.

The stub exposes scalar capability functions for the current subset contract:
`renderer_supported_directive_count()` returns the number of supported
directives, and `renderer_supported_opcode_count()` returns the number of
supported opcodes. These values are checked against the subset manifest; they do
not render Assembly.

The stub also exposes one scalar ID function per supported directive and opcode.
Those IDs follow the subset manifest order and are checked as constants only;
they do not render Assembly.

The candidate declares scalar ID ranges for directives and opcodes. It also
exposes scalar support predicates for directive and opcode IDs. These APIs only
describe the current supported ID space; they do not render Assembly.

The candidate also has a hosted capability smoke function:
`renderer_candidate_capability_smoke()`. It reaches scalar count and selected ID
functions, ranges, and support predicates, then returns `-1` when those
assertions match the subset contract. This keeps the candidate status aligned
with the stub meaning; it does not implement Assembly rendering.

`python tools/compare_assembly_renderer.py --check` fails intentionally while
the S3 renderer is unavailable.

## Why check fails today

Failure is correct today because real comparison is still blocked by:

- string runtime support;
- records/structs or an equivalent representation;
- enums/sum types or safe tags;
- deterministic formatting helpers.

Returning success before a real S3 renderer exists would create a false-positive
comparison result.

## Future behavior

When the S3 renderer exists, `--check` should:

- generate Python reference output;
- generate S3 renderer output;
- compare the two outputs byte-for-byte;
- print a deterministic diff when output diverges;
- return 0 only when the outputs are identical.

## Scope

This harness does not implement the S3 renderer.

It does not alter the Python renderer.

It does not alter the Assembly format.

It does not alter CI.
