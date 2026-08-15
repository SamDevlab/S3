# P13.R0 — Compiler Foundation Literature Corpus

```text
CAMPAIGN=P13.R0
DATE=2026-08-15
PURPOSE=LITERATURE_REBASE_FOR_COMPILER_FOUNDATION
PRODUCTION_EFFECT=NONE
SOURCE_PDFS_STORED_IN_REPO=NO
```

This file records source-derived guidance only. It does not turn literature into S3 evidence. Every S3 claim still requires code inspection, a proof obligation, or an experiment.

## Confirmed technical corpus

### 1. Rastello & Bouchez Tichadou (eds.) — SSA-based Compiler Design

Confirmed source: Fabrice Rastello and Florent Bouchez Tichadou, Springer, ISBN 978-3-030-80515-9.

Relevant structure inspected from the supplied EPUB:

- Part I — Vanilla SSA;
- Chapter 3 — standard SSA construction/destruction;
- Chapter 5 — SSA reconstruction;
- Chapter 8 — propagation of information using SSA, including the Wegman-Zadeck SCCP family;
- Chapter 9 — liveness;
- Chapter 10 — loop trees and induction variables;
- Chapter 21 — SSA destruction for machine code;
- Chapter 22 — register allocation.

Primary S3 bridges:

- phi nodes are not incidental syntax; they represent merge/loop-carried value semantics that analyses must preserve;
- CFG-changing transformations can require SSA repair/reconstruction rather than ad-hoc provenance recovery;
- SSA destruction can create edge shuffle/copy traffic, so de-SSA is a distinct causal stage for future runtime work;
- liveness, loop structure, phi semantics and register allocation should be treated as connected but distinct contracts.

What this source does **not** prove:

- it does not prove the S3 LICM or SCCP implementation is correct;
- it does not prove a particular S3 phi lowering is optimal;
- it does not authorize compact-state promotion.

Priority: `P0` for P13.1–P13.3.

---

### 2. Møller & Schwartzbach — Static Program Analysis

Confirmed supplied edition: Anders Møller and Michael I. Schwartzbach, Aarhus University, 2021 notes.

Relevant chapters:

- Chapter 2 — CFGs;
- Chapter 4 — lattice theory, monotonicity and fixed points;
- Chapter 5 — monotone dataflow frameworks, constant propagation, work-list fixed points, forward/backward and may/must analyses, initialized variables;
- Chapter 6 — widening/narrowing;
- Chapter 11 — abstract interpretation, abstraction/concretization and soundness.

Source-derived guidance relevant to S3:

- a compiler analysis should have an explicit abstract domain, ordering, merge/join behavior and transfer semantics;
- fixed-point convergence and precision are part of the analysis contract, not implementation trivia;
- definite initialization is naturally a forward must property;
- testing can find unsoundness, but sound static reasoning requires the analysis result to safely approximate concrete executions.

Primary S3 bridges:

- SCCP partial-phi behavior should be audited as a lattice/join soundness question, not merely as a special-case bug;
- initialization facts used to remove a native check must be definite facts, not possible facts;
- P13.2 should make the abstract meaning of `UNKNOWN`, constants and merge states explicit wherever an O1 pass relies on them.

Priority: `P0` for P13.1–P13.3.

---

### 3. Patrick Cousot — Principles of Abstract Interpretation

Confirmed source: Patrick Cousot, MIT Press, ISBN 9780262361521.

Relevant supplied-EPUB chapters/parts:

- Chapters 10–11 — posets/lattices and Galois connections;
- Chapters 15–18 — fixpoints and fixpoint abstraction;
- Chapters 21–23 — abstract domains, chaotic iterations and abstract equational semantics;
- Chapters 34–36 — convergence acceleration, fixpoint checking and reduced products;
- Chapter 41 — dataflow analysis;
- Chapter 52 — semantic soundness/completeness/definedness.

Source-derived guidance relevant to S3:

- approximation must have an explicit concrete/abstract meaning;
- convergence acceleration may sacrifice precision but must not silently sacrifice soundness;
- reduced products are a principled way to combine abstract domains only when their concretization/interaction is defined;
- fixpoint checking and analysis soundness are independent questions from runtime performance.

Primary S3 bridges:

