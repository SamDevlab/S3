# S3 Research Handoff

Use this file as the first context document when continuing S3 compiler research in a new ChatGPT/Codex conversation.

## 1. Project identity

Production repository:

```text
https://github.com/SamDevlab/S3
```

This research workspace lives on:

```text
research/zettelkasten-lab-20260812
```

It is intentionally long-lived and **must not be merged directly into production main**. Proven ideas are ported to a fresh production feature branch based on the then-current `origin/main`.

## 2. Production state at research-lab creation

```text
MAIN=a83e25c3364302227694399ebe12946f887c0ead

P1=COMPLETE
P2=COMPLETE
P3=COMPLETE
P4=NOT_STARTED

P3_PR=169
P3_IMPLEMENTATION_HEAD=4643f60176aec68c7a4d7203f3623bde8bac2ae4
P3_MERGE_COMMIT=a83e25c3364302227694399ebe12946f887c0ead
```

P3 final evidence included Linux full suite exit 0, natural CI green, implementation/merge ancestry confirmed, and no P4 stacking.

When resuming later, **do not assume main is still this SHA**. Fetch current `origin/main`, verify ancestry, and update the research anchor separately.

## 3. Capability history

The major capability roadmap M1.32–M1.38 is complete:

- M1.32 Numeric Domains & Large Indexing
- M1.33 Borrowed Slices
- M1.34 Foreign ABI, Library Mode & Zero-Copy
- M1.35 Owned Dynamic Runtime Data
- M1.36 Linux Host Services & Foreign Tool Interop
- M1.37 Project & Container-Native App Model
- M1.38 S3 Docker V1

Do not reopen these capabilities merely because performance work exposes implementation opportunities.

## 4. Performance campaign history

### Post-M1.38 forensics

Representative findings before the targeted campaigns included very large S3/GCC O2 performance and code-size gaps. The strongest diagnosis was representation/lowering expansion rather than a fundamental language tax.

### P1 — Compact Indexed Access & Bounds Lowering

P1 reduced control-flow/code-size expansion, including representative changes approximately:

```text
.text:               320689 -> 313169
static instructions: 55271  -> 53767
branches:            13197  -> 12445
loads/stores:         27873 -> 27873
```

Key lesson: bounds/control expansion was real, but memory traffic did not move.

### P2 — Value Locality & Representation Staging Reduction

P2 added contained same-basic-block forwarding for eligible non-reference scalar moves in the native emitter. It removed real targeted frame MOVs but did not materially alter the large representative aggregate counters.

Key lesson: local forwarding is correct but too narrow to explain the dominant remaining cost.

### P3 — Cross-Block Value Lifetime & Frame Canonicalization

P3 added conservative cross-block scalar residence. It was intentionally not a general RA redesign. P3 proved additional targeted frame operations could be removed safely, but large global representative counters again moved little.

Fresh P3 performance characterization was roughly:

```text
baseline geomean slowdown vs GCC O2: ~27.274x
candidate:                            ~31.152x
```

No speedup claim was made.

Key post-P3 conclusion:

```text
PRIMARY_REMAINING_BOTTLENECK=
frame canonicalization and cross-block store/reload traffic

SECONDARY=
phi/SSA staging

TRUE_RA_SPILL_DOMINANT=
NOT ESTABLISHED
```

## 5. Testing/process rules

These rules are important and were learned through expensive campaigns:

- Correctness, equivalence, safety, and exact-head evidence are merge gates.
- Performance is characterization; do not weaken correctness to hit a timing target.
- Do focused/native/differential/codegen tests during development.
- Run the expensive full suite only for a coherent production merge candidate.
- Any production commit after final-candidate full-suite evidence invalidates that exact-head evidence.
- Natural CI and full-suite evidence are distinct unless CI-shard equivalence is factually proven.
- Do not rerun slow CI merely because it is slow.
- Preserve first failure; classify/root-cause/minimum-correct/retest. Do not blindly retry.
- Linux-native evidence is mandatory for Linux-native backend work.
- Windows Linux-only failures must remain recorded as platform limitations rather than being reclassified as passes.
- One production milestone = one coherent capability = one PR. No stacking.

Research-lab prototypes do not need the production full suite; they need focused mathematical/semantic self-checks. Production promotion re-enters the normal gates.

## 6. Research philosophy

The current research thesis is:

