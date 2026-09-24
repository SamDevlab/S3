# Exact Segment Budget Semantic Closure

**Status:** Review evidence; no promotion or merge is authorized.
**Candidate implementation:** P2 `1a76e341098b54a639fec22eecea362cc243c46f`
**Test/evidence freeze:** `c07b2c486b98e8408119f44ceedceb46c6d2549b`
**Platform:** Linux x86-64

## Concurrency Contract Audit

The reviewed public contracts do not promise concurrent host-thread entry into
one loaded native artifact. ADR-0008 defines the native ABI/runtime scope and
ADR-0014 defines logical instruction accounting, but neither specifies
same-artifact concurrency. The existing tests
`test_repeated_serial_ffi_calls_preserve_process_budget_lifetime` and
`test_foreign_callback_reentry_observes_a_complete_call_segment` qualify
serialized calls and synchronous callback re-entry, respectively; neither is a
concurrent-entry test. The resulting existing contract classification is
`UNSPECIFIED`, not supported and not explicitly unsupported.

In both P0 (`e07d0b5464bf472b2ca18993f3e196a234ff0fc5`) and P2, the generated
runtime places `__s3_instruction_count` and `__s3_frame_count` in aligned,
writable `.bss` storage in the native artifact. P0 updates these with ordinary
memory `inc`/`dec`; P2 retains scalar `inc`/`dec` and adds ordinary memory
`add` for segment precharge. There is no lock, `lock`-prefixed RMW, or
thread-local storage. The accounting state is shared by calls using the same
loaded artifact instance and persists across qualified serial FFI calls. A
second loader namespace or separately mapped copy was not tested and is not
claimed to share or isolate state.

The assembly therefore does not provide concurrent accounting safety: races
could lose counter updates or produce nondeterministic limit outcomes. This is
not evidence that P2 weakens a documented promise: the audited P0 baseline has
the same unsynchronized accounting model, and no same-artifact concurrency
promise was found. Runtime synchronization is not added by this campaign.

The conservative proposal is:

```text
SAME_ARTIFACT_CONCURRENT_FFI=NOT_SUPPORTED_UNLESS_EXPLICITLY_QUALIFIED
CALLER_REQUIREMENT=SERIALIZE_ENTRY_INTO_ONE_LOADED_ARTIFACT
SYNCHRONOUS_CALLBACK_REENTRY=SUPPORTED_WITHIN_QUALIFIED_SERIAL_CALL
CONCURRENT_FFI_TESTS=NOT_REQUIRED_UNDER_PROPOSED_SCOPE
PROPOSED_SCOPE_ACCEPTED=NO
```

This wording is a proposed scope, not an accepted normative change. Project
governance must accept it before the candidate can be described as a supported
native capability. Consequently, semantic readiness remains `CONDITIONAL`.

## Instruction-Limit Domain and Boundaries

The native API accepts integer values in `1..2^64-1`; zero and negative values
are rejected, `bool` and other non-integers are rejected, and values above the
native U64 maximum are rejected. The `PER_INSTRUCTION` mode compares the
configured limit directly: immediate encoding is used through `0x7fffffff`,
and the wide path uses `movabs` above it.

For `EXACT_SEGMENT`, the fast admission comparison is against `L-W`, not `L`.
For the boundary executable `W=2`, the tested limits `0x7fffffff` and
`0x80000000` produce immediate precharge comparisons of `0x7ffffffd` and
`0x7ffffffe`; `0x80000001` produces `0x7fffffff`. At `10_000_000_000` and
U64_MAX, the wide remaining-budget encoding is assembled and executed. The
P0 and P2 programs both execute and produce identical result/output at every
matrix limit. FFI shared objects also build and execute at every limit.

