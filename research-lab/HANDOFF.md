# S3 Research Handoff

## 2026-09-19 current overlay — native self-hosting frontend

This overlay supersedes older "next" wording in this handoff when discussing current execution priority.

Current production/self-hosting work has advanced beyond the August research snapshot:

- PR #301 (Draft): native source-frontend expression core through integer literals, `+`, `*`, precedence, associativity and grouping; Linux x86-64 focused 34 passed; full suite PASS on functional head `5230f92281e482a30fee8d116fb29d6932483fe1`; no hosted-parser fallback.
- PR #302 (Draft, stacked on #301): native identifier expressions integrated with binary expressions, precedence and grouping; Linux x86-64 focused 36 passed; full suite PASS on functional head `0cceff303f0337fe45db9b80a2e7b6e814ff979e`; no hosted-parser fallback.
- Next parser blocker: `NATIVE_STATEMENT_SEQUENCE`.
- Remote GitHub Actions remain blocked before step execution by runner/provisioning infrastructure; this is not classified as a test failure.
- Process correction: the September implementation advanced without updating this Research Lab. Decision D-009 and the campaign knowledge-closure protocol now require meaningful campaigns to feed successes, failures, negative results and unknowns back into the Zettelkasten.
- Operational correction: avoid one PR/research ceremony per microscopic grammar feature. Keep semantic milestones internally, but group related work into coherent self-hosting campaigns with focused intermediate validation and consolidated knowledge closure.

Canonical detailed reconciliation:

`research-lab/reconciliations/SELFHOST_FRONTEND_20260919.md`

Current speculative language-design idea:

`IC-014` records implicit function signatures / semantic type inference separately from numeric representation-width selection. It is deferred and must not alter the stable self-hosting target.

### 2026-09-20 update — PR #303 statement sequence complete

PR #303 is now an open Draft on `feat/s3-native-statement-sequence`, stacked on #302.

```text
FUNCTIONAL_HEAD=fa379629a7491458ca3a6d9a567ef7fe01eb5885
FINAL_HEAD=6231eb676ea3f8a67461a2bd2d6db82aea753f86
FINAL_DELTA=DOCS_ONLY

NATIVE_STATEMENT_SEQUENCE=PASS
VARIABLE_STATEMENT_COUNT=PASS
STATEMENT_ORDER_PRESERVED=PASS
BLOCK_BOUNDARY=PASS
TRAILING_SOURCE_REJECTION=PASS
LINUX_NATIVE=55 passed
FULL_SUITE=PASS
REFERENCE_FALLBACK=NONE
```

The native parser frontier is now `PARTIAL_EXPRESSION_CORE_WITH_IDENTIFIERS_AND_STATEMENT_SEQUENCE`.

Remote CI again failed before step execution (10 jobs in 2–3 seconds with `steps=[]`); no remote test executed and no rerun was performed. Treat this as infrastructure dispatch failure, not code failure.

The next technical blocker is `NATIVE_LOCAL_BINDING`, but the process boundary changes here: #303 is the last intentionally microscopic frontend PR. The next phase is one larger `NATIVE_PROGRAM_FRONTEND` campaign with internal semantic milestones, focused intermediate tests, broader checkpoint validation and consolidated knowledge closure.

Detailed reconciliation:

`research-lab/reconciliations/SELFHOST_STATEMENT_SEQUENCE_20260920.md`

---


This is the durable context document for continuing S3 compiler research in another ChatGPT/Codex conversation.

## 1. Project identity

Production repository:

```text
https://github.com/SamDevlab/S3
```

Long-lived research branch:

```text
research/zettelkasten-lab-20260812
```

Durable locator:

```text
GitHub issue #171 — [Research] S3 Zettelkasten compiler research lab
```

**Never merge the research branch directly into `main`.** Proven ideas are ported selectively to a fresh production branch from then-current `origin/main`.

## 2. Production state after P4

Historical lab creation anchor:

```text
MAIN_AT_LAB_CREATION=a83e25c3364302227694399ebe12946f887c0ead
```

Completed performance milestones:

```text
P1=COMPLETE
P2=COMPLETE
P3=COMPLETE
P4=COMPLETE
P5_STARTED=NO
```

P4:

```text
P4_PR=170
P4_BASE_SHA=a83e25c3364302227694399ebe12946f887c0ead
P4_IMPLEMENTATION_HEAD=59df1d0f9ab9147b8d7f71a1db395c5fab560171
P4_MERGE_COMMIT=a0b694fadc985c0b8e0944fb7844e14f72a838d8
MAIN_AFTER_P4=a0b694fadc985c0b8e0944fb7844e14f72a838d8
```

P4 exact-head Linux full suite passed with exit 0; natural CI was terminal/green; implementation and merge ancestry were verified.

A future session must fetch current `origin/main`; the SHA above is an historical production anchor, not a promise that main has not advanced.

## 3. Capability history

M1.32–M1.38 remain complete:

- Numeric Domains & Large Indexing
- Borrowed Slices
- Foreign ABI, Library Mode & Zero-Copy
- Owned Dynamic Runtime Data
- Linux Host Services & Foreign Tool Interop
- Project & Container-Native App Model
- S3 Docker V1

Do not reopen these capability milestones merely because optimization work reveals implementation opportunities.

## 4. Performance history

### Post-M1.38

Forensics established massive representation/lowering expansion versus GCC O2. Primary conclusion: backend/codegen immaturity rather than a fundamental language tax.

### P1 — Compact Indexed Access & Bounds Lowering

Historical representative structural change:

```text
.text:               320689 -> 313169
static instructions: 55271  -> 53767
branches:            13197  -> 12445
loads/stores:         27873 -> 27873
```

Bounds/control expansion was real; memory traffic remained.

### P2 — Value Locality & Representation Staging Reduction

Same-basic-block eligible scalar forwarding removed targeted frame MOVs but barely moved aggregate counters.

### P3 — Cross-Block Value Lifetime & Frame Canonicalization

Conservative cross-block scalar residence removed further targeted frame operations but aggregate counters again moved little. Post-P3 primary remaining diagnosis was frame canonicalization/store-reload traffic with phi/SSA staging secondary; true RA spilling was not established as primary.

### P4 — Global Value Residency as Native Default

P4 produced an important causal correction to the research model.

The existing allocator was already whole-function, CFG-liveness-aware, interference-based and deterministic. The major early collapse was that native x86-64 backend register allocation still defaulted OFF.

P4 established:

```text
EARLIEST_LOCATION_FLEXIBILITY_LOSS=
X8664Backend.register_allocation default false

EARLIEST_MEMORY_IDENTITY_LAYER=
emitter frame canonicalization after the default backend selected RA_OFF

RA_PRIMARY_CAUSE=NO
```

Selected production transformation:

```text
make the existing liveness-backed register allocator the native default
while preserving register_allocation=false as explicit stack-backed fallback
```

No allocator redesign, phi rewrite or Assembly IR redesign was required.