> Memory should be a consequence of necessity, not the default identity of a logical value.

Distinguish:

```text
LOGICAL VALUE IDENTITY
LOCATION FLEXIBILITY
MEMORY VALIDITY
PHYSICAL REGISTER ASSIGNMENT
```

Do not collapse these prematurely.

Before changing register allocation ask:

```text
Did RA actually receive the original logical value as a cross-block virtual value?
```

If RA sees only frame loads/stores created upstream, RA cannot be the primary cause of those operations.

## 7. Zettelkasten method

Atomic research notes use IDs:

```text
S3-ZK-0001
S3-ZK-0002
...
```

Types:

```text
SOURCE
PERMANENT
BRIDGE
QUESTION
HYPOTHESIS
EXPERIMENT
NEGATIVE_RESULT
ARCHITECTURE
```

One note = one idea.

A hypothesis must be linked to a measurable experiment before it is promoted to architecture.

Negative results are durable knowledge. Do not delete them merely because a model failed.

## 8. Initial literature corpus

The user supplied these books for research:

- Aho/Lam/Sethi/Ullman — *Compilers: Principles, Techniques, and Tools*, 2e
- Davey/Priestley — *Introduction to Lattices and Order*, 2e
- Ahuja/Magnanti/Orlin — *Network Flows: Theory, Algorithms, and Applications*
- Nielson/Nielson/Hankin — *Principles of Program Analysis*
- Schrijver — *Combinatorial Optimization: Polyhedra and Efficiency*, Volumes A–C

The PDFs are **not copied into the repository**. A future conversation may need them reattached or retrieved from the user's file library.

Important conceptual bridges already identified:

- global register residence across block boundaries;
- liveness and IN/OUT fixed points;
- monotone frameworks and abstract interpretation;
- Galois connections and precision management;
- lattice/product domains for representation state;
- lazy materialization;
- materialization placement as a possible cut/flow problem;
- exact bounded optimization as an oracle rather than a production dependency;
- matroid/submodular structure as hypotheses to prove or reject;
- information loss / location-flexibility loss as a compiler quality metric.

## 9. Current candidate research architecture

The most important architectural separation to test is:

```text
value identity
    ↓
location-flexible representation
    ↓
analysis determines constraints
    ↓
materialization only where required
    ↓
physical location assignment / RA
```

Instead of:

```text
value identity
    ↓
frame slot
    ↓
late emitter special-cases try to keep some copies in registers
```

Potential explicit states include:

```text
DEAD
VIRTUAL
REGISTER_VALID
MEMORY_VALID
BOTH_VALID
REMATERIALIZABLE
MUST_MATERIALIZE
CONFLICT
```

This exact lattice is **not established**. It is a hypothesis and must be checked for a valid partial order/meet/join and useful transfer functions.

## 10. Mathematical experiments to prioritize

1. Compute exact backward liveness on generic CFGs.
2. Construct a small finite residence/materialization abstract domain.
3. Build an exact brute-force oracle on tiny CFGs to measure optimality gap.
4. Test whether binary register-flexible vs memory-required materialization placement maps to min-cut.
5. Add register-capacity coupling and observe whether the cut formulation breaks.
6. Test whether any useful residence-benefit set function is submodular.
7. Test whether feasible resident sets satisfy a matroid exchange property in restricted domains.
8. Compare eager frame canonicalization vs lazy materialization on the same CFG/value traces.

A failed proof/experiment should become a `NEGATIVE_RESULT` note.

## 11. Promotion criteria

A research idea is promotable when it has:

```text
clear compiler problem
formal or operational model
correctness/safety argument
prototype
negative/positive tests
measured opportunity coverage
generality beyond jsmn
bounded production complexity
comparison against simpler alternatives
```

Then create a fresh production milestone prompt/branch.

## 12. How to resume in a new chat

Give the new assistant this instruction:

```text
Open SamDevlab/S3 branch research/zettelkasten-lab-20260812.
Read research-lab/HANDOFF.md, research-lab/STATE.json,
research-lab/zettelkasten/INDEX.md and research-lab/RESEARCH_PROTOCOL.md first.
Treat them as the durable project/research context.
Then inspect current origin/main because production may have advanced.
Do not merge the research branch to main.
```

After that, provide any new production reports generated since this handoff and update `STATE.json`/`HANDOFF.md` on the research branch when a major milestone changes the research landscape.