The boundary matrix uses a real two-opcode eligible segment (`W=2`). Existing
loop/call differential coverage exercises real planned segment weights 3, 4,
5, 7, and 10 at small exact limits. A synthetic emitter-level check covers
`W=U64_MAX-1`, `L=U64_MAX`, and verifies `L-W=1` plus wide weight emission; it
is explicitly encoding-only, not an executable planner segment. Thus signed
encoding, representative runtime segments, and near-limit subtraction each
have evidence, while a real W=3 segment is not separately swept across every
wide limit.

No semantic boundary bug was observed. The existing small-budget failure
boundary tests continue to establish exact fallback behavior without trying
to execute billions of logical instructions.

## Test Evidence

The test-only commit adds coverage in
`tests/test_exact_segment_instruction_budget.py`; no production/backend source
changed. The focused Linux native gate was:

```text
S3_NATIVE_REQUIRED=1
python -m pytest tests/test_exact_segment_instruction_budget.py tests/test_instruction_limit_e2.py tests/test_native_x86_64.py -ra
75 passed in 3.05s
exit=0
python=3.14.4
pytest=9.1.1
```

One full S3 suite ran on the exact Git checkout (with valid Git metadata) at
`c07b2c486b98e8408119f44ceedceb46c6d2549b`:

```text
4390 passed
1 skipped
572 subtests passed
0 failed
exit=0
elapsed=3698.92s
```

The single skip is `tests/test_m187_package_signatures.py:90` because the guest
environment lacks the optional `cryptography` package. The raw transcript is
`evidence/full-suite-valid-c07b2c48-linux-x86_64.txt`, SHA-256
`6ebbbdc645cb66b3fcfea5b5683b64c416acd15eff11181ab2a99f6473f0e8b0`. The
transcript records the exact tested HEAD, start/end times, valid Git metadata,
and exit status.

An earlier, non-qualifying full-suite attempt used a source archive without
`.git`; renderer golden lookups and Git metadata tests failed because Git
objects were unavailable. It reported `50 failed, 4269 passed, 1 skipped,
113 errors, 91 subtests passed`, exit 1. That diagnostic transcript is
preserved losslessly in
`evidence/full-suite-invalid-git-archive-c07b2c48-linux-x86_64.tar.gz` and is
not counted as a candidate failure or a valid suite gate. Its decompressed
SHA-256 is `c1181dcae4cbfe18c3b3f7f59662de4dfaef569923c8a12bb395cdd255b0dd16`
(246,267 bytes); the `.tar.gz` archive SHA-256 is
`71867b77d936d2be2204613226ac1c11d075a687c24c6876a3da48deac3d3482`. No suite
was repeated after the valid run.

The native focused result and both suite transcripts are evidence only; no
benchmark was run or changed. Python compileall passed for `bootstrap/s3` on
the frozen source. `git diff --check` is required again after report updates.

## Readiness Delta

```text
BACKEND_IMPLEMENTATION_CHANGED=NO
TEST_SOURCE_CHANGED=YES
LIMIT_BOUNDARIES=PASS
CONCURRENCY_CONTRACT_SOURCE=UNSPECIFIED
PROPOSED_CONCURRENCY_SCOPE=NOT_SUPPORTED_UNLESS_EXPLICITLY_QUALIFIED
SEMANTIC_READINESS=CONDITIONAL_PENDING_GOVERNANCE
TECHNICAL_CANDIDATE_READINESS=CONDITIONAL
RELEASE_GATE_READINESS=BLOCKED
```

Other release blockers remain: the #301-#309 integration stack, S3 CI
pre-step failures without an attributed cause, disabled benchmark-repository
Actions, and product policy for the measured `.text` growth. The P2 default
and all promotion/release states remain unchanged. The next critical decision
is governance acceptance or revision of the same-artifact concurrency scope;
after that, the recommended engineering campaign is
`S3_1_X_PR_STACK_INTEGRATION_CLOSURE`, before investing in CI repair.

No production code, default, benchmark evidence, PR #310, or canonical
performance ledger was changed. PR #311 remains review-only, Draft, and
unmerged; this campaign creates at most one separate Draft PR for the test and
semantic evidence.