Final P4 corrections also resolved local TMOV aliases in call snapshots and skipped dead incoming parameters during physical entry initialization.

Direct structural evidence:

```text
TARGET_OPPORTUNITIES=13
TARGET_TRANSFORMED=13
COVERAGE_RATIO=1.0

FRAME_LOADS:  1549 -> 491
FRAME_STORES: 1520 -> 471

TOTAL_FRAME_ACCESSES: 9282 -> 7175
METADATA_ACCESSES:     5638 -> 5638

TEXT_BYTES:            313169 -> 305543
STATIC_INSTRUCTIONS:    53767 -> 53922
```

Important metric nuance:

```text
GCC-relative geomean:
34.708283588x -> 38.975981467x

absolute S3 runtime:
8890.413541 ns/parse -> 8405.052702 ns/parse
S3_RUNTIME_DELTA=-5.46%
```

The GCC denominator varied, so the relative ratio is characterization only. Absolute S3 runtime improved ~5.46% in the recorded P4 protocol. Compiler median time improved ~2.92%.

P4 residual:

```text
RESIDUAL_PRIMARY_BOTTLENECK=REPEATED_MEMORY_STATE_MATERIALIZATION
NEXT_RECOMMENDED_TARGET=SSA_DESTRUCTION_AND_MEMORY_STATE_METADATA_STAGING
P5_STARTED=NO
```

See:

```text
research-lab/reconciliations/P4_20260812.md
```

## 5. Revised RA rule

Do not conflate:

```text
RA_ENABLEMENT
RA_INPUT_QUALITY
RA_ALGORITHM_QUALITY
TRUE_SPILL_BEHAVIOR
EMITTER_USE_OF_ALLOCATION
```

P4 showed that allocator enablement/default policy was a major causal variable while allocator algorithm quality was **not** established as primary.

A future RA redesign is justified only if true allocator spills become a measured dominant residual after upstream/default-policy and metadata-state problems are separated.

## 6. Current research problem after P4

The immediate question is no longer simply “why are values frame-backed?”

P4 greatly reduced ordinary value frame traffic but left:

```text
METADATA_ACCESSES=5638 -> 5638
```

Therefore the next research question is:

> Why are memory/initialized-state metadata repeatedly materialized, and what fraction originates in SSA destruction/phi/loop-carried staging versus later memory-state bookkeeping?

Treat these as separate state spaces until evidence proves they should be unified:

```text
LOGICAL_VALUE_STATE
MEMORY_VALIDITY_STATE
INITIALIZATION_STATE
SSA_MERGE_STATE
ABI/OBSERVABILITY_STATE
```

Do not start P5 production implementation until this attribution is quantitative.

## P5-AUDIT result — 2026-08-12

P5-AUDIT was completed as research only on a clean detached worktree at
`a0b694fadc985c0b8e0944fb7844e14f72a838d8`. `origin/main` was unchanged and
the P4 merge remained an ancestor.

The P4 probe's `5638` metadata number is a lexical count of every native line
containing `byte ptr [rbp`. Independent region-aware analysis reproduced the
number in RA_OFF and RA_ON and decomposed it into:

```text
register initialization bytes = 4589
memory initialization bytes   = 837
trit payload bytes             = 212
```

The true initialization/definedness population is therefore `5426`; the `212`
payload operations are user data included by the broad metric. The JSMN
candidate has `34` backedges but `0` phis, `0` phi-edge copies and `0` critical
edges. SSA destruction is not dominant for that corpus, although a phi-heavy
corpus is still required before generalizing.

The native emitter has explicit initialized bytes but no independent memory-
validity bit. A dual-validity/reduced-product model is useful for research
because a physical value may be current while its canonical frame value is
stale until a call/address observer. Exact required/avoidable shares, dead
metadata stores, true spill traffic and dynamic weights remain open.

Recommended future production capability, not started here:

```text
P5 - Proof-Preserving Initialization State and Lazy Materialization
```

See `research-lab/reconciliations/P5_AUDIT_20260812.md` and the external
`production-reports/performance-p5-memory-state-forensics/` directory. No
production code, PR, full suite, benchmark, CI gate, P6 or shutdown was
started.

## 7. Testing/process rules

- Correctness/equivalence/safety/exact-head evidence are gates.
- Performance benchmarks are characterization, not correctness gates.
- Development uses focused/native/differential/codegen tests.
- Expensive full suite only for a coherent production merge candidate.
- A production HEAD change invalidates previous exact-head full-suite evidence.
- Natural CI and full-suite evidence are distinct unless equivalence is factually proven.
- Do not rerun slow CI merely because it is slow.
- Preserve first failure; classify/root-cause/minimum-correct/retest.
- Linux-native evidence mandatory for Linux-native backend changes.
- One production milestone = one coherent capability = one PR. No stacking.
- Research prototypes use focused mathematical/semantic checks; production promotion re-enters normal gates.

## 8. Research methodology — Zettelkasten

Permanent IDs:

```text
S3-ZK-0001 ...
S3-EXP-0001 ...
```

Types include SOURCE, PERMANENT, BRIDGE, QUESTION, HYPOTHESIS, EXPERIMENT, NEGATIVE_RESULT and ARCHITECTURE.

Rules:

- one Zettel = one atomic idea;
- separate source-established facts from S3 inference and measurement;
- a hypothesis needs a measurable falsifier/experiment;
- negative results/counterexamples are durable knowledge;
- exact/exponential algorithms are welcome as bounded research oracles;
- do not promote a striking demo directly to production maturity.

After P4 reconciliation the index contains **31 notes**.

P4 added/refined:

```text
S3-ZK-0028 configuration can itself be an information-loss boundary
S3-ZK-0029 causal metric hierarchy: structural/absolute/relative metrics stay distinct
S3-ZK-0030 memory-state metadata is a distinct optimization state space
S3-ZK-0031 RA enablement and RA quality are different causal variables
```

## 9. Three flexibility dimensions

The long-term research architecture remains:

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF_KNOWLEDGE_FLEXIBILITY
```

Working model:

```text
LOGICAL VALUE
   |
   +-- semantic facts
   +-- legal representations
   +-- legal locations/materialization states
   +-- proof/validity facts
   |
constraints accumulate
   |
irreversible choices delayed until required
   |
