# Assembly Renderer Comparison Harness

## Purpose

This harness stabilizes the future comparison interface between the Python
Assembly renderer and a later S3 Assembly renderer.

The command exists now so tests can validate the blocked state deterministically
before the S3 renderer exists.

## Current status

The Python renderer remains the reference implementation. A compilable S3 stub
and nine executable S3 renderer bootstrap artifacts now exist, but the S3
renderer implementation is not available.

String literals are available only as front-end expressions. Runtime string
support is not implemented, so the renderer comparison remains blocked.

S3 0.10 closed with the candidate contracts and readiness gate in place. S3
0.11 is closed after establishing deterministic static text helpers. S3 0.12
is closed after making `first` available and passed. S3 0.13 is closed after
making `simple_call` available and passed. S3 0.14 is closed after making
`sign` available and passed. S3 0.15 is closed after keeping the renderer
candidate check state safely blocked while clarifying the reason; see
`docs/roadmap-0.10.md`, `docs/roadmap-0.11.md`,
`docs/roadmap-0.12.md`, `docs/roadmap-0.13.md`, `docs/roadmap-0.14.md`,
`docs/roadmap-0.15.md`, `docs/roadmap-0.16.md`,
`docs/roadmap-0.17.md`, `docs/roadmap-0.18.md`, and
`docs/roadmap-0.19.md`, `docs/roadmap-0.20.md`,
`docs/roadmap-0.21.md`, `docs/roadmap-0.22.md`,
`docs/roadmap-0.23.md`, `docs/roadmap-0.24.md`,
`docs/roadmap-0.25.md`, `docs/roadmap-0.26.md`, and
`docs/roadmap-0.27.md`. S3 0.16 is closed after
routing the three current
fixture probes through the incremental renderer core. S3 0.17 is closed after
connecting the `first`, `simple_call`, and `sign` fixture paths to that core
through controlled `AssemblyProgram` adapters. S3 0.18 is closed after
consolidating those controlled adapters behind a common supported
`AssemblyProgram` renderer subset. S3 0.19 is closed after expanding that
Python-side path to match the current `AssemblyProgram.render()` output and
making `AssemblyProgram.render()` delegate to it, while keeping the global
`--check` mode blocked. S3 0.20 is closed after adding an executable S3
renderer bootstrap spike that validates supported-subset invariants without
claiming to be the full textual renderer. S3 0.21 is closed after adding an
executable S3 output model for fixture rendering metrics.
S3 0.22 is closed after adding an executable S3 text segment model that assigns
numeric IDs to Assembly text segment kinds and validates fixture segment
metrics without runtime strings or text emission.
S3 0.23 is closed after adding an executable S3 line blueprint model that maps
each current Assembly output line to one primary numeric blueprint, treating
source metadata as an instruction-line variant instead of a separate segment.
S3 0.24 is closed after adding an executable S3 line sequence model that records
the ordered blueprint IDs for each current fixture and validates fixture
boundaries, transition rules, negative probes, totals, and a small deterministic
signature without runtime strings or arrays.
S3 0.25 is closed after adding an executable S3 line content encoding model that
records scalar line categories, directive IDs, opcode IDs, register arities,
operand/source flags, ordinals, totals, and deterministic line encoding
signatures without runtime strings or arrays.
S3 0.26 is closed after adding an executable S3 event stream model that records
ordered renderer emission events, payload classes, transition rules, counts,
and deterministic event/payload signatures without runtime strings or arrays.
S3 0.27 is closed after adding an executable S3 event writer state model that
consumes those events and records writer states, line advancement, emitted
counts, final state, and deterministic signatures without runtime strings or
arrays.
S3 0.28 is closed after adding an executable hosted S3 output buffer model that
consumes numeric writer writes and records capacity, cursor progress, write
counters, buffer states, overflow behavior, final state, and deterministic
signatures without runtime strings or arrays.

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

0.12-B creates the first versioned candidate actual output for `first` from
`build_first_fixture_assembly_text()`. The actual-output contract now marks
`first` as available with pending formal comparison, while `simple_call` and
`sign` remain blocked and absent. `--check` remains blocked until the formal
`first` comparison is introduced.

0.12-C formalizes that comparison. `python tools/compare_assembly_renderer.py
--candidate-compare-available` compares available actual outputs only; `first`
passes byte-for-byte against the LF-normalized inspect golden, while
`simple_call` and `sign` remain blocked. The global `--check` mode still fails
because the complete S3 renderer is not implemented.

After 0.12, `first` is available and passed. The next focus is `simple_call`;
`sign` remains blocked. `--check` stays blocked until the required fixture
coverage is sufficient.

