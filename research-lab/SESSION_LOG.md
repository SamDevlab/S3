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