representation + materialization + physical resource assignment
```

This remains a research architecture, not an accepted production design.

P4 supports one part of it: default-off RA was an avoidable premature collapse. P4 does **not** prove that every memory state should be delayed or that min-cut/global optimization is the right production solution.

## 10. Ternary virtualization research

The user explicitly wants S3 ternary logic/virtualization explored as a potentially disruptive direction.

Core rule:

> Do not assume `trit` is merely a tiny binary integer. Preserve exact current S3 trit semantics first; choose physical encoding later if evidence supports it.

Current ternary research includes:

```text
S3-ZK-0016 semantic ternary abstraction
S3-ZK-0017 representation flexibility
S3-ZK-0018 ternary primitive-basis synthesis
S3-ZK-0019 semantic state minimization
S3-ZK-0020 partition information dependencies
S3-ZK-0023 ternary virtual ISA
S3-ZK-0024 representation conversion graph
```

Hypothesis document:

```text
research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
```

Hard constraints:

- current S3 semantics are source of truth;
- do not call S3 Łukasiewicz/Kleene/Post logic until exact truth tables are compared;
- quantum/DNA sources are representation/architecture inspiration, not a backend commitment;
- dense base-3/packed/vector forms require cost evidence;
- representation selection must preserve S3 safety/provenance semantics.

## 11. Information/proof preservation research

Current notes include:

```text
S3-ZK-0021 compiler information-loss metrics
S3-ZK-0022 proof-carrying optimization facts
S3-ZK-0025 bounded compiler fact/proof language
S3-ZK-0027 information-lossless lowering contracts
S3-ZK-0028 configuration information loss
S3-ZK-0030 metadata materialization state space
```

Use information theory carefully:

- Shannon entropy/mutual information require a defined probability model;
- otherwise prefer deterministic quantities such as legal-representation count, equivalence partitions, recoverability and partial-order precision;
- do not create decorative entropy metrics.

## 12. Literature corpus

PDFs/EPUBs are **not committed to GitHub**.

Canonical bibliography and deduplication registry:

```text
research-lab/sources/REGISTRY.md
```

It currently tracks 25 canonical sources, including compiler/dataflow references, abstract interpretation, SSA, automata, many-valued logic, term rewriting, decision procedures, quantitative architecture, combinatorial/convex/numerical optimization and parameterized algorithms.

Future uploads must be classified as NEW, EXACT_WORK_REUPLOAD, EDITION_VARIANT or TOPIC_OVERLAP before new Zettels are created.

## 13. Experiments

`S3-EXP-0002 RA OFF vs RA ON` is no longer an unresolved top-level question: P4 production evidence established the key causal result.

Highest-value unresolved sequence now is:

```text
memory-state metadata provenance
        +
SSA destruction / phi / loop staging attribution
        +
compiler-boundary information-loss audit
        ↓
select P5 production target
```

Ternary experiments remain parallel research:

```text
S3-EXP-0009 exact current trit semantics/lowering map
S3-EXP-0010 ternary operation-basis exact oracle
S3-EXP-0011 ternary/finite-state minimization
S3-EXP-0012 ternary representation conversion graph
S3-EXP-0013 compiler information-loss boundary audit
```

Do not let ternary research delay a clearly measured production bottleneck, and do not merge speculative ternary architecture into P5 unless causal evidence connects it.

## 14. Research prototypes already present

Under `research-lab/prototypes/`:

- generic CFG;
- backward fixed-point liveness;
- residence lattice checks;
- binary materialization min-cut;
- exact binary placement oracle;
- Lagrangian capacity relaxation;
- exact multi-value oracle;
- matroid/submodularity counterexample tools;
- S3 Assembly adapter;
- S3 value trace scaffold/CLI.

Ternary semantic mapper, ternary basis oracle, ternary representation oracle, information-loss boundary auditor, metadata provenance auditor and SSA-destruction attribution tooling are planned/not yet established unless later files say otherwise.

## 15. Promotion criteria

A research idea becomes promotable only with:

```text
clear compiler problem
formal/operational model
correctness/safety argument
prototype
positive + negative/counterexample tests
measured opportunity coverage
generality beyond one benchmark
bounded production complexity
comparison against simpler alternatives
```

Then create a fresh production branch from current `origin/main` and port only the winning mechanism.

## 16. How to resume in a new chat

Tell the new assistant to open `SamDevlab/S3` branch `research/zettelkasten-lab-20260812` and read, in order:

```text
research-lab/HANDOFF.md
research-lab/STATE.json
research-lab/NEW_CHAT_PROMPT.md
research-lab/RESEARCH_PROTOCOL.md
research-lab/reconciliations/P4_20260812.md
research-lab/zettelkasten/INDEX.md
research-lab/sources/REGISTRY.md
research-lab/experiments/README.md
research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
```

Then independently inspect current `origin/main`.

Do not merge the research branch directly to main. Continue from evidence and update durable state whenever a production milestone or major research result changes.

## 17. P5-PREWORK dynamic observability — 2026-08-12

The P5-PREWORK campaign is research-only and complete. It reproduced the
P5-AUDIT lexical metric exactly on origin/main at
a0b694fadc985c0b8e0944fb7844e14f72a838d8: 5638 byte-frame lines, decomposed
into 4589 register-initialization, 837 memory-initialization and 212 trit
payload accesses. The true initialization-state population is 5426.

Temporary emitter/runtime counters were used only in a disposable worktree
and reverted. They recorded register/memory initialization reads and writes,
trit payload reads/writes, function/block/opcode and observer class, with output
isolated on Linux fd 3. Exact JSMN produced 21221 weighted initialization
events, including 356 direct initialization-check events and 14367 allocated
memory reset events. A deterministic repeat matched.

The direct semantic classification is intentionally bounded: 324/5426 static
accesses and 356/21221 JSMN dynamic events have proven check outcomes. The
remaining populations are UNKNOWN/UNMEASURED, not conditionally removable.
Focused call, reference/address, slice, numeric and phi-heavy corpora were
collected. Native paths passed; hosted emulator differential remains partial
because TADDR is unsupported.

P5_PREWORK_STATUS=COMPLETE
PROMOTION_DECISION=MORE_RESEARCH_REQUIRED
P5_STARTED=NO
P6_STARTED=NO
PRODUCTION_CODE_COMMITTED=NO
PRODUCTION_PR_OPENED=NO
FULL_SUITE_RUN=NO
BENCHMARK_RUN=NO
SHUTDOWN_AUTHORIZED=NO

Do not start production P5 from the reset hotness alone. The next research
questions are observer-frontier closure, reset/store deadness, proof-preserving
metadata propagation, and hosted TADDR support.

## 18. P5-RESEARCH-CLOSURE - 2026-08-12

The closure campaign reproduced the 5426 true initialization-state population,
21221 exact JSMN dynamic initialization events and 14367 allocated-memory reset
bytes. A temporary native trace classified 13340 bytes as directly required by
an uninitialized-memory observation, 1024 as overwrite-before-direct-observer
candidates and 3 as lifetime-end candidates. These latter two classes remain
conservative candidates, not semantic deadness proofs.

The temporary hosted TADDR support passed six O0 native/emulator corpus
comparisons, including reference and a valid mutable slice. It was discarded;
production Assembly emulation remains unchanged. The existing O1 slice
optimizer verifier error was recorded as a limitation rather than changed.

```text
P5_RESEARCH_CLOSURE=COMPLETE
PROMOTION_DECISION=MORE_RESEARCH_REQUIRED
RESET_SEMANTIC_CLASSIFICATION_COVERAGE=UNAVAILABLE
PRODUCTION_CODE_COMMITTED=NO
PRODUCTION_PR_OPENED=NO
FULL_SUITE_RUN=NO
BENCHMARK_RUN=NO
P5_STARTED=NO
P6_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

