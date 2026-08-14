# Research Session Log

## 2026-08-12 — Lab initialization

Production anchor:

```text
origin/main=a83e25c3364302227694399ebe12946f887c0ead
P3=COMPLETE
P4=NOT_STARTED
```

Actions:

- created long-lived branch `research/zettelkasten-lab-20260812` from P3 main;
- created durable handoff/state/new-chat bootstrap;
- established Zettelkasten protocol and initial notes;
- cataloged the initial literature corpus without copying source PDFs;
- created broad P4 research hypothesis rather than prematurely naming a production implementation;
- created experiment registry;
- created research prototypes for generic CFG, liveness, residence lattice, binary materialization min-cut, exact placement oracle, Lagrangian capacity relaxation, multi-value oracle, matroid/submodularity checks, S3 Assembly adapter and value tracing;
- created GitHub issue #171 as durable locator.

No production code was changed on `main`.
No production PR was opened.

## 2026-08-12 — Literature expansion + ternary virtualization synthesis

Additional user-supplied sources expanded the lab into many-valued logic, automata, information theory, combinatorial search, mathematical logic and ternary processor/circuit literature.

Research synthesis expanded from one flexibility dimension to three:

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF_KNOWLEDGE_FLEXIBILITY
```

Created Zettels through `S3-ZK-0027`, `TERNARY_VIRTUALIZATION.md`, and experiments `S3-EXP-0009..0013`.

Important discipline recorded:

- current S3 trit semantics are source of truth;
- do not assume a named three-valued logic without truth-table comparison;
- quantum/DNA computing literature is architecture/representation inspiration, not a backend commitment;
- Shannon entropy is not a decorative compiler metric; a probability model is required;
- state/representation information should be preserved only when downstream benefit can be demonstrated;
- research demonstration is not production maturity.

A canonical source/deduplication registry was later added under `research-lab/sources/REGISTRY.md`.

## 2026-08-12 — P4 production completed and reconciled

User/executor reported P4 complete; GitHub PR #170 was independently verified as merged.

```text
P4_BASE_SHA=a83e25c3364302227694399ebe12946f887c0ead
P4_IMPLEMENTATION_HEAD=59df1d0f9ab9147b8d7f71a1db395c5fab560171
P4_MERGE_COMMIT=a0b694fadc985c0b8e0944fb7844e14f72a838d8
P4_STATUS=COMPLETE
P5_STARTED=NO
```

Critical causal result:

```text
EARLIEST_LOCATION_FLEXIBILITY_LOSS=
X8664Backend.register_allocation default false

EARLIEST_MEMORY_IDENTITY_LAYER=
emitter frame canonicalization after RA_OFF default

RA_PRIMARY_CAUSE=NO
```

The existing whole-function liveness-aware allocator already had the required global residency machinery. P4 made RA the native default while preserving explicit `register_allocation=false` fallback.

Measured direct frame probe:

```text
loads:  1549 -> 491
stores: 1520 -> 471