0.13-A adds an in-memory probe for `simple_call` using the same deterministic
static text path. It validates the expected output against the LF-normalized
inspect golden, but it does not create a candidate actual output: `simple_call`
remains blocked and `not_implemented`, and `sign` remains blocked.

0.13-B creates the versioned candidate actual output for `simple_call` from
`build_simple_call_fixture_assembly_text()`. The contract now marks `first` as
available and passed, `simple_call` as available with pending formal
comparison, and `sign` as blocked and `not_implemented`. The S3 renderer is
still a stub and `--check` remains blocked until later fixture coverage and the
renderer implementation exist.

0.13-C formalizes the available `simple_call` comparison. `python
tools/compare_assembly_renderer.py --candidate-compare-available` now reports
both `first` and `simple_call` as passed byte-for-byte against their
LF-normalized inspect goldens, while `sign` remains blocked and absent. The
global `--check` mode still fails because the S3 renderer is not implemented.

After 0.13, `first` and `simple_call` are available and passed. S3 0.14 moves
the practical fixture focus to `sign`, which remains `not_implemented` and
blocked. The global `--check` mode remains blocked while `sign` is not passed.

0.14-A adds an in-memory probe for `sign` using `StaticTextLineEmitter`. It
validates the expected output byte-for-byte against the LF-normalized inspect
golden, including byte count, line count, and SHA-256 metadata, but it does not
create a versioned candidate actual output or change the actual-output
contracts. `first` and `simple_call` remain available and passed, `sign`
remains blocked and `not_implemented`, and the global `--check` mode still
fails because the S3 renderer is not implemented.

0.14-B creates the versioned candidate actual output for `sign` from
`build_sign_fixture_assembly_text()`. The contract now marks `first` and
`simple_call` as available and passed, and `sign` as available with pending
formal comparison. The global `--check` mode remains blocked because the S3
renderer is not implemented; 0.14-C should formalize the byte-for-byte `sign`
comparison before the project separately evaluates whether that global state
can change.

0.14-C formalizes the available `sign` comparison. `python
tools/compare_assembly_renderer.py --candidate-compare-available` now reports
`first`, `simple_call`, and `sign` as passed byte-for-byte against their
LF-normalized inspect goldens. The global `--check` mode still fails because
the S3 renderer is not implemented; changing that blocked state is a separate
follow-up decision.

After 0.14, `first`, `simple_call`, and `sign` are available and passed. S3
0.15 keeps the global `--check` mode blocked because the real S3 renderer is
still missing. `--candidate-compare-available` is the passing mode for completed
actual outputs; global check success remains reserved for a real renderer.

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
API; it does not render Assembly. The same command also executes
`examples/self_hosting/assembly_renderer_bootstrap.s3` and expects `main` to
return `0`. That spike validates scalar opcode, directive, fixture line-count,
and operand-shape invariants, then reports renderer implementation and full text
rendering as `not_implemented`. The command also executes
`examples/self_hosting/assembly_renderer_output_model.s3` and expects `main` to
return `0`. That model validates structural output metrics for `first`,
`simple_call`, and `sign`, then reports `s3 output model: passed` without
declaring full text rendering implemented. The command also executes
`examples/self_hosting/assembly_renderer_text_segments.s3` and expects `main`
to return `0`. That model validates numeric segment IDs and segment counts for
the same fixtures, then reports `s3 text segment model: passed` while the real
textual renderer remains unavailable.
The command also executes
`examples/self_hosting/assembly_renderer_line_blueprints.s3` and expects `main`
to return `0`. That model validates one primary line blueprint per rendered
Assembly line, then reports `s3 line blueprint model: passed` while renderer
implementation and full text rendering remain `not_implemented`.
The command also executes
`examples/self_hosting/assembly_renderer_line_sequences.s3` and expects `main`
to return `0`. That model validates the ordered line blueprint sequence for
each fixture, legal transitions between blueprint kinds, invalid transition and
index probes, function boundaries, totals, and a deterministic sequence
signature, then reports `s3 line sequence model: passed` while renderer
implementation and full text rendering remain `not_implemented`.
The command also executes
`examples/self_hosting/assembly_renderer_line_encodings.s3` and expects `main`
to return `0`. That model validates line categories, directive/opcode IDs,
register operand arity, operand/source flags, unknown probes, totals, and
deterministic content encoding signatures, then reports `s3 line content
encoding model: passed` while renderer implementation and full text rendering
remain `not_implemented`.
The command also executes
`examples/self_hosting/assembly_renderer_event_stream.s3` and expects `main`
to return `0`. That model validates renderer event kinds, payload classes,
payload permissions, event transitions, unknown probes, counts, and
deterministic event/payload signatures, then reports `s3 event stream model:
passed` while renderer implementation and full text rendering remain
`not_implemented`.
The command also executes
`examples/self_hosting/assembly_renderer_event_writer.s3` and expects `main`
to return `0`. That model validates writer state transitions, line
advancement, emitted counters, opened/closed function balance, final state,
unknown probes, and deterministic final-state signatures, then reports
`s3 event writer model: passed` while renderer implementation and full text
rendering remain `not_implemented`.
The command also executes
`examples/self_hosting/assembly_renderer_output_buffer.s3` and expects `main`
to return `0`. That model validates numeric writer writes, capacity, cursor
progress, final buffer state, counters, unknown probes, overflow, and a
deterministic final-buffer signature, then reports `s3 output buffer model:
passed` while renderer implementation and full text rendering remain
`not_implemented`.

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
the S3 renderer is unavailable. Its output reports that actual outputs and
available comparisons passed, then marks renderer implementation as
`not_implemented` and the global check as blocked.