Canonical external report:
`C:/Users/samue/Downloads/S3/production-reports/performance-p5-research-closure-20260812/FINAL_P5_RESEARCH_CLOSURE.md`

## 19. CI cost audit and O1 correction campaign - 2026-08-13

The campaign `CI_COST_TEST_AUDIT_AND_CONDITIONAL_P5` audited the Actions API,
the pytest collection, the O1 slice failure and the current post-P4 backend.

```text
API_RUNS=591
API_JOBS=5506
API_JOB_MINUTES=22356.616667
USER_METER_MINUTES=25340
USER_GROSS_USD=152.04
TEST_COLLECTION_TOTAL=2709
DUPLICATE_TEST_EXECUTIONS=4740
NON_MAIN_TESTS_PUSH_MINUTES=12274.700000
RESEARCH_BRANCH_MINUTES=3716.766667
DUPLICATED_PUSH_SIDE_MINUTES=8068.350000
```

The O1 slice issue was real metadata loss in SSA-to-IR lowering. PR #172,
implementation `19b39c71fb644d2f4d923d1695eb3ac43e7e49e7`, passed both natural
CI runs and merged as `229811359948cf8e12848036882edaa89108a9fa`. It is a
correctness correction, not a performance P5.

The single CI-efficiency PR is:

```text
CI_OPTIMIZATION_PR=173
CI_OPTIMIZATION_HEAD=ae278bfdec2c9b957a1d885c2076d37f58f97df2
CI_OPTIMIZATION_MERGE=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18
ORIGIN_MAIN_END=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18
```

It restricts Tests pushes to main, keeps executable PR paths, adds PR-only
concurrency cancellation, enables official pip caching and narrows M1.38
Docker paths. Native, differential, SSA, Python 3.11/3.12/3.13, benchmark
smoke and Docker gates are preserved. The modeled trigger replay reduction is
54.94% of historical Tests minutes; concurrency/cache gains are not added.

The post-P4 reprofile covered JSMN, numeric integer, nested loop,
branch-heavy, call-heavy, slice/reference, f64 and trit-heavy workloads. All
passed hosted IR and Linux x86-64 native execution. JSMN remains the largest
shape, but the metadata/reset population is not proven removable and sound
dynamic per-value attribution is unavailable.

```text
P5_SELECTION=READY_FOR_IMPLEMENTATION
P5_STARTED=YES
P5_IMPLEMENTED=YES
P5_PR=174
P5_HEAD=a615d298b8d72f355a03e8abb2df5bd5a58d4758
P5_MERGE=a08ee420e9bd0734a28363d60fc0f5f3e1169fb4
P6_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The external campaign evidence is under:

```text
C:/Users/samue/Downloads/S3/production-reports/github-actions-efficiency-20260812/
C:/Users/samue/Downloads/S3/production-reports/ci-p5-autonomous-campaign-20260812/
```

The #173 gate is terminal green and the PR is merged. The fresh P5 v2 campaign
then selected, implemented, and merged the bounded instruction-limit immediate
guard in PR #174. The factual merge SHA is in `STATE.json`, this handoff and
the external P5 JSON. Push the research branch after the document updates,
verify the original checkout is preserved, and do not start P6 or issue a
shutdown command.

## Current P6 closure - 2026-08-13

The preceding P5 handoff is historical. P6 was subsequently profiled,
implemented, validated, and merged as PR #175. The selected capability was
`P6_DIRECT_NON_F64_TCONST_IMMEDIATE`, using the existing destination writer for
signed-imm32 non-F64 constants while retaining the wide/F64 fallback.

```text
P6_SELECTION=READY_FOR_IMPLEMENTATION
P6_STARTED=YES
P6_IMPLEMENTED=YES
P6_PR=175
P6_HEAD=b9ac7d9e8370f013889b8efc9acaed0429447ac2
P6_MERGE=69f5908687123a9ad7a4659b5133f815f08377b1
P6_FULL_SUITE_HEAD=b9ac7d9e8370f013889b8efc9acaed0429447ac2
P6_FULL_SUITE_EXIT=0
P6_LINUX_NATIVE=PASS
P6_CI=PASS
P6_P7_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The first candidate full-suite failure was a stale physical-residency test
expectation; it was corrected narrowly, and the exact final candidate suite
passed. P6 reduced aggregate O1 native instructions from 290658 to 283311 and
`.text` from 16814716 to 16667776; memory operands, frame accesses, branches,
and address calculations were unchanged. No runtime speedup is claimed.

The original checkout remains preserved with its two pre-existing untracked
artifacts. Do not start P7, do not merge this research branch into production,
and do not issue a shutdown command.

## Authoritative P7 closure - 2026-08-13

The preceding P6 block is historical. P7 was profiled, implemented, validated,
and merged as PR #176. The selected capability was
`P7_DIRECT_TCMP_BRANCH_LOWERING`: a same-block liveness-gated direct branch for
an adjacent `TCMP`/`TBR3` pair, with the old materializing fallback whenever a
successor can observe the result.

```text
P7_SELECTION=READY_FOR_IMPLEMENTATION
P7_STARTED=YES
P7_IMPLEMENTED=YES
P7_PR=176
P7_HEAD=b118917ec5a5284899d27b1838712b2e04364caf
P7_MERGE=631b51e70562a33183ac14d0be5bbe2ddd140779
P7_LINUX_FULL_SUITE_SOURCE=CI_SHARDED_EQUIVALENT
P7_LINUX_FULL_SUITE_EXIT=0
P7_WINDOWS_FULL_SUITE_EXIT=1_PLATFORM_LIMITATION
P7_CI=PASS
P7_IMPLEMENTATION_ANCESTOR=YES
P7_MERGE_ANCESTOR=YES
P8_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

Fresh evidence found 566 static eligible pairs and 66 dynamic executions. The
Windows full suite reached 100% but its two Linux-native numeric tests
correctly rejected the Windows host; natural Linux CI, including numeric
closure and the complete unit/renderer/benchmark filter union, provided the
canonical full-suite-equivalent proof. No new comparable runtime measurement
was made.

The P7 external evidence is under:

```text
C:/Users/samue/Downloads/S3/production-reports/p7-necessary-vs-accidental-intermediates-20260813/
```

Do not start P8 or issue a shutdown command. Preserve the original checkout's
two untracked artifacts and keep the production branch available for audit.

## Workflow provenance containment - 2026-08-13

P8.1 remains complete with `P8_SELECTION=NO_VALID_TARGET_YET`; P9 remains
unauthorized. A later read-only reconciliation found that the research ref's
`tests.yml` had an unrestricted `push` trigger even though the exact production
main workflow was filtered to `main` and production-relevant paths. The push
of `06ed79449dcd917c3213570389a3639f6ad0be24` consequently created Actions run
`31748403817`, which failed immediately under the exhausted allowance. No
rerun, retry, cancellation, or further remote write followed discovery.

The direct cause was the research workflow trigger; the process cause was
auditing `main` instead of the workflow state of the proposed target ref; the
control gap was the absence of a remote-write automation provenance gate in
`validate_lab.py`. The durable research branch was repaired and published at
`d852a611f0c824436c736ff380d5cfb33d86feb5`; repository-level Actions are now
disabled and no new run followed publication.

The isolated local branch
`local/workflow-provenance-containment-20260813` contains the published
repair. Its `tests.yml` now restricts `push` to `main` with the current
production path policy, while preserving the research branch's job bodies.
`m138-docker.yml` already restricted `push` to `main` and was not changed.

`research-lab/tools/validate_remote_write.py` models the bounded push trigger
surface using workflow files from the proposed head, the target ref, and the
computed diff. It classifies the old push as `ACTIONS_POSSIBLE` and the local
repaired candidate as `PROVEN_ZERO_ACTIONS`; malformed or unsupported inputs
are `UNKNOWN` and non-zero. This is a local proof, not write authorization.

```text
LOCAL_REPAIR_BRANCH=local/workflow-provenance-containment-20260813
REMOTE_PUBLICATION_PENDING=NO
REMOTE_WRITES_THIS_CAMPAIGN=0
GITHUB_ACTIONS_RUNS_TRIGGERED_THIS_CAMPAIGN=0
P8_STARTED=NO
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