frame accesses:    9282 -> 7175
metadata accesses: 5638 -> 5638
```

P4 also recorded:

```text
.text: 313169 -> 305543
static instructions: 53767 -> 53922
absolute S3 runtime: 8890.413541 -> 8405.052702 ns/parse (-5.46%)
compiler median time: -2.9208848%
```

The GCC-relative geomean moved `34.708283588x -> 38.975981467x`, but the external denominator varied. The durable metric rule is therefore to keep direct causal structural evidence, absolute S3 timings and comparator-relative ratios separate.

Residual production diagnosis:

```text
REPEATED_MEMORY_STATE_MATERIALIZATION
```

Post-P4 recommendation:

```text
SSA_DESTRUCTION_AND_MEMORY_STATE_METADATA_STAGING
```

Research consequences:

- `S3-EXP-0002 RA OFF vs RA ON` promoted to `SUPPORTED_BY_P4`;
- created `S3-ZK-0028..0031`;
- created `S3-EXP-0014 memory-state metadata provenance`;
- created `S3-EXP-0015 SSA destruction vs metadata staging`;
- updated durable `STATE.json`, `HANDOFF.md`, `NEW_CHAT_PROMPT.md`, experiment registry and Zettelkasten index;
- no P5 production implementation started.

Current highest-priority research sequence:

```text
metadata provenance
+
SSA destruction/phi/loop attribution
+
information-loss boundary audit
↓
select P5 only from measured residual cause
```
## 2026-08-12 — P5-PREWORK initialization observability

- Reconciled origin/main=a0b694fadc985c0b8e0944fb7844e14f72a838d8 and preserved the original checkout's unrelated untracked files.
- Reproduced the P5-AUDIT metric: 5638 lexical byte-frame lines and 5426 true initialization-state accesses.
- Used temporary isolated native instrumentation only in a disposable worktree; exact JSMN dynamic initialization total was 21221, with 356 proven check events and 14367 allocated-memory-reset events.
- Repeated JSMN dynamically with exact category/function/block/observer/top-site/return/total agreement.
- Added focused call/reference/slice/numeric/phi-heavy corpus evidence. Native paths passed; hosted emulator TADDR remains unsupported for reference/slice differential closure.
- Corrected the reports so only directly proven populations are classified; residual shares are UNKNOWN/UNMEASURED, not fabricated conditional shares.
- Decision: MORE_RESEARCH_REQUIRED; no production P5, PR, full suite, benchmark or shutdown.

## 2026-08-12 - P5-RESEARCH-CLOSURE

- Corrected closure trace weighting so each allocated memory metadata reset
  contributes `length * length` bytes across the `rep stosb` execution model.
- Reproduced exact JSMN allocated-memory reset bytes: 14367, with 2259 reset
  operations including register metadata and 37 memory reset operations.
- Measured direct JSMN evidence: 13340 required bytes, 1024 overwrite-before-
  observer candidates and 3 lifetime-end candidates.
- Added a disposable hosted TADDR/reference representation and validated six
  O0 native/emulator comparisons. No production file was changed or committed.
- Focused test groups passed; the O1 slice optimizer verifier limitation was
  recorded without changing code.
- Decision remains MORE_RESEARCH_REQUIRED. No full suite, benchmark, P5/P6
  production work or shutdown was started.

## 2026-08-13 - CI cost audit, O1 correction, and post-P4 reprofile

- Audited 591 Actions runs / 5506 jobs from 2026-08-01 onward: 22356.616667
  timestamp-derived job minutes, 12274.700000 non-main Tests-push minutes,
  3716.766667 research-branch minutes, and 8068.350000 redundant push-side
  minutes across 197 same-SHA push/PR pairs.
- Collected 2709 unique pytest nodes. The current matrix executes 7449 node
  instances, with 4740 duplicate executions. No test knowledge was deleted.
- Reproduced and fixed the real O1 slice SSA-to-IR metadata-loss bug in PR #172;
  natural CI passed and merged as 229811359948cf8e12848036882edaa89108a9fa.
- Opened the single CI-efficiency PR #173 from the P4 main anchor. Its natural
  run retains native, differential, SSA, Python, benchmark-smoke and Docker
  gates; only the slow renderer remains pending at this checkpoint.
- Reprofiled eight workloads on hosted IR and Linux x86-64 native. All results
  matched expected values. JSMN remains the dominant code-size/compile-time
  shape; dynamic per-value attribution is unavailable.
- Decision: NO_VALID_TARGET_YET for production P5. P6 not started. Shutdown is
  authorized only after PR #173 merge and final report persistence.
- PR #173 natural CI finished green, including the 31m04s renderer, and merged
  at 1a775ba79f3abb6d3b33bb7d710ab67d0f808e18. Both production PR heads and
  merge ancestry are verified against origin/main.
- Final research reconciliation is now the only required persistence step
  before the authorized local Windows shutdown; no P5/P6 implementation is to
  be started.

## 2026-08-13 - P5 target selection v2 shipped

- Rebased independently from `origin/main=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18`.
- Profiled 15 workloads at O0/O1 with Linux native correctness evidence.
- Selected the bounded x86-64 immediate instruction-limit guard after a
  4.748% aggregate O1 instruction and 1.694% text reduction prototype.
- Implemented commit `a615d298b8d72f355a03e8abb2df5bd5a58d4758` in PR #174.
- Focused tests, exact-head full suite, Linux native, and all natural CI checks
  passed. PR #174 merged as `a08ee420e9bd0734a28363d60fc0f5f3e1169fb4`.
- P6 was not started. Shutdown remains unauthorized. The original checkout and
  its two pre-existing untracked artifacts remain preserved.

## 2026-08-13 - P6 simplicity-first discovery shipped

- Rebased from post-P5 `origin/main=a08ee420e9bd0734a28363d60fc0f5f3e1169fb4`
  and profiled 15 workloads across heavy-bottleneck and simplicity-first
  tracks.
- The selected local opportunity was non-F64 signed-imm32 `TCONST` lowering:
  7351 static one-use materializations, 7347 eligible, and 200250 eligible
  dynamic events. The direct destination write preserved initialized-state
  marking and avoided the temporary register only where sound.
- The first candidate full suite exposed one stale physical-residency test
  expectation. The narrow test-contract correction was followed by the exact
  final candidate suite with `FULL_SUITE_EXIT=0`.
- P6 implementation head is
  `b9ac7d9e8370f013889b8efc9acaed0429447ac2`, PR #175 merged as
  `69f5908687123a9ad7a4659b5133f815f08377b1`, and all 11 natural CI checks
  passed. Implementation and merge ancestry are verified against
  `origin/main`.
- Aggregate O1 native instructions changed `290658 -> 283311` and `.text`
  changed `16814716 -> 16667776`; memory operands, frame accesses, branches,
  and address calculations were unchanged. Runtime evidence remains
  characterization-only.
- P7 is not started and shutdown remains unauthorized. The original checkout
  and its two pre-existing untracked artifacts remain untouched.

## 2026-08-13 - P7 necessary vs accidental intermediates

- Reconciled post-P6 main at `69f5908687123a9ad7a4659b5133f815f08377b1` and
  preserved the original detached checkout plus its two untracked artifacts.
- Fresh 15-workload triage measured 566 static adjacent `TCMP`/`TBR3` pairs and
  66 dynamic executions. The direct-consumer result was classified conditional:
  liveness can prove the result dead after the branch, but successor observers
  retain the materialization.
- Implemented the narrow native x86-64 emitter fusion in PR #176. Focused
  tests, natural Linux CI, native numeric closure, and the complete CI filter
  union passed. The Windows full suite reached 100% with exit 1 only because
  two native numeric tests reject the Windows host; this limitation is retained.
- PR #176 merged as `631b51e70562a33183ac14d0be5bbe2ddd140779`; implementation
  and merge ancestry are verified against `origin/main`.
- Added `S3-ZK-0049`, `S3-EXP-0026`, the P7 reconciliation, external numbered
  reports, and final JSON. P8 and shutdown remain unauthorized.

## 2026-08-13 - P8.1 obligation frontier and first useful work

- Reconciled `origin/main=631b51e70562a33183ac14d0be5bbe2ddd140779` and
  preserved the original Windows checkout and its two pre-existing artifacts.
- Audited the two current workflows before any remote write. Feature and
  research branch pushes are safe under the static definitions; PR creation,
  main pushes and workflow dispatch remain prohibited. No Actions run was
  triggered.
- Validated the lab structurally and against a detached exact production
  checkout. Both validators exited 0.
- Validated a new exact-head 12-workload O1 emulator/Linux-native profile.
  All workloads matched expected results. The aggregate profile contained
  10,459 native instructions, 5,093 approximate load/store/address mnemonics,
  2,365 branches and 33 calls.
- Ran a nine-workload first-useful-work probe with 15 process launches per
  workload. All emulator/native results matched; launch/loader attribution
  remains open because cold-cache state and S3-controlled share were not
  isolated.
- Reproduced available local workflow responsibilities in the VM:
  compileall/golden, SSA/differential, native x86-64, instruction-limit E3,
  numeric closure, generated differential, benchmark contracts/smoke and
  Docker/project tests. Docker image construction was unavailable because the
  VM has no Docker executable; only Python 3.14 was installed locally.
- P8 promotion was falsified: initialization-state and checked materialization
  have real observers, but no path-complete removable subpopulation was proved.
  Added `S3-ZK-0050..0052`; no production code, branch, PR, full candidate
  suite, P9 or shutdown was started.
- A remote-write audit incident was discovered after the optional research
  persistence push: the production checkout's filtered `tests.yml` differed
  from the research branch's unfiltered `on: push:` definition. Run
  `31748403817` triggered on the research SHA and all jobs failed immediately
  under the exhausted Actions allowance. No rerun, retry, cancellation or
  further remote write was made. Research push safety is now `NO`.
- Workflow provenance containment was completed locally. The research
  `tests.yml` trigger was narrowed to the current production `main` branch and
  path policy without changing job bodies. A bounded fail-closed validator and
  controls A-F prove the old state as `ACTIONS_POSSIBLE` and the repaired local
  state as `PROVEN_ZERO_ACTIONS`; pull-request semantics remain `UNKNOWN` by
  design. Added `S3-ZK-0053` and `S3-EXP-0028`. The repair is reachable from
  `local/workflow-provenance-containment-20260813` but is intentionally not
  published while Actions allowance is exhausted.

## 2026-08-13 - P8.2 preserved possibilities and collapse points

- Reconciled the published containment checkpoint at `d852a611` with
  `origin/main=631b51e70562a33183ac14d0be5bbe2ddd140779`; the remote research
  branch contains the repair and repository Actions are disabled by policy.
- Audited the exact production anchor with a deterministic seven-file golden
  structural triage. It found the already-shipped conditional `TCMP->TBR3`
  family and no new adjacent memory/address/ternary roundtrip family.
- Built the possibility collapse ledger across representation, location,
  proof, control, address/memory, ABI, and ternary tracks. Initialization and
  memory-state materialization remain the strongest unresolved family, but
  P8.1 observer and failure witnesses prevent a path-complete safe rewrite.
- Compared the global possibility-set notation with local producer/consumer
  rules. The latter remain the simpler implementation model and no new target
  was promoted. P8.2 is `NO_VALID_TARGET_YET`; no production code, branch, PR,
  merge, full suite, benchmark, P9, or shutdown was started.

## 2026-08-13 - P8.3 path-complete memory-state necessity

- Reconciled stale state count 49 against 54 unique index/note IDs before
  assigning `S3-ZK-0055`; the next experiment ID was `S3-EXP-0030`.
- Profiled exact production HEAD `631b51e70562a33183ac14d0be5bbe2ddd140779`
  over 12 workloads at O0/O1. The simple CFG/use-def worklist fixed point
  converged and three focused model-control tests passed.
- Static census: 1587 sites; dynamic tracking: 4350 events. The largest
  bounded accidental family was definite `REGISTER_INIT_CHECK`, 1660 events
  across 11 workloads. Static unknown share was 20.163831127914303%; dynamic
  unknown share was 1.1954022988505748% of observed events.
- Linux native profile passed all 24 O0/O1 pairs. The two `slice_reference`
  emulator pairs were recorded as unsupported at TADDR, not treated as zero.
- No native structural effect was measured. Public runtime proof transport and
  exact fallback are missing, so P8.3 is `NO_VALID_TARGET_YET`; no production
  code, branch, PR, full suite, benchmark, P9 or shutdown was started.

## 2026-08-14 - P8 final proof-guided native initialization-check elision

- Reconciled P8.4's bounded transport/recompute comparison with the exact
  production candidate `87eb49cd19a78570f07d66ce7982650c8b422210`, based on
  `631b51e70562a33183ac14d0be5bbe2ddd140779`.
- The candidate computes a fail-closed definite register-initialization set at
  the native consumer. It does not add public proof metadata; calls,
  references, slices, address-taken registers, unsafe joins/loops and unknown
  facts retain the existing checked path.
- P8.3 population matched exactly: 416 safe static sites and 1660 dynamic
  events. The native consumer used 402 sites and 1558 events. All 24 Linux O0/O1
  pairs preserved semantics. Aggregate native checks changed 550->148,
  instructions 20903->20099, branches 4746->4344, text 107709->102646, while
  loads/stores stayed 10175.
- The persistent exact-head Linux full suite exited 0. The earlier SSH timeout
  is classified as external harness interruption, not product failure. PR #178
  was merged as `5dd6844607ba3a2d5830ed836fb9026eed86d0fb`; implementation and
  merge ancestry both passed. Post-merge focused smoke passed on origin/main.
- Actions permissions remained disabled and no candidate-branch run existed.
  Runtime and compile-time measurements remain unavailable/not-comparable. P9
  and reboot were not started.
