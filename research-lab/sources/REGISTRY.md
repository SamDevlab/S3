# S3 Research Source Registry

This file is the durable canonical bibliography/deduplication registry for the S3 research lab.

## Deduplication rule

A source is identified primarily by **work + authors/editors + edition**, not by uploaded filename.

When the same work is supplied again:

- do **not** create duplicate Zettels merely because the file name differs;
- keep one canonical source record;
- record an alternate copy/scan/edition only when it adds meaningful material;
- if editions differ, treat them as `EDITION_VARIANT`, not as independent intellectual sources;
- when a later edition supersedes an earlier one for the same topic, use the later edition as the default citation basis unless the older edition contains uniquely relevant material.

The source PDFs/EPUBs themselves are not committed to this repository.

---

## Canonical corpus

| ID | Source | Status | Primary S3 research role |
|---|---|---|---|
| SRC-001 | Aho, Lam, Sethi, Ullman — *Compilers: Principles, Techniques, and Tools*, 2e | CANONICAL | CFG/dataflow, codegen, RA, PRE, dominators/loops |
| SRC-002 | Davey & Priestley — *Introduction to Lattices and Order*, 2e | CANONICAL | posets, lattices, complete lattices, fixed points |
| SRC-003 | Ahuja, Magnanti, Orlin — *Network Flows* | CANONICAL | min-cut/min-cost flow, duality, potentials |
| SRC-004 | Nielson, Nielson, Hankin — *Principles of Program Analysis* | CANONICAL | dataflow, abstract interpretation, constraints, products |
| SRC-005 | Schrijver — *Combinatorial Optimization: Polyhedra and Efficiency* | CANONICAL | matroids, submodularity, polyhedra, exact/bounded structure |
| SRC-006 | Gottwald — *A Treatise on Many-Valued Logics* | CANONICAL | many-valued/three-valued semantics and algebra |
| SRC-007 | Kohavi & Jha — *Switching and Finite Automata Theory* | CANONICAL | state minimization, partitions, information-flow/lossless machines |
| SRC-008 | Cover & Thomas — *Elements of Information Theory* | CANONICAL | entropy, mutual information, data-processing viewpoint |
| SRC-009 | Knuth — *The Art of Computer Programming, Vol. 4A* | CANONICAL | combinatorial search/oracles/exact enumeration |
| SRC-010 | Graham, Knuth, Patashnik — *Concrete Mathematics* | CANONICAL | recurrence, sums, discrete analysis and combinatorics |
| SRC-011 | Hopcroft, Motwani, Ullman — *Introduction to Automata Theory, Languages, and Computation*, 2e | CANONICAL | equivalence/minimization/automata/complexity |
| SRC-012 | Roland & Shiman — *Strategic Computing* | CANONICAL_META | research-program discipline; demos vs maturity |
| SRC-013 | *Logic in Tehran* (Enayat/Kalantari/Moniri eds.) | CANONICAL_DEEP | mathematical logic, bounded arithmetic, definability, computability |
| SRC-014 | Hafiz Md. Hasan Babu — *Multiple-Valued Computing in Quantum Molecular Biology, Vol. 2* | CANONICAL_SPECIALIZED | ternary gates/state/memory/processor organization; extract algebra/organization, not hardware claims blindly |
| SRC-015 | Hennessy & Patterson — *Computer Architecture: A Quantitative Approach*, 5e | RECEIVED_2026_08_12 | quantitative machine-cost reality: ILP, SIMD/vector/GPU, memory hierarchy, performance tradeoffs |
| SRC-016 | Baader & Nipkow — *Term Rewriting and All That* | RECEIVED_2026_08_12 | termination, confluence, completion, unification, semantic rewrite systems |
| SRC-017 | Kroening & Strichman — *Decision Procedures: An Algorithmic Point of View*, 2e | RECEIVED_2026_08_12 | SAT/SMT/bit-vectors/theory combination; bounded optimization proof oracles |
| SRC-018 | Stankovic, Astola, Moraga — *Representation of Multiple-Valued Logic Functions* | RECEIVED_2026_08_12 | functional, spectral and decision-diagram representations; ternary synthesis |
| SRC-019 | Patrick Cousot — *Principles of Abstract Interpretation* | RECEIVED_2026_08_12 | modern abstract domains, soundness, widening/narrowing, precision engineering |
| SRC-020 | Miller & Thornton — *Multiple Valued Logic: Concepts and Representations* | RECEIVED_2026_08_12 | MVL algebra and implementation-oriented representations/decision diagrams |
| SRC-021 | Rastello & Bouchez Tichadou (eds.) — *SSA-based Compiler Design* | RECEIVED_2026_08_12 | SSA construction/destruction, phi, liveness, codegen and RA boundary |
| SRC-022 | Nocedal & Wright — *Numerical Optimization* | RECEIVED_2026_08_12 | offline cost-model fitting, continuous relaxations, convergence engineering |
| SRC-023 | Boyd & Vandenberghe — *Convex Optimization* | RECEIVED_2026_08_12 | convex relaxation, duality, lower bounds, interpretable resource prices |
| SRC-024 | Cygan et al. — *Parameterized Algorithms* | RECEIVED_2026_08_12 | FPT, treewidth/separators, exact-when-structured optimization |
| SRC-025 | Jean-Éric Pin (ed.) — *Handbook of Automata Theory, Vol. I: Theoretical Foundations* | RECEIVED_2026_08_12 | modern automata, weighted automata, algebraic/equational views, transducers |