## P8.2 checkpoint: preserved possibilities

The containment repair was subsequently published at `d852a611` to
`research/zettelkasten-lab-20260812`. Repository-level Actions are disabled;
the remote run count after publication is zero. The exact production anchor is
`631b51e70562a33183ac14d0be5bbe2ddd140779`.

P8.2 completed a bounded possibility-collapse audit and recorded
`S3-EXP-0029`, `S3-ZK-0054`, and
`reconciliations/P8_2_PRESERVED_POSSIBILITIES_20260813.md`. The ledger is a
research notation only. Initialization and memory-state materialization remain
the strongest unresolved family, but observer/failure/alias/call/successor
witnesses prevent promotion. The simplicity challenger remains local
producer/consumer rules.

```text
P8_2_STATUS=COMPLETE_NO_VALID_TARGET_YET
P8_SELECTION=NO_VALID_TARGET_YET
P8_STARTED=NO
PRODUCTION_CODE_CHANGED=NO
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

Before any future P8 implementation, run one bounded path-complete
observer-aware attribution experiment. Do not reopen broad compiler triage or
start P9.

## P8.3 checkpoint: path-complete memory-state necessity - 2026-08-13

P8.3 completed the bounded experiment on exact production HEAD
`631b51e70562a33183ac14d0be5bbe2ddd140779`. The fixed-point CFG/use-def model
and emulator boundary tracker passed three focused control tests, 12 workloads,
and 24 Linux native O0/O1 pairs. The largest bounded accidental family was
definite register initialization checks, but this is an emulator-only safety
check with no measured native reduction. Calls, references, slices, failure
paths, loops and aliases remain conservative, and TADDR is an explicit emulator
observability gap.

```text
P8_3_STATUS=COMPLETE_NO_VALID_TARGET_YET
P8_SELECTION=NO_VALID_TARGET_YET
P8_STARTED=NO
PRODUCTION_CODE_CHANGED=NO
FULL_SUITE_RUN=NO
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The authoritative experiment is `S3-EXP-0030`, the new zettel is
`S3-ZK-0055`, and the reconciliation is
`reconciliations/P8_3_MEMORY_STATE_NECESSITY_20260813.md`. Do not reopen this
hypothesis without proof-bearing Assembly transport, checked fallback, and a
measured emulator-cost benefit.

## Authoritative current checkpoint: P8 complete - 2026-08-14

P8 is now a real merged production capability, not the earlier P8.3 negative
research checkpoint. The final mechanism is bounded fail-closed native
recomputation of definite register initialization at the x86-64 native
consumer. Generic proof transport was tested and rejected as unnecessary; the
public Assembly/verifier trust boundary is unchanged.

```text
P8_NAME=P8_PROOF_GUIDED_NATIVE_INIT_CHECK_ELISION
P8_BASE=631b51e70562a33183ac14d0be5bbe2ddd140779
P8_IMPLEMENTATION_HEAD=87eb49cd19a78570f07d66ce7982650c8b422210
P8_PR=178
P8_MERGE=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
ORIGIN_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
RESEARCH_HEAD_FINAL=9b8718e290653d1f6f8026a983f28cdb7c452313
P8_IMPLEMENTATION_ANCESTOR=YES
P8_MERGE_ANCESTOR=YES
P8_FULL_SUITE_HEAD=87eb49cd19a78570f07d66ce7982650c8b422210
P8_FULL_SUITE_EXIT=0
P8_ACTIONS_ENABLED=NO
P8_NEW_ACTIONS_RUNS=0
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
REBOOT_EXECUTED=NO
```

P8.3's 416 static safe sites and 1660 dynamic events were reproduced exactly;
402 sites and 1558 events reached the native consumer. Across 24 Linux O0/O1
pairs, semantics matched baseline. Aggregate initialization checks fell
550->148, static instructions 20903->20099, branches 4746->4344 and text
107709->102646; loads/stores remained 10175. Runtime and compile-time values
are unavailable under a directly comparable protocol and must not be inferred.

The durable P8.4 result is in `S3-EXP-0031`, `S3-ZK-0056`, and
`reconciliations/P8_FINAL_PROOF_GUIDED_INIT_ELISION_20260814.md`. Do not start
P9 or reboot from this checkpoint.

## Authoritative current checkpoint: P9 selection closed - 2026-08-14

P9 selection research is complete and did not authorize a production target:

```text
P9_CAMPAIGN=P9_CAUSAL_FRAME_REPRESENTATION_ATTRIBUTION_V1
P9_SELECTION=NO_VALID_TARGET_YET
P9_STATUS=COMPLETE_RESEARCH_ONLY
P9_STARTED=NO
P9_PRODUCTION_COMPILER_CHANGED=NO
P9_BENCHMARK_RERUN=NO
P9_ACTIONS_EXECUTION=NO
SHUTDOWN_AUTHORIZED=NO
```

The experiment `S3-EXP-0032` used the frozen P8 and benchmark evidence and a
validated `MODELLED_NATIVE_DYNAMIC_COUNT` sidecar, not a hardware counter. It
covered nine internal workloads and six frozen JSMN fixtures. The O1 model
total was 143151; frame-value traffic was 7807 and observed stack-resident
frame-value traffic was 5431, exactly 3.793895956018% of the model. Direct
indexed addressing falsified the current fixed-array base-reload hypothesis.
Stack residency did not establish spill causality, and register allocation is
not promoted automatically.