0.16-A adds a minimal Python Assembly text renderer core for the `first`
fixture path. It uses `StaticTextLineEmitter` through structured operations
instead of emitting every `first` line directly in the probe. This is a step
away from fixture-only probes, but it does not render arbitrary
`AssemblyProgram` values and does not implement the real S3 renderer.

0.16-B applies that renderer core to `simple_call`. The existing core API can
emit its parameters, two functions, `TCALL`, and the blank line between
functions without adding a general `AssemblyProgram` dependency. `first` and
`simple_call` now use the core; `sign` remains on the previous probe path. The
global `--check` mode remains blocked because the S3 renderer is still not
implemented.

0.16-C applies that renderer core to `sign`. The existing core API can emit its
parameters, registers, `TBR3`, labels, source metadata, blank line between
functions, and `.end` directives without adding a general `AssemblyProgram`
dependency. `first`, `simple_call`, and `sign` now use the core, closing S3
0.16 while keeping all inspect goldens and candidate actual outputs
byte-for-byte unchanged. The global `--check` mode remains blocked because the
S3 renderer is still not implemented.

0.17-A adds a minimal `AssemblyProgram` adapter for `first`. It validates the
first-only real model shape and emits through `AssemblyTextRenderer`, preserving
byte-for-byte output against the LF-normalized inspect golden and the versioned
candidate actual output. This does not replace `AssemblyProgram.render()`,
does not migrate `simple_call` or `sign`, and does not implement the S3
renderer. The global `--check` mode remains blocked.

0.17-B extends the controlled `AssemblyProgram` adapter to `simple_call`. It
validates the narrow two-function `add`/`main` model shape, including
parameters, registers, `TCALL`, and source metadata, then emits through
`AssemblyTextRenderer` with byte-for-byte stable output against the
LF-normalized inspect golden and candidate actual output. This still does not
replace `AssemblyProgram.render()`, does not migrate `sign`, and does not
implement the S3 renderer. The global `--check` mode remains blocked.

0.17-C extends the controlled `AssemblyProgram` adapter to `sign`. It validates
the narrow two-function `sign`/`main` model shape, including parameters,
registers, `TCMP`, `TBR3`, `TCALL`, multiple labels, and source metadata, then
emits through `AssemblyTextRenderer` with byte-for-byte stable output against
the LF-normalized inspect golden and candidate actual output. This closes S3
0.17 without replacing `AssemblyProgram.render()` globally and without
implementing the S3 renderer. The global `--check` mode remains blocked.

0.18 adds `render_supported_program(program)` as the common supported
`AssemblyProgram` adapter path. The previous `render_first_program`,
`render_simple_call_program`, and `render_sign_program` wrappers keep their
fixture-specific validation and delegate byte emission to the common path.
The supported subset covers only the shapes already proven by `first`,
`simple_call`, and `sign`, including source metadata, labels, `TCALL`, `TBR3`,
and the fixture opcodes. Actual outputs and inspect goldens remain unchanged,
and the global `--check` mode remains blocked because the real S3 renderer is
not implemented.

0.19 adopts that Python-side path inside the real `AssemblyProgram.render()`
method. The supported adapter now covers the current Python Assembly text
format, including `.memory`, `TLOAD`, `TSTORE`, `TJMP`, `TMIN`, `TMAX`, optional
source metadata, and `TCALL` arities beyond the initial fixtures. The inspect
goldens and candidate actual outputs remain unchanged. This is still not the
S3 renderer implementation: `--candidate-compare-available` remains the passing
available-output check, and global `--check` remains blocked with renderer
implementation reported as `not_implemented`.

