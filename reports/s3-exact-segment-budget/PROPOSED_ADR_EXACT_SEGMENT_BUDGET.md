# Proposed ADR: Exact Segment Instruction Budget

```text
STATUS=PROPOSED
ACCEPTED=NO
```

## Context

The accepted instruction-budget contract in ADR-0014 counts logical S3
Assembly opcodes. P0 performs an exact check and increment before every opcode.
That implementation is the semantic oracle. P2 reduces repeated counter
traffic by grouping only a proven block-local sequence of logical opcodes into
an exact segment. This proposal formalizes P2; it does not accept or promote it.

## Decision Proposed

1. Preserve `PER_INSTRUCTION` as the default and correctness oracle.
2. Permit `EXACT_SEGMENT` only in the qualified x86-64 backend path until a
   stable public API is separately approved.
3. Count logical S3 Assembly instructions, including `TCALL`, `TBR3`, `TJMP`,
   and `TRET`; never count physical x86-64 instructions or helpers.
4. Keep segments within one basic block and end them at calls, branches,
   returns, and block boundaries. Fused native lowering does not reduce logical
   weight.
5. For current count `C`, configured limit `L`, and segment weight `W`, take
   the fast path only when `C + W <= L`, implemented with an overflow-safe
   comparison against `L - W`. Charge `W` before executing the segment.
6. If the full segment does not fit, execute the original per-instruction
   checks. The failing logical instruction does not execute and retains its
   function, block, opcode, source context, and error category.
7. Keep one instruction counter per loaded native artifact instance,
   consistent with the existing serial runtime model. Calls and recursion
   using that instance do not reset it. Do not claim sharing or isolation
   across separate loader namespaces or mappings without separate evidence.
   Frame and memory guards remain independent.
8. Qualify E0 for serial execution and synchronous callback re-entry at call
   barriers. The same-artifact concurrency governance recommendation and its
   pending authority status are recorded in the section below. This proposal
   is not an accepted normative contract.
9. Do not expose PNEG in production. It remains an unsafe benchmark lower bound.

## E0 Contract and Evidence Mapping

| Required equivalence | Evidence |
| --- | --- |
| Same success/failure and result on exact boundaries | `test_single_segment_w_minus_one_exact_and_w_plus_one_boundaries` |
| Same side effects before/after budget exhaustion | `test_side_effect_boundary_before_and_after_budget_exhaustion_matches_p0` |
| Calls, loops, and branches preserve accounting order | `test_loop_calls_and_failure_boundaries_match_p0` |
| Non-budget failure inside an eligible segment preserves context | `test_non_budget_runtime_failure_inside_fast_path_matches_p0` |
| Serial repeated FFI calls share budget lifetime | `test_repeated_serial_ffi_calls_preserve_process_budget_lifetime` |
| Callback re-entry observes a complete call segment | `test_foreign_callback_reentry_observes_a_complete_call_segment` |
| Fused compare/branch guarded reads retain diagnostics | `test_fast_fused_compare_keeps_context_for_guarded_register_reads` |
| Structure and precharge match exact segment plan | `test_planner_is_block_local_and_splits_after_calls_and_control`; `test_exact_segment_codegen_has_exact_precharge_and_scalar_slow_path` |
| Six limit values build/execute in both modes and P0/P2 agree | `test_instruction_limit_boundaries_build_execute_and_match_p0` |
| Invalid configuration values are rejected in both modes | `test_zero_budget_is_rejected_in_both_modes`; `test_invalid_instruction_limit_domain_is_rejected_in_both_modes` |
| Near-U64 `L-W` arithmetic and wide weight encoding | `test_exact_segment_precharge_handles_weight_near_native_maximum` (synthetic encoding-only segment) |

### Configuration domain

Proposed native legal domain is `1 <= max_instructions <= 2^64 - 1`, default
100,000. Zero, negatives, bool, non-integer, and values above U64_MAX are
rejected. The Linux x86-64 closure matrix tests
`0x7ffffffe`, `0x7fffffff`, `0x80000000`, `0x80000001`, 10,000,000,000, and
U64_MAX in both modes, including native executable and FFI build/load/execute.
P0 selects a direct-limit immediate through `0x7fffffff` and a `movabs` path
above it. P2's fast segment check uses `L-W`; tests verify its remaining-budget
encoding, including wide values, and small-budget tests retain exact fallback
behavior. This budget does not change `max_frames` semantics.