The strongest candidate to carry forward is the bounds-validity contract
surface. The smallest next experiment is a proof-bearing loop-carried
TLOAD/TSTORE bounds and validity sharing or hoisting analysis preserving
initialization, immutability, instruction-limit, failure-order and checked
fallback obligations. It is not part of this checkpoint. Read
`reconciliations/P9_TARGET_SELECTION_CAUSAL_FRAME_20260814.md`,
`experiments/S3-EXP-0032-p9-causal-frame-representation-attribution.md`, and
`zettelkasten/notes/S3-ZK-0057.md` before any future work.

## Authoritative current checkpoint: P9.1 closed - 2026-08-14

P9.1 bounds/validity attribution is complete research only:

```text
P9_1_CAMPAIGN=P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_V1
P9_1_STATUS=COMPLETE_RESEARCH_ONLY
P9_1_SELECTION=NO_VALID_TARGET_YET
P9_1_STARTED=NO
P9_1_RESEARCH_PUBLICATION_COMMIT=05f08dcf574ff2ab4bab4539e74d6136ef3fd45c
P9_1_RESEARCH_HEAD_AT_PUBLICATION=05f08dcf574ff2ab4bab4539e74d6136ef3fd45c
MODELLED_NATIVE_DYNAMIC_COUNT_REPRODUCED=YES
MODELLED_DYNAMIC_TOTAL=289500
WORKLOADS=15
SAFETY_RELATED_DYNAMIC=65224
BOUNDS_DYNAMIC=17464
VALIDITY_DYNAMIC=6660
AVOIDABLE_DYNAMIC=0
UNKNOWN_DYNAMIC=26456
NATIVE_FOCUSED=PASS
PRODUCTION_COMPILER_CHANGED=NO
EXTERNAL_BENCHMARK_RERUN=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
REMOTE_WRITE_PROVENANCE=PROVEN_ZERO_ACTIONS
P9_2_RESEARCH_HEAD_FINAL=5717ca0aa03a8c54bb69007ac412ba528f143280
```

The safety family is material, but no minimum local fact model established a
proven reusable object/index/length subset. The first observed boundary is
the Assembly-to-emitter range-fact contract, where control shape exists but
no explicit range fact is serialized. The strongest future question is a
proof-bearing loop-carried access with all alias, call, mutation, lifetime,
overflow and failure-order invalidators closed. Read
`reconciliations/P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_20260814.md`,
`experiments/S3-EXP-0033-p9-1-bounds-validity-contract-attribution.md`, and
`zettelkasten/notes/S3-ZK-0058.md` before any future work.

## Authoritative current checkpoint: P9.2 closed - 2026-08-14

P9.2 was research-only on the stacked correctness candidate A+B. It did not
change production or imply that the candidate is main:

