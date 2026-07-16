# S3 0.12 Roadmap

Status: closed

## Objective

S3 0.12 used the deterministic static text foundation from S3 0.11 to create
the first real candidate actual output path. The milestone focused only on the
`first` fixture and deliberately kept broader renderer work out of scope.

0.12 is complete after 0.12-C. There is no 0.12-D planned. The next milestone
starts the move from `first` to `simple_call`.

## Completed sequence

### 0.12-A: in-memory first fixture output probe

0.12-A added an in-memory probe for the `first` fixture. The probe builds the
expected Assembly text with `StaticTextLineEmitter`, finalizes it as a
`StaticTextDocument`, and validates LF-normalized bytes and metadata against
the existing inspect golden.

### 0.12-B: first versioned actual output

0.12-B created the first versioned candidate actual output:
`tests/golden/assembly_renderer_candidate_actual/first.assembly.txt`.

The file is generated from `build_first_fixture_assembly_text()`, keeps
LF-stable bytes, and is tracked by the existing actual-output contract.

### 0.12-C: first byte-for-byte comparison

0.12-C formalized the byte-for-byte comparison for `first`. The expected
inspect golden and the versioned candidate actual output match after LF
normalization, so `first` has `comparison_status: passed`.

The partial comparison mode is:

`python tools/compare_assembly_renderer.py --candidate-compare-available`

## Delivered

0.12 delivered:

- the first Assembly output reconstructed in memory;
- the first versioned candidate actual output;
- formal byte-for-byte comparison for `first`;
- stable `first` metadata:
  - bytes: 441;
  - lines: 18;
  - sha256: `46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67`;
- `--candidate-compare-available`;
- partial renderer candidate state;
- `simple_call` and `sign` still blocked.

## Not delivered

0.12 did not:

- implement the real S3 renderer;
- create an actual output for `simple_call`;
- create an actual output for `sign`;
- make `python tools/compare_assembly_renderer.py --check` pass;
- alter inspect goldens;
- alter parser, lexer, semantic analysis, lowering, IR, backend, or emulator;
- migrate the full Python compiler to S3.

## Next milestone

S3 0.13 moves from the isolated `first` output to the `simple_call` fixture. The
goal is to start covering function and call structure without attempting a full
renderer migration; see `docs/roadmap-0.13.md`.