## Compatibility and Scope

No source-language, Assembly, IR, FFI ABI, calling-convention, public-symbol,
or artifact-loading change is proposed. Existing top-level generation
signatures remain unchanged and the default emitted code is byte-identical for
the frozen representative corpus. The opt-in mode currently exists on the
exported `X8664Backend` configuration but is absent from the top-level helper
and CLI; API classification is semi-public and must be deliberately resolved
before stable opt-in.

This evidence applies to Linux x86-64 only. It makes no Windows, ARM64, or
macOS-native qualification claim.

## Evidence and Tradeoffs

P2 is the selected candidate `1a76e341098b54a639fec22eecea362cc243c46f`;
control is `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`. P2H
`6f320242e3c1ebbb0d2ac5d6d85272ab375e5333` is rejected as a hardening
replacement: its E0 and runtime gates passed but its predeclared structural
text/hot-layout materiality gate failed.

On the frozen RMSD, XSBench, and JSMN Linux x86-64 protocol, P2 recovered
92.14%-104.56% of the measured P0-to-PNEG excess across six O0/O1 cells. This
is not a universal S3 speedup. `.text` increased 39.17% for RMSD,
53.35%-53.57% for XSBench, and 58.27%-58.54% for JSMN. No runtime harm from
instruction-cache effects is established. Product owners must decide whether
that measured size cost fits intended targets; no binary-size threshold is
invented here.

QPI remains `NOT_AVAILABLE`; workload-specific evidence is sufficient for
this research decision and QPI is not required solely by this proposal.

## Alternatives and Rejected Work

- Retain P0 as default: selected for compatibility and rollback.
- Immediately switch default: rejected pending contract, product policy,
  integration, and CI gates.
- P2H cold outlining: rejected as not structurally material; do not continue
  architecture search.
- P3/P4/P5 budget architectures: closed; not proposed.
- PNEG: unsafe diagnostic only; never a candidate.

## Rollout, Rollback, and Release Gates

No rollout is authorized. If later approved, begin with an explicitly
documented Linux x86-64 opt-in, retain `PER_INSTRUCTION`, and consider a default
change only after release qualification and a product size-policy decision.
Rollback means regenerate/rebuild with `PER_INSTRUCTION` and redeploy; compiled
machine code cannot change modes in place. No data migration or source-language
change is required.

Before any promotion proposal is ready, require:

- accepted concurrency scope, including the same-artifact thread-entry rule;
- retain the exact-limit boundary matrix and small-budget failure gates;
- clean integration lineage;
- one valid green S3 CI run with actual executed steps;
- benchmark validation automation that actually runs;
- product decision on the measured `.text` tradeoff;
- focused E0/native tests and full S3 suite on exact source SHA;
- release RMSD, XSBench, and JSMN evidence with statistically justified
  regression bands and a tested fallback.

## Semantic Closure Evidence

The test-only closure candidate `c07b2c486b98e8408119f44ceedceb46c6d2549b`
passed the focused native gate (75 passed) and one full Linux x86-64 suite
(4,390 passed, 1 skipped, 572 subtests passed, exit 0). Its raw transcript is
preserved in the semantic-closure branch at
`reports/s3-exact-segment-budget/evidence/full-suite-valid-c07b2c48-linux-x86_64.txt`
(SHA-256 `6ebbbdc645cb66b3fcfea5b5683b64c416acd15eff11181ab2a99f6473f0e8b0`).
The single skip is optional `cryptography`, unavailable in the guest Python
environment. No production/backend implementation changed. Current public
documentation leaves same-artifact concurrency unspecified; the conservative
caller-serialized scope remains proposed and unaccepted.

## Concurrency Contract Governance Decision (Not Accepted)

### Context and historical contract