```text
P9_2_CAMPAIGN=P9_2_EXPLICIT_RANGE_FACT_CONTRACT_V1
P9_2_STATUS=COMPLETE_RESEARCH_ONLY
P9_2_TARGET_KIND=CORRECTNESS_CANDIDATE_NOT_MAIN
P9_2_TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
TARGET_IS_MAIN=NO
TARGET_HEAD_MATCH=YES
OLD_P9_MODEL_EXPECTED=289500
OLD_P9_MODEL_REPRODUCED=YES
POST_CORRECTNESS_MODEL=289512
CORRECTNESS_ONLY_DELTA=12
WORKLOADS=15
CLASSIFICATION_COVERAGE=1.0
REQUIRED_DYNAMIC=65224
AVOIDABLE_DYNAMIC=0
UNKNOWN_DYNAMIC=26456
PROVABLY_REDUNDANT_SITES=0
PROVABLY_REDUNDANT_DYNAMIC=0
MODEL_A_RECOMPUTE=PASS_NO_SAFE_AVOIDABLE_SUBCLASS
MODEL_B_PRIVATE_FACT=NOT_NEEDED
MODEL_C_PUBLIC_CONTRACT=REJECTED_NOT_JUSTIFIED
P9_2_SELECTION=NO_VALID_TARGET_YET
P9_PRODUCTION_STARTED=NO
PRODUCTION_CODE_CHANGED=NO
BENCHMARK_EXECUTED=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The bounded domain was explicit object/index/length identity plus range and
validity status. Path disagreement, unsupported loops and all listed
invalidators map to `UNKNOWN`, which retains the check. The first fact-loss
boundary remains `ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT`; it
does not authorize public Assembly proof metadata. Read
`reconciliations/P9_2_EXPLICIT_RANGE_FACT_CONTRACT_20260814.md`,
`reconciliations/P9_2_RESULT.json`,
`experiments/S3-EXP-0034-p9-2-explicit-range-fact-contract.md`, and
`zettelkasten/notes/S3-ZK-0059.md` before any future range-fact work.

## Authoritative current checkpoint: P9.3 closed - 2026-08-14

P9.3 is complete research-only on the validated A+B correctness candidate. It
did not integrate the candidate and did not start production P9:

```text
P9_3_CAMPAIGN=P9_3_UNKNOWN_CAUSAL_ATTRIBUTION_V1
P9_3_STATUS=COMPLETE_RESEARCH_ONLY
P9_3_TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
P9_3_BASELINE_EXPECTED=289512
P9_3_BASELINE_REPRODUCED=YES
TOTAL_UNKNOWN_DYNAMIC=26456
UNKNOWN_CLASSIFICATION_COVERAGE=1.0
P8_REGISTER_INIT_UNKNOWN_STATIC=30096
P8_REGISTER_INIT_UNKNOWN_DYNAMIC=26456
P9_RELEVANT_UNKNOWN_DYNAMIC=0
INHERENTLY_REQUIRED_DYNAMIC=0
OUT_OF_SCOPE_EXISTING_MECHANISM_DYNAMIC=26456
ATTRIBUTION_LIMIT_ONLY_DYNAMIC=0
POTENTIALLY_AVOIDABLE_UNPROVEN_DYNAMIC=0
PROVABLY_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_AVOIDABLE_DYNAMIC=0
MAX_THEORETICAL_SHARE_OF_MODEL=0.0
P9_3_SELECTION=NO_P9_BOUNDS_OPPORTUNITY
P9_PRODUCTION_STARTED=NO
P9_4_AUTHORIZED_BY_EVIDENCE=NO
BOUNDS_VALIDITY_LINE_STATUS=CLOSE
NEXT_GLOBAL_OPTIMIZATION_QUESTION=NO_NEW_TARGET_YET
REMOTE_WRITE_PROVENANCE=PROVEN_ZERO_ACTIONS
REMOTE_WRITE_EVENT=push
REMOTE_WRITE_TARGET_REF=research/zettelkasten-lab-20260812
REMOTE_WRITE_POSSIBLE_ACTIONS=0
```

The complete UNKNOWN population is exactly the existing P8 register-init
mechanism, measured over 8892 structural sites and six workloads. No
P9-relevant UNKNOWN class or concrete redundant example remains. The exact
candidate baseline is `289512`, and the classification partition has complete
coverage. Read `reconciliations/P9_3_RESULT.json`,
`reconciliations/CORRECTNESS_A_B_INTEGRATION_20260814.md`,
`experiments/S3-EXP-0035-p9-3-unknown-causal-attribution.md`, and
`zettelkasten/notes/S3-ZK-0060.md` before any future campaign.

The A+B integration route was analyzed statically. Feature-branch publication
is `PROVEN_ZERO_ACTIONS`, but pull-request semantics are `UNKNOWN` and the
resulting main-ref update is `ACTIONS_POSSIBLE`; therefore
`CORRECTNESS_INTEGRATION=BLOCKED`, `MAIN_UPDATED=NO`, and `PR_CREATED=NO`.
No workflow was changed and no alternative route was executed.

## Authoritative current checkpoint: P10 census complete - 2026-08-14

P10 is research-only and did not select or implement a production optimization:

```text
P10_CAMPAIGN=P10_GLOBAL_DYNAMIC_OPPORTUNITY_CENSUS_V1
P10_STATUS=COMPLETE_RESEARCH_ONLY
INITIAL_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
CORRECTNESS_CANDIDATE_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RESEARCH_HEAD_START=9e40cf15780fd2e4ce4175c7f98ab778b7c0a92e
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
TARGET_MAIN_ANCESTRY=YES
P9_STATUS=CLOSED
P9_BOUNDS_VALIDITY_STATUS=CLOSED
BASELINE_EXPECTED=289512
BASELINE_REPRODUCED=YES
BASELINE_ACTUAL=289512
WORKLOADS=15
CLASSIFICATION_COVERAGE=1.0
TOP_DYNAMIC_FAMILY=INSTRUCTION_LIMIT_ACCOUNTING
TOP_DYNAMIC_FAMILY_DYNAMIC=99036
TOP_NON_SEMANTIC_FAMILY=INSTRUCTION_LIMIT_ACCOUNTING
TOP_NON_SEMANTIC_DYNAMIC=99036
FRAME_CANONICALIZATION_DYNAMIC=39081
FRAME_VALUE_DYNAMIC=14795
STACK_RESIDENT_FRAME_VALUE_DYNAMIC=10063
TRUE_SPILL=UNKNOWN_NOT_ESTABLISHED
TRUE_RELOAD=UNKNOWN_NOT_ESTABLISHED
PROVABLY_REQUIRED_DYNAMIC=250431
PROVABLY_AVOIDABLE_DYNAMIC=0
POTENTIALLY_AVOIDABLE_DYNAMIC=0
UNKNOWN_AVOIDABILITY_DYNAMIC=39081
CONCRETE_AVOIDABLE_EXAMPLE_FOUND=NO
MATERIAL_AVOIDABLE_FAMILY_FOUND=NO
P10_SELECTION=NO_VALID_TARGET_YET
NEXT_GLOBAL_TARGET=NONE
PRODUCTION_OPTIMIZATION_STARTED=NO
LAB_CONSISTENCY=PASS
REMOTE_WRITE_PROVENANCE=PROVEN_ZERO_ACTIONS
REMOTE_WRITE_EVENT=push
REMOTE_WRITE_TARGET_REF=research/zettelkasten-lab-20260812
REMOTE_WRITE_POSSIBLE_ACTIONS=0
```

The primary sidecar partition is exact. Instruction-limit is policy-required;
bounds and memory validity are closed by P9; semantic payload is not treated
as overhead; and frame traffic is not established as spill. The P10 census
found no concrete avoidable example and selected no next target. Read
`reconciliations/P10_GLOBAL_DYNAMIC_OPPORTUNITY_CENSUS_20260814.md`,
`reconciliations/P10_RESULT.json`,
`experiments/S3-EXP-0036-p10-global-dynamic-opportunity-census.md`, and
`zettelkasten/notes/S3-ZK-0061.md` before any future campaign.

The A+B integration remains `STILL_BLOCKED_BY_PROVENANCE`; it was not retried.
No production code, benchmark, GitHub Actions run or shutdown occurred.

## Authoritative current checkpoint: P10.1 frame representation causal decomposition - 2026-08-14

P10.1 is complete research-only on the frozen correctness candidate A+B. It
consumed the existing P9/P10 sidecars and did not import or modify production:

```text
P10_1_CAMPAIGN=P10_1_FRAME_REPRESENTATION_CAUSAL_DECOMPOSITION_V1
P10_1_STATUS=COMPLETE_RESEARCH_ONLY
INITIAL_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
CORRECTNESS_CANDIDATE_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RESEARCH_HEAD_START=0b4ea40b6555689712ae616b346f49aef5253c21
TARGET_IS_MAIN=NO
TARGET_IS_VALIDATED_CORRECTNESS_CANDIDATE=YES
TARGET_HEAD_MATCH=YES
TARGET_MAIN_ANCESTRY=YES
BASELINE_EXPECTED=289512
BASELINE_REPRODUCED=YES
BASELINE_ACTUAL=289512
WORKLOADS=15
FRAME_REPRESENTATION_BROAD_EXPECTED=39081
FRAME_REPRESENTATION_BROAD_ACTUAL=39081
LOGICAL_FRAME_VALUE_TRAFFIC_DYNAMIC=14795
PHYSICAL_STACK_VALUE_TRAFFIC_DYNAMIC=10063
OTHER_FRAME_REPRESENTATION_DYNAMIC=24286
TMOV_COPY_MATERIALIZATION_DYNAMIC=240
TRUE_SPILL_STORE_DYNAMIC=0_PROVEN
TRUE_SPILL_RELOAD_DYNAMIC=0_PROVEN
CAUSAL_CLASSIFICATION_COVERAGE=1.0
AVOIDABILITY_CLASSIFICATION_COVERAGE=1.0
PROVABLY_REQUIRED_DYNAMIC=0
PROVABLY_AVOIDABLE_DYNAMIC=0
POTENTIALLY_AVOIDABLE_UNPROVEN_DYNAMIC=0
ATTRIBUTION_LIMIT_ONLY_DYNAMIC=39081
MAX_THEORETICAL_REMOVABLE_DYNAMIC=0
MAX_REGISTER_PRESSURE_OBSERVED=UNKNOWN_NOT_MEASURED
CONCRETE_SPILL_EXAMPLE_FOUND=NO
CONCRETE_NON_SPILL_AVOIDABLE_EXAMPLE_FOUND=NO
ORACLE_USED=NO
FIRST_CAUSAL_BOUNDARY=FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED
P10_1_SELECTION=NO_VALID_TARGET_YET
TARGET_SUBCLASS=NONE
FRAME_LINE_STATUS=CLOSE
NEXT_EXPERIMENT=NONE_WITHIN_FRAME
PRODUCTION_OPTIMIZATION_STARTED=NO
CORRECTNESS_INTEGRATION_STATUS=STILL_BLOCKED_BY_PROVENANCE
CORRECTNESS_INTEGRATED=NO
LAB_CONSISTENCY=PASS
REMOTE_WRITE_PROVENANCE=PROVEN_ZERO_ACTIONS
REMOTE_WRITE_EVENT=push
REMOTE_WRITE_TARGET_REF=research/zettelkasten-lab-20260812
REMOTE_WRITE_POSSIBLE_ACTIONS=0
GITHUB_ACTIONS_EXECUTED=NO
BENCHMARK_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The broad class reconciles exactly as `14795 + 24286 = 39081`. The `10063`
stack-resident frame-value events are an overlay inside the logical-value
row, not a third additive class and not proof of spill. The sidecar does not
provide exact load/store direction, liveness, pressure, frame slots,
call-clobber survivors or a valid counterfactual, so all unresolved frame
events are `ATTRIBUTION_LIMIT_ONLY`. Correction B's `ALWAYS_MATERIALIZE_TMOV`
decision is recorded at `240` dynamic events and is not reopened.