0.20 adds `examples/self_hosting/assembly_renderer_bootstrap.s3`, an executable
S3 bootstrap kernel for the future renderer. It uses only scalar S3 features to
validate the supported opcode surface, `.memory` directive coverage, fixture
line counts for `first`, `simple_call`, and `sign`, and representative operand
shapes. `--candidate-run` executes it and reports `s3 bootstrap spike: passed`,
but the full textual S3 renderer remains absent and global `--check` remains
blocked.

0.21 adds `examples/self_hosting/assembly_renderer_output_model.s3`, an
executable S3 output model for the same fixture set. It calculates and validates
line, function, parameter, register, memory, label, instruction, directive, and
distinct opcode counts for `first`, `simple_call`, and `sign`, plus combined
totals. `--candidate-run` executes both the bootstrap spike and the output
model, reporting both as passed while renderer implementation and full text
rendering remain `not_implemented`.

0.22 adds `examples/self_hosting/assembly_renderer_text_segments.s3`, an
executable S3 model of renderer text segments. It represents `.s3asm`,
`.function`, `.param`, `.register`, `.memory`, `.label`, `.end`, instruction
lines, blank lines, and source metadata as stable numeric IDs, then validates
segment metrics for `first`, `simple_call`, and `sign`. `--candidate-run`
executes the bootstrap spike, output model, and text segment model, reporting
all three as passed while renderer implementation and full text rendering
remain `not_implemented`.

0.23 adds `examples/self_hosting/assembly_renderer_line_blueprints.s3`, an
executable S3 model of renderer line blueprints. It maps every current rendered
Assembly line in `first`, `simple_call`, and `sign` to exactly one primary
numeric blueprint, with source metadata encoded as the
`instruction_with_source` line variant rather than as a separate text segment.
`--candidate-run` executes the bootstrap spike, output model, text segment
model, and line blueprint model, reporting all four as passed while renderer
implementation and full text rendering remain `not_implemented`.

0.24 adds `examples/self_hosting/assembly_renderer_line_sequences.s3`, an
executable S3 model of ordered renderer line blueprint sequences. It validates
the exact blueprint ID order for `first`, `simple_call`, and `sign`, the legal
transition table used by those sequences, negative transition/index/fixture
probes, function start/end boundaries, line and transition totals, and a small
deterministic sequence signature. `--candidate-run` executes the bootstrap
spike, output model, text segment model, line blueprint model, and line sequence
model, reporting all five as passed while renderer implementation and full text
rendering remain `not_implemented`.

0.25 adds `examples/self_hosting/assembly_renderer_line_encodings.s3`, an
executable S3 model of renderer line content encodings. It validates scalar
categories, directive IDs, opcode IDs, register arities, operand/source flags,
function/block ordinals, negative probes, aggregate totals, and deterministic
fixture signatures for `first`, `simple_call`, and `sign`. `--candidate-run`
executes the bootstrap spike, output model, text segment model, line blueprint
model, line sequence model, and line content encoding model, reporting all six
as passed while renderer implementation and full text rendering remain
`not_implemented`.

0.26 adds `examples/self_hosting/assembly_renderer_event_stream.s3`, an
executable S3 model of renderer emission events. It validates one event per
current rendered line for `first`, `simple_call`, and `sign`, payload classes
derived from line encodings, legal event transitions, negative probes, aggregate
event counts, and deterministic event/payload signatures. `--candidate-run`
executes all seven executable renderer bootstrap artifacts and reports them as
passed while renderer implementation and full text rendering remain
`not_implemented`.

0.27 adds `examples/self_hosting/assembly_renderer_event_writer.s3`, an
executable S3 model of renderer writer state. It consumes the modeled event
stream for `first`, `simple_call`, and `sign`, validates state before and after
events, line advancement, counters, function open/close balance, last event,
final state, negative probes, and deterministic final-state signatures.
`--candidate-run` executes all eight executable renderer bootstrap artifacts
and reports them as passed while renderer implementation and full text
rendering remain `not_implemented`.

0.28 adds `examples/self_hosting/assembly_renderer_output_buffer.s3`, an
executable hosted S3 model of renderer output buffering. It consumes numeric
writer writes for `first`, `simple_call`, and `sign`, validates capacity,
cursor movement, write counters, state transitions, overflow, final state,
negative probes, and deterministic final-buffer signatures. `--candidate-run`
executes all nine executable renderer bootstrap artifacts and reports them as
passed while renderer implementation and full text rendering remain
`not_implemented`.

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

The Python `AssemblyProgram.render()` path now uses the shared Python-side
adapter, but the harness still treats the S3 renderer implementation as absent.

It does not alter the Assembly format.

It does not alter CI.
