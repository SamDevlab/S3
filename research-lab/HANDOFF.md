# S3 Research Handoff

Use this file as a first durable context document when continuing S3 compiler research in a new ChatGPT/Codex conversation.

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

**Never merge the research branch directly into `main`.** Proven ideas are reproduced/validated here and then ported selectively to a fresh production branch from the then-current `origin/main`.

## 2. Production anchor at lab creation

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

P3 final evidence included Linux full suite exit 0, natural CI green, ancestry confirmed, P4 not stacked.

A future session must fetch current `origin/main`; this SHA is an historical anchor, not a promise that production is unchanged.

## 3. Capability history

M1.32–M1.38 are complete:

- Numeric Domains & Large Indexing
- Borrowed Slices
- Foreign ABI, Library Mode & Zero-Copy
- Owned Dynamic Runtime Data
- Linux Host Services & Foreign Tool Interop
- Project & Container-Native App Model
- S3 Docker V1

Do not reopen these capability milestones merely because performance research exposes implementation opportunities.

## 4. Performance campaign history

### Post-M1.38

Forensics established massive representation/lowering expansion compared with GCC O2. Primary conclusion: backend/codegen immaturity rather than a fundamental language tax.

### P1 — Compact Indexed Access & Bounds Lowering

Representative historical structural change:

```text
.text:               320689 -> 313169
static instructions: 55271  -> 53767
branches:            13197  -> 12445
loads/stores:         27873 -> 27873
```

Lesson: bounds/control expansion was real; memory traffic remained.

### P2 — Value Locality & Representation Staging Reduction

Same-basic-block eligible scalar forwarding removed targeted frame MOVs but barely moved large aggregate counters.

### P3 — Cross-Block Value Lifetime & Frame Canonicalization

Conservative cross-block scalar residence removed further targeted frame operations but aggregate counters again moved little. Fresh characterization was roughly:

```text
baseline geomean slowdown vs GCC O2: ~27.274x
candidate:                            ~31.152x
```

No speedup claim was made.

Post-P3:

```text
PRIMARY_REMAINING_BOTTLENECK=
frame canonicalization and cross-block store/reload traffic

SECONDARY=
phi/SSA staging

TRUE_RA_SPILL_DOMINANT=
NOT ESTABLISHED
```

## 5. Existing RA fact

At the P3 anchor, current `analyze_allocation()` already:

- consumes whole-function CFG liveness;
- sees cross-block vregs that survive to Assembly IR;
- builds an interference graph;
- performs deterministic greedy coloring;
- treats address-taken referents as stack-canonical;
- treats call-crossing values specially in register-pool preference.

Therefore **RA OFF vs RA ON is a mandatory causal control**. Do not assume the remaining frame traffic is allocator spilling merely because it touches stack/frame memory.

## 6. Testing/process rules

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

## 7. Research methodology — Zettelkasten

IDs:

```text
S3-ZK-0001 ...
S3-EXP-0001 ...
```

Types include SOURCE, PERMANENT, BRIDGE, QUESTION, HYPOTHESIS, EXPERIMENT, NEGATIVE_RESULT, ARCHITECTURE.

Rules:

- one Zettel = one idea;
- separate source-established facts from S3 inference;
- a hypothesis needs a measurable falsifier/experiment;
- negative results are durable knowledge;
- exact/exponential algorithms are welcome as bounded research oracles;
- do not promote a striking demo directly to production maturity.

Current Zettelkasten count after the ternary expansion: **27 notes**.

## 8. Initial global-value research thesis

> Memory should be a consequence of necessity, not the default identity of a logical value.

Distinguish:

```text
LOGICAL VALUE IDENTITY
LOCATION FLEXIBILITY
MEMORY VALIDITY
PHYSICAL REGISTER ASSIGNMENT
```

Primary candidate models already prototyped/researched:

- fixed-point liveness;
- finite residence lattice/reduced products;
- lazy materialization;
- forward availability + backward memory necessity;
- min-cut/min-cost materialization placement;
- exact bounded placement oracles;
- Lagrangian relaxation for shared register capacity;
- matroid/submodular hypotheses/counterexamples;
- location-flexibility loss instrumentation.

## 9. Expanded research thesis — three flexibility dimensions

