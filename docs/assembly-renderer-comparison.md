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