Read `reconciliations/P10_1_FRAME_REPRESENTATION_CAUSAL_DECOMPOSITION_20260814.md`,
`reconciliations/P10_1_RESULT.json`,
`experiments/S3-EXP-0037-p10-1-frame-representation-causal-decomposition.md`,
and `zettelkasten/notes/S3-ZK-0062.md` before any future work.

## Authoritative current checkpoint: post-P13/P14 knowledge reconciliation - 2026-08-15

The P13/P14 research evidence has been reconciled into the durable knowledge
graph. This is a research closure, not a new optimization campaign:

```text
P13_P14_RECONCILIATION_STATUS=COMPLETE
P13_STATUS=COMPILER_RESEARCH_FOUNDATION_VALIDATED
P14_0=NEW_RUNTIME_TARGET_SELECTED
P14_1=P14_1_MIXED_SCALING
P14_2=P14_2_MECHANISM_LOCALIZED
P14_3_STARTED=NO
P14_WORKTREE_HEAD=87a5f8bea876b62b564c729feb6975ecc69bed58
FIRST_MATERIAL_AMPLIFICATION_STAGE=DYNAMIC_EXECUTION
LOCALIZED_MECHANISM=repeated parser-loop input/token-array loads/stores
WORK_PROVABLY_AVOIDABLE=UNKNOWN
LEGAL_TRANSFORMATION_ESTABLISHED=NO
REALIZABLE_SAVING_ESTABLISHED=NO
PROFITABILITY_ESTABLISHED=NO
PERMANENT_ZETTELS=S3-ZK-0076..S3-ZK-0078
TEMPORARY_OPEN_QUESTION=S3-ZK-0079
PRODUCTION_CODE_CHANGED=NO
BENCHMARK_EXECUTED=NO
REMOTE_WRITE_EXECUTED=NO
SHUTDOWN_EXECUTED=NO
```

The selected target was the existing JSMN S3 parser state-loop workload with
input-length scaling. P14.1 established mixed scaling. P14.2 localized the
first material amplification to dynamic execution and identified repeated
input/token-array load-store materialization. The evidence deliberately does
not call that work redundant or avoidable.

The open question remains bounded by aliasing, mutation, call effects,
reference semantics, bounds and failure ordering, memory validity,
loop-carried state, SSA identity, memory versions, instruction-limit
semantics, and observer effects. Reopening requires new compiler, workload,
memory-provenance, alias, mutation or semantic evidence, or an explicit
explanation of why the unknown is resolvable.

Read `P13_P14_RECONCILIATION.md`, `zettelkasten/P14_INDEX.md`, and
`zettelkasten/notes/S3-ZK-0076.md` through `S3-ZK-0079.md` before any future
performance research. Do not start P14.3 or production optimization from
this checkpoint.

## Authoritative current checkpoint: native program frontend campaign - 2026-09-20

The functional PR #304 (`feat/s3-native-program-frontend`) extends the
bounded native source slice with typed local state, mutable assignment, typed
parameters, multi-function structure, calls, relational expressions and
`while` block structure. Its final pushed functional head for this checkpoint
is `bf79e618c64b96d2be5640b4f2949b829df10b5c`. The exact reconciliation is in
`reconciliations/SELFHOST_NATIVE_PROGRAM_FRONTEND_20260920.md`.

The result is a real representational program frontend, not a self-hosted
semantic compiler. Focused Windows tests, compileall, diff-check, and the
focused Linux x86-64 qualification passed. The natural PR CI run failed
before execution with all observed jobs ending in 1-8 seconds and `steps=[]`,
so it is classified as infrastructure dispatch failure and was not rerun.

The scientific-kernel gate is closed as a scope frontier:

```text
SCIENTIFIC_KERNEL_READINESS=BLOCKED_ARCHITECTURALLY
FIRST_MISSING_SCIENTIFIC_CAPABILITY=native semantic/lowering/execution plus f64 indexed data and math contracts
SCIENTIFIC_MICROKERNEL_EXECUTED=NO
FULL_SUITE=PASS
FULL_SUITE_HEAD=bf79e618c64b96d2be5640b4f2949b829df10b5c
FULL_SUITE_RESULT=4002 passed, 311 skipped, 572 subtests passed
FULL_SUITE_EXIT=0
FULL_SUITE_DURATION_SECONDS=4952.20
FULL_SUITE_TRANSCRIPT=C:/Users/samue/AppData/Local/Temp/s3-pr304-full-suite-20260920-060307.txt
PR304=OPEN_DRAFT
PR304_MERGED=NO
S3_BENCHMARKS_CHANGED=NO
```

Do not infer full self-hosting, native scientific execution, or benchmark
performance from this checkpoint. A future campaign must begin with an
explicit semantic/lowering/runtime design and preserve the differential
boundary; it must not silently expand this parser slice into an ABI or runtime.

### 2026-09-20 update — PR #305 native semantic execution

PR #305 is an open Draft on `feat/s3-native-semantic-execution`, based on the
exact PR #304 head. It closes the first i64 semantic execution slice in S3
source: literals, local binding, assignment, parameters, calls, returns,
grouping, and bounded while execution. The first real result is `42` for
`40 + 2`; arbitrary positive literals and zero/one/many loop iterations are
covered. The semantic path has no hosted frontend fallback.

```text
FUNCTIONAL_HEAD=34a923f84db7ff8d4f9b7cf9083f272169cc7524
FINAL_DOCS_HEAD=4fb69f0b
NATIVE_I64_SEMANTICS=PASS
FOCUSED_SEMANTIC=14 passed, 1 skipped
FULL_SUITE=PASS
FULL_SUITE_EXIT=0
LINUX_X86_64=DEFERRED_TO_LINUX_HOST
```

The next blocker is the missing native typed value/result contract needed for
f64 and indexed data. Do not infer f64 or scientific-workload readiness from
the i64 result. Detailed reconciliation:

`research-lab/reconciliations/SELFHOST_NATIVE_SEMANTIC_EXECUTION_20260920.md`