The existing public contract for two host threads concurrently entering the
same loaded native S3 artifact is `UNSPECIFIED`. A narrow second-pass audit of
the README, specifications, docs, ADRs, public FFI/native API material,
relevant FFI tests, and release/project artifacts found no explicit promise:
`EXISTING_CONCURRENT_ENTRY_PROMISE=NONE_FOUND`. The general S3 thread and
structured-concurrency facilities do not promise concurrent entry into one
native shared object. No repository artifact documents a current or
specifically planned product use case requiring that exact behavior.

### P0 and P2 behavior

Both P0 and P2 keep instruction accounting in an aligned writable `.bss`
object per loaded native artifact instance; frame accounting is also
artifact-scoped writable `.bss`. P0 uses ordinary memory `inc`/`dec`; P2 uses
ordinary memory `add` for segment precharge and scalar `inc`/`dec`. Those
accounting operations have no locked read-modify-write or TLS protocol. P2
therefore does not weaken an existing concurrent-entry guarantee: none was
found in P0 or the public contract.

The FFI contract describes signatures, calling convention, scalar widths,
call-scoped buffers, and ownership. It exposes no execution-context object,
per-call budget object, or TLS accounting ABI. The Python buffer registry's
lock protects that registry only; it does not synchronize native artifact
accounting. No accounting ownership model is selected here.

### Proposed contract and compatibility

The recommendation is Path A, pending human/project acceptance:

> A loaded native S3 artifact currently supports serialized host invocation.
> Synchronous callback re-entry is supported within the qualified native
> call-barrier contract. Concurrent entry into the same loaded artifact from
> multiple host threads is not currently supported. This restriction applies
> to artifact-scoped runtime accounting state and does not make a broader claim
> that all S3 execution or all S3 programs are intrinsically single-threaded.
> Future concurrent-entry support requires a separate execution-context and
> resource-accounting design.

Path A would preserve qualified serialized execution and synchronous callback
re-entry. Since no earlier public promise, test dependency, or documented
same-artifact concurrent behavior was found, its compatibility classification
is `CLARIFICATION_OF_UNSPECIFIED_BEHAVIOR`, not a breaking change. Users needing
parallel calls must not concurrently enter the same loaded artifact under the
current unaccepted proposal. No unverified workaround is prescribed.

Path B means concurrent same-artifact entry is a required native capability.
Current P0/P2 accounting does not qualify that promise. Choosing Path B would
require new decisions about budget ownership and lifetime, frame accounting,
thread interactions, failure ordering and exhaustion attribution, and callback
interaction. Thus `PATH_B_IS_NEW_RUNTIME_SEMANTICS=YES`; this ADR does not
choose shared, per-thread, or per-call accounting and does not recommend a
mutex, atomics, TLS, or any other implementation mechanism.

### Decision authority and status

The candidate-promotion policy requires explicit architectural review and an
accepted ADR. It does not identify this campaign/agent as an acceptance
authority. Therefore this document records a recommendation only:

```text
DECISION_RECOMMENDATION=PATH_A
DECISION_AUTHORITY=HUMAN_ACCEPTANCE_REQUIRED
DECISION_STATUS=READY_FOR_HUMAN_ACCEPTANCE
ACCEPTED_CONCURRENCY_CONTRACT=NONE_PENDING
```

This is a clarification proposal, not acceptance or production promotion.
Until governance accepts or revises it, same-artifact concurrent entry remains
unqualified and the concurrency blocker remains open. If Path B is selected,
stop and start a separate concurrency-design campaign. No implementation,
concurrent test, benchmark, or default change is authorized here.

### Future extension and non-goals

Path A is not a permanent ban. Concurrent same-artifact entry may be added in
a future version through a separate execution-context and resource-accounting
design. This governance closure does not implement synchronization, select an
accounting architecture, qualify concurrency, or change executable behavior.

## Open Questions

1. Is concurrent entry into one native artifact a supported product contract?
2. Should the mode remain internal or become a documented backend option?
3. What, if any, product binary-size limit applies to Linux x86-64 outputs?
4. How will the stacked #301-#309 lineage be integrated or cleanly extracted?
5. What causes the S3 pre-step CI failures, and who owns restoring Actions in
   S3-Benchmarks?

This ADR remains proposed and unaccepted. Human/project governance must review
the concurrency recommendation before stack integration proceeds and must
review the complete ADR before any production promotion work.