The literature/ternary synthesis expanded the architecture question to:

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF_KNOWLEDGE_FLEXIBILITY
```

Long-term model under investigation:

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

This is a research architecture, not an accepted production design.

## 10. Ternary virtualization research

The user explicitly wants S3's ternary logic/virtualization explored as a potentially disruptive direction.

Core rule:

> Do not assume `trit` is merely a tiny binary integer. Preserve exact S3 trit semantics first; choose physical encoding later if evidence supports it.

Current ternary research notes:

```text
S3-ZK-0016 semantic ternary abstraction
S3-ZK-0017 representation flexibility
S3-ZK-0018 ternary primitive-basis synthesis
S3-ZK-0019 semantic state minimization
S3-ZK-0020 partition information dependencies
S3-ZK-0023 ternary virtual ISA
S3-ZK-0024 representation conversion graph
```

Research hypothesis document:

```text
research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
```

Hard constraints:

- current S3 semantics are source of truth;
- do not call S3 Łukasiewicz/Kleene/Post logic until exact truth tables are compared;
- no quantum/DNA backend is implied by the multiple-valued hardware literature;
- dense base-3/packed/vector representations are hypotheses requiring cost evidence;
- representation selection must preserve reference/provenance/safety semantics where applicable.

## 11. Information/proof preservation research

New notes:

```text
S3-ZK-0021 compiler information-loss metrics
S3-ZK-0022 proof-carrying optimization facts
S3-ZK-0025 bounded compiler fact/proof language
S3-ZK-0027 information-lossless lowering contracts
```

Use information theory carefully:

- Shannon entropy/mutual information require a defined probability model;
- otherwise prefer deterministic measures such as legal-representation count, equivalence partitions, recoverability or partial-order precision;
- do not create decorative entropy metrics.

A bounded fact language is being considered for facts such as range/nonzero/equivalence/memory-version validity, not as an unrestricted theorem prover.

## 12. Literature corpus cataloged

PDFs are **not committed to GitHub**. A future session may need them reattached/retrieved from the user's file library.

Catalog:

- Aho/Lam/Sethi/Ullman — *Compilers: Principles, Techniques, and Tools*, 2e
- Davey/Priestley — *Introduction to Lattices and Order*, 2e
- Ahuja/Magnanti/Orlin — *Network Flows*
- Nielson/Nielson/Hankin — *Principles of Program Analysis*
- Schrijver — *Combinatorial Optimization: Polyhedra and Efficiency*, A–C
- Gottwald — *A Treatise on Many-Valued Logics*
- Kohavi/Jha — *Switching and Finite Automata Theory*, 3e
- Cover/Thomas — *Elements of Information Theory*
- Knuth — *TAOCP 4A: Combinatorial Algorithms, Part 1*
- Graham/Knuth/Patashnik — *Concrete Mathematics*, 2e
- Hopcroft/Motwani/Ullman — *Introduction to Automata Theory, Languages, and Computation*, 2e
- Roland/Shiman — *Strategic Computing*
- Enayat/Kalantari/Moniri — *Logic in Tehran*
- Hafiz Md. Hasan Babu — *Multiple-Valued Computing in Quantum Molecular Biology*, Vol. 2

See `research-lab/sources/README.md` for source-vs-inference bridges.

## 13. New experiment queue

Existing key experiments continue, especially RA OFF/ON and frame-attribution work.

Added:

```text
S3-EXP-0009 current exact S3 ternary semantics/lowering map
S3-EXP-0010 ternary operation-basis synthesis oracle
S3-EXP-0011 ternary/finite-state minimization
S3-EXP-0012 ternary representation conversion graph
S3-EXP-0013 compiler information-loss boundary audit
```

Highest-priority combined sequence:

```text
RA OFF/ON causal control
        +
>=50-value frame/location attribution
        +
compiler-boundary information-loss audit
        +
exact current trit semantics map
        ↓
only then choose whether production P4 attacks
frame representation, information preservation,
ternary representation, SSA/phi, or RA.
```

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

Ternary semantic mapper, ternary basis oracle, ternary representation oracle and information-loss boundary auditor are **planned, not yet implemented**. Do not claim otherwise.

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

Tell the new assistant:

```text
Open SamDevlab/S3 branch research/zettelkasten-lab-20260812.
Read, in order:
  research-lab/HANDOFF.md
  research-lab/STATE.json
  research-lab/NEW_CHAT_PROMPT.md
  research-lab/RESEARCH_PROTOCOL.md
  research-lab/zettelkasten/INDEX.md
  research-lab/sources/README.md
  research-lab/hypotheses/P4_GLOBAL_VALUE_RESIDENCY.md
  research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
  research-lab/experiments/README.md
Then inspect current origin/main independently.
Do not merge the research branch to main.
Continue from evidence, and update durable handoff/state when major findings change.
```