- refine old `residence lattice` and `reduced product` notes: they remain hypotheses until S3 defines concrete semantics for every abstract fact;
- P13 should prefer conservative `UNKNOWN` over an unsupported constant/state inference;
- future combined analyses should state which information dimension is being approximated and what loss is sound.

Priority: `P0/P1` for P13.2; not a mandate to formalize the entire compiler.

---

### 4. Steven S. Muchnick — Advanced Compiler Design and Implementation

Confirmed source: Steven S. Muchnick, Morgan Kaufmann, 1997, ISBN 1-55860-320-4.

Relevant inspected material:

- the optimization-order diagrams explicitly separate transformations by source/high-level, medium/low-level and machine/link-time stages;
- Chapter 12 includes sparse conditional constant propagation and other early optimizations;
- loop optimization material includes LICM, induction-variable work and bounds-checking transformations;
- later stages cover machine idioms, branch optimization, scheduling, graph-coloring register allocation, cache and interprocedural optimization.

Primary S3 bridges:

- pass order and IR level are causal variables: an opportunity can disappear when information is lowered or transformed too early;
- SCCP, LICM, value numbering and related transformations are distinct even when their effects overlap;
- a performance mechanism should be attributed to the first stage where material amplification or information loss appears, rather than to a generic label such as `optimizer`;
- P12.14's `STAGE_1_COMPACT_ELIGIBILITY` result fits a general compiler-engineering pattern: placement and representation determine whether later optimization can act.

What this source does **not** prove:

- it does not prove the historical S3 pass order is wrong;
- it does not justify importing Muchnick's recommended pipeline wholesale;
- it does not prove any stack traffic is a spill.

Priority: `P0/P1` for P13 pass-contract audit and P14 causal funnel.

---

### 5. Bryant & O'Hallaron — Computer Systems: A Programmer's Perspective, 3e

Confirmed source: Randal E. Bryant and David R. O'Hallaron, Pearson, third edition, ISBN 978-0-13-409266-9.

Relevant inspected chapters:

- Chapter 2 — binary/integer/floating-point representation;
- Chapter 3 — x86-64 machine-level program representation, data movement, condition codes, branches, procedures, arrays and stack frames;
- Chapter 5 — optimizing program performance, register spilling, branch prediction, load/store performance and profiling;
- Chapter 6 — locality and memory hierarchy;
- Chapter 7 — linking, relocation, object files and PIC;
- later chapters cover Linux processes, virtual memory, I/O, networking and concurrency.

Primary S3 bridges:

- S3 must remain a competent binary systems language; ternary semantics are not a requirement for ordinary machine-level code;
- static instruction count is only one structural metric and cannot by itself establish runtime improvement;
- branch behavior, dependency structure, data movement and the memory hierarchy are separate machine-level cost dimensions;
- future P14 runtime work should keep claims structural unless hardware-counter evidence exists.

Priority: `P0/P1` for P14 and for binary/native systems maturity.

---

## Excluded supplied file

### Engineering Education — Aims & Goals for the Eighties

The supplied PDF is an Engineering Foundation / ABET conference report from 1981 about engineering education, enrollment, faculty, accreditation and educational policy.

```text
CORPUS_STATUS=EXCLUDED
REASON=NOT_ENGINEERING_A_COMPILER_AND_NOT_A_COMPILER_TECHNICAL_SOURCE
```

It is **not** Keith Cooper & Linda Torczon's *Engineering a Compiler* and must not be cited as compiler evidence.

---

## P13.R0 synthesis

The five-source corpus changes the literature priority from broad idea generation to compiler-foundation questions:

```text
SSA / PHI / RECONSTRUCTION
        +
ABSTRACT DOMAIN / JOIN / FIXPOINT / SOUNDNESS
        +
PASS ORDER / IR LEVEL / ANALYSIS LIFETIME
        +
MACHINE-LEVEL COST MODEL
```

This supports the planned transition:

```text
P12 CLOSED
   ↓
P13 correctness and verifier foundation
   ↓
P14 broad runtime rebase
```

It does **not** reopen P12.18.

## Reading policy

Do not summarize whole books into hundreds of notes.

For every future question:

```text
S3 QUESTION
→ relevant source chapter
→ SOURCE CLAIM
→ S3 BRIDGE / INFERENCE
→ falsifiable claim
→ experiment or verifier
→ supported / rejected / narrower
```

The literature is a hypothesis generator and a correctness reference, not an oracle for S3 behavior.
