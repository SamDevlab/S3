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
