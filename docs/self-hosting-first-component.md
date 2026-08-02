# First Python-to-S3 Component Candidate

## Decision

The first candidate component for future Python-to-S3 migration should be an
Assembly renderer subset.

This means a small S3 implementation that takes an Assembly-shaped value and
emits deterministic S3 Assembly text for a narrow set of already observed
constructs. It does not include parsing, broad validation, execution, native
code emission, or any replacement of the current Python compiler path.

## Why this component

The Assembly renderer subset is the smallest practical first candidate because:

- it has deterministic text output;
- the Python reference already renders stable S3 Assembly;
- output can be compared byte-for-byte;
- the input shape is smaller than parser, lexer, optimizer, runtime, or native
  code generation inputs;
- it can start with the instructions used by existing stable examples;
- failure modes are mostly formatting drift rather than language semantics
  changes.

Candidate comparison:

| Candidate | Required input | Observable output | S3 dependencies | Difficulty | Risk | Python-vs-S3 comparison | Requires strings | Requires arrays | Requires records | Requires modules | Can start small |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Assembly renderer subset | Assembly-shaped program data | S3 Assembly text | strings, arrays, records, helpers | medium | low-medium | byte-for-byte text diff | yes | yes | yes | later | yes |
| IR normalizer | IR-shaped program data | canonical IR-like data or text | arrays, records, comparison, serialization | medium | medium | structural or text diff | maybe | yes | yes | later | yes |
| Diagnostic formatter | diagnostic record | stable diagnostic text or JSON-like text | strings, records, enums | medium | medium | text diff | yes | maybe | yes | later | yes |
| Small static checker | narrow structured input | pass/fail plus diagnostic | arrays, records, diagnostics | medium | medium | result and diagnostic comparison | maybe | yes | yes | later | yes |

The Assembly renderer subset is preferred because the first useful milestone can
be very narrow and still valuable: render the same textual artifact that the
current Python implementation already emits for selected examples.

## Why not parser/lexer/optimizer/backend first

The full parser should not be first because it depends on a stable token model,
recursive syntax data, structured diagnostics, and broad grammar behavior.
Small differences are hard to classify as formatting drift or semantic change.

The full lexer should not be first because it depends on source text handling,
source spans, lexical diagnostics, and exact edge-case behavior. S3 does not yet
have the text facilities needed for a faithful implementation.

The optimizer should not be first because it changes program structure while
preserving behavior. It requires IR modeling, dataflow, verification, and broad
regression coverage before migration is safe.

The native backend should not be first because it is platform-specific, has a
large observable surface, and depends on layout details outside the early
language feature set.

The full emulator should not be first because it combines runtime state, memory,
frames, control flow, and structured failures.

The complete CLI should not be first because it requires argument handling,
file I/O, diagnostics, and host interaction. It should remain a Python boundary
until component comparison is proven.

## Python reference

The Python reference is `bootstrap/s3/assembly.py`, especially:

- `AssemblyProgram.render`;
- `AssemblyFunction.render`;
- `AssemblyBlock.render`;
- `AssemblyInstruction.render`;
- the formatting of declarations, labels, opcodes, source comments, blank
  lines, and final newline.

The future S3 component must match this reference for the selected subset before
it can be considered experimental.

## Initial S3 subset

Initial scope for the Assembly renderer subset:

- render the header `.s3asm 0.6.0`;
- render `.function <name> -> <type>`;
- render `.register rN, <type>`;
- render `.label <name>`;
- render simple instructions present in the initial fixtures:
  - `TCONST`;
  - `TMOV`;
  - `TINV`;
  - `TADD`;
  - `TCMP`;
  - `TCALL`;
  - `TBR3`;
  - `TRET`;
- preserve function order;
- preserve register order supplied by the input;
- preserve block order supplied by the input;
- preserve instruction order;
- preserve source comments when present;
- preserve blank lines and final newline.

Explicitly out of scope for the first subset:

- parsing S3 Assembly text;
- validating arbitrary Assembly;
- executing Assembly;
- native emission;
- target selection;
- broad formatting options;
- changing the default compiler path.

## Input contract

Conceptual future contract:

- an Assembly program value with a version string and an ordered list of
  functions;
- each function has a name, return type, ordered register declarations, and
  ordered blocks;
- each block has a label and ordered instructions;
- each instruction has an opcode, operands, optional callee, optional labels,
  optional immediate, and optional source location.

Minimum possible first implementation:

- a constrained Assembly-shaped value for the fixture subset only;
- fixed instruction variants used by `examples/first.s3`,
  `examples/simple_call.s3`, and `examples/sign.s3`;
- no parser;
- no mutation;
- no broad validation.

Current blockers:

- strings are needed to produce text;
- arrays or vectors are needed for ordered functions, registers, blocks, and
  instructions;