---

## Edition variants / duplicates

### DRAGON-BOOK-OLD

A scanned Portuguese *Compiladores — Princípios, Técnicas e Ferramentas* by Aho/Sethi/Ullman was supplied again.

Classification:

```text
EDITION_VARIANT
```

It is the older edition and does **not** replace `SRC-001` (Dragon Book 2e) as the default research source.

Use only when:

- a historical formulation is specifically useful;
- a chapter/page is available in the old scan but not in the supplied 2e copy;
- comparing how the treatment changed between editions is itself relevant.

Do not create duplicate Zettels for concepts already sourced from `SRC-001`.

### HOPCROFT-REUPLOAD

The 2nd edition of Hopcroft/Motwani/Ullman was supplied again.

Classification:

```text
EXACT_WORK_REUPLOAD
```

Canonical record remains `SRC-011`.

Do not duplicate source notes.

---

## Overlap is not duplication

The following pairs overlap heavily but are intentionally distinct:

```text
SRC-011 Hopcroft/Motwani/Ullman
SRC-025 Handbook of Automata Theory
```

The first is a foundational textbook; the second is a broad modern research handbook.

Likewise:

```text
SRC-006 Gottwald
SRC-018 Stankovic/Astola/Moraga
SRC-020 Miller/Thornton
SRC-014 Multiple-Valued Computing Vol.2
```

share multiple-valued/ternary subject matter but serve different roles:

- semantics and logic;
- representation theory/spectral methods;
- implementation-oriented MVL concepts;
- specialized ternary circuit/processor examples.

And:

```text
SRC-004 Principles of Program Analysis
SRC-019 Principles of Abstract Interpretation
```

are complementary, not duplicates: the former bridges several static-analysis paradigms, while the latter deepens the abstract-interpretation foundation.

---

## Current synthesis priority

### Immediate P4 / backend-causality cluster

```text
SRC-001  Compilers 2e
SRC-004  Principles of Program Analysis
SRC-019  Principles of Abstract Interpretation
SRC-021  SSA-based Compiler Design
SRC-015  Computer Architecture: A Quantitative Approach
SRC-016  Term Rewriting and All That
SRC-017  Decision Procedures
```

### Ternary / representation-disruption cluster

```text
SRC-006  A Treatise on Many-Valued Logics
SRC-007  Switching and Finite Automata Theory
SRC-018  Representation of Multiple-Valued Logic Functions
SRC-020  Multiple Valued Logic: Concepts and Representations
SRC-025  Handbook of Automata Theory Vol. I
SRC-008  Elements of Information Theory
SRC-014  Multiple-Valued Computing Vol. 2
```

### Optimization-model cluster

```text
SRC-003  Network Flows
SRC-005  Combinatorial Optimization
SRC-009  TAOCP 4A
SRC-010  Concrete Mathematics
SRC-022  Numerical Optimization
SRC-023  Convex Optimization
SRC-024  Parameterized Algorithms
```

---

## Rule for future uploads

Whenever a new book is supplied:

1. normalize title/authors/edition;
2. compare against this registry;
3. classify as `NEW`, `EXACT_WORK_REUPLOAD`, `EDITION_VARIANT`, or `TOPIC_OVERLAP`;
4. only create new source/Zettel connections if the source adds a distinct theorem, representation, model, algorithm, or research lens;
5. update this registry before relying on conversational memory.
