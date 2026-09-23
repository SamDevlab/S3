# Exact Segment Budget Hardening

## Pre-implementation feasibility audit

Audit base: S3 documentation head `e814f5457c2fdd346d85f3b8a6321e96b2bc759f`; frozen P2 source `1a76e341098b54a639fec22eecea362cc243c46f`.

The current `_emit_budgeted_segment()` emits the fast guard and precharge, the fast instruction sequence, a jump around the inline slow copy for nonterminating segments, and then the scalar slow sequence with per-instruction accounting. The segment planner itself partitions at calls, branches, and returns. The proposed hardening leaves that planner and both instruction-sequence emitters unchanged.

| Strategy | E0 preservable | P0 byte identity preservable | No new per-instruction hot cost | Existing emitter structure | Fail closed | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| A. Cold-outline duplicated slow path | Yes: emit the same scalar slow sequence and failure sites; only relocate it and preserve its continuation edge | Yes: applies only to `EXACT_SEGMENT`; default `PER_INSTRUCTION` emission is untouched | Yes: the fast path retains its guard/precharge and can fall through instead of jumping over the duplicate | Yes: collect existing slow instruction sequences and place them in an ELF cold text section; branch/continuation labels remain explicit | Yes: assembly, link, E0, and FFI gates must all pass; otherwise retain P2 | `ELIGIBLE`, selected as the one candidate |
| B. Structurally shared exact slow path | Not with the existing unique instruction bodies without changing execution representation | Potentially, but irrelevant to P0 | No credible body sharing is available without per-instruction dispatch/calls or a generic interpreter | No: a shared executor would add a new execution mechanism, not factor existing emitter structure | Not applicable | `REJECTED_COMPLEXITY` |
| C. Current inline duplication | Already proven by the P2 gates | Yes | Yes | Yes | Yes | Control; no implementation |

Strategy A is a layout experiment, not presumed code-size compression. It moves unique scalar copies from `.text` to `.text.unlikely`. We will report `.text` separately from total executable text (`.text` plus `.text.unlikely`); no total-byte reduction or runtime benefit is claimed in advance. The fast path must not gain per-instruction work. Slow replay retains the existing exact accounting, diagnostic contexts, terminators, and continuation behavior.

`plan_budget_segments()` and all segment weights, barriers, and eligibility remain unchanged. The `PER_INSTRUCTION` branch is not edited. P0 identity remains an explicit gate, not an assumption. If ELF sectioning, function metadata, standalone linking, FFI artifacts, E0 behavior, or any predeclared threshold fails, P2 remains the candidate and no second hardening design will be attempted.

## Hypotheses

`H12`: the exact slow path can be outlined while preserving E0 and P0 and improving hot layout without material performance degradation. `UNDER_TEST`.

`H12A`: placing exact scalar replay copies in a cold executable section reduces the hot code footprint without degrading P2 timing. `UNDER_TEST`.

No H12B is opened because structural body sharing was rejected before implementation. No new budget architecture is proposed.

## Evidence log

Implementation, focused tests, source freeze, full-suite evidence, Linux native validation, benchmark validation, and final disposition will be appended here. Existing P2 timing and full-suite evidence remain historical controls and will not be relabeled as P2H results.