- records or structs are needed for named Assembly data;
- enums or equivalent tags are needed for opcodes and types;
- reusable helpers are needed for register names and line rendering.

## Output contract

The output must be deterministic S3 Assembly text:

- no absolute paths;
- no host data;
- no timestamps;
- stable function order;
- stable register order;
- stable block order;
- stable instruction order;
- stable spacing matching the Python reference;
- stable source comments when included by the input;
- final newline preserved.

For the initial subset, the expected comparison is exact text equality with the
Python-rendered Assembly for the same fixture.

## Required language features

| Feature | Priority | Why it is needed | Temporary alternative |
| --- | --- | --- | --- |
| Strings | P0 | Required to render Assembly text, names, opcodes, comments, and newlines. | None for a useful renderer. |
| Arrays or vectors | P0 | Required to preserve ordered functions, registers, blocks, and instructions. | Fixed-size arrays for very small fixtures only. |
| Reusable helper functions | P0 | Required for register formatting, instruction formatting, and line joining. | Single-file helpers can work before modules exist. |
| Program tests | P0 | Required to validate the S3 renderer as a compiled program. | Existing CLI checks can validate fixture programs. |
| Records or structs | P1 | Required to represent Assembly functions, blocks, and instructions clearly. | Positional encodings for a tiny experiment only. |
| Enums or tags | P1 | Required to represent opcodes and types safely. | Integer tags for a constrained experiment only. |
| Structural comparison | P1 | Useful for testing intermediate Assembly-shaped values. | Text-only comparison at first. |
| Modules and imports | P1 | Needed once renderer helpers are split across files. | Keep the first experiment in one file. |
| Deterministic serialization | P1 | Needed for stable Python-vs-S3 artifact comparison. | Direct Assembly text output for the first subset. |
| Controlled file I/O | P2 | Useful for later standalone comparison tools. | Python harness can provide fixture data initially. |

## Comparison strategy

1. The Python compiler compiles a fixture and renders Assembly using
   `bootstrap/s3/assembly.py`.
2. The future S3 renderer receives equivalent Assembly-shaped fixture data.
3. The S3 renderer emits deterministic Assembly text.
4. A harness compares Python output and S3 output byte-for-byte.
5. Any difference is reported as a unified diff.
6. CI can run the comparison once the S3 renderer and harness exist.

This strategy deliberately starts with text comparison because the renderer's
observable behavior is text.

## Fixtures

Initial fixtures:

- `examples/first.s3`;
- `examples/simple_call.s3`;
- `examples/sign.s3`.

These are already part of the stable program and inspect coverage. This
delivery does not add new fixtures.

## Acceptance criteria

The candidate can move from decision to implementation only when:

- S3 has enough strings, ordered data, reusable helpers, and compound data
  support for the selected subset;
- a S3 renderer program compiles with the Python compiler;
- there is an automatic Python-vs-S3 comparison harness;
- existing S3 program checks pass;
- inspect and diagnostic goldens continue passing;
- output is deterministic;
- CI can validate the comparison;
- the implementation remains behind an experimental path until proven.

## Next steps

0.10-E:

- define the detailed contract for the Assembly renderer subset;
- list exact input shapes, supported instruction variants, and formatting rules.

0.10-F:

- implement or specify the most blocking minimum language feature;
- likely candidates are minimal strings or arrays/vectors, depending on the
  chosen subset encoding.

0.10-G:

- create the Python-vs-S3 comparison harness for the selected subset;
- keep the Python renderer as the reference.

Do not promise immediate implementation of the renderer while the required
language features are still missing.

## Milestone 1.01 selection

Milestone 1.01 selects the Assembly opcode classifier as the first implemented
S3 toolchain component.

The opcode classifier is a narrow subcomponent of the Assembly renderer subset.
It does not render text. It classifies Assembly opcodes into deterministic
metadata used by renderer and verifier logic:

- whether an opcode is value-producing, memory-related, or terminating;
- the expected textual operand count for the supported Assembly shape;
- whether a candidate operand count matches the opcode contract.

The component is small enough to implement with the current language:

- module declarations and imports keep the id table separate from the
  classifier;
- records model classifier queries;
- enums model opcodes and opcode categories;
- exhaustive enum `match` covers every supported opcode;
- scalar public entry points make Python-vs-S3 differential tests possible
  before type imports and dynamic strings exist.

Alternatives rejected for Milestone 1.01:

- full Assembly text rendering still requires runtime text construction beyond
  this milestone;
- an IR normalizer needs broader IR-shaped data and serialization;
- a diagnostic formatter needs dynamic strings or JSON-like output;
- lexer, parser, optimizer, backend, emulator, and CLI remain too broad for the
  first implementation.

Maturity target for this component is `differential reference`: Python remains
the reference implementation, and the S3 component is validated beside it
without becoming the default compiler path.
