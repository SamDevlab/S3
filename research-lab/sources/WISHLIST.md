# S3 Research Literature Wishlist

This is a prioritized **research acquisition/review list**, not a requirement to buy books. Prefer legal library/institutional/author-access copies where available.

The goal is to add sources that can create new Zettelkasten connections, not duplicate material already covered.

## Tier A — Highest expected value

### 1. Patrick Cousot — Principles of Abstract Interpretation

Why:

- modern, deep treatment of abstract interpretation;
- directly strengthens residence/product domains, fixed points, invariants, widening/narrowing and correctness arguments;
- likely bridge to `S3-ZK-0003`, `0004`, `0010`, `0011`, `0022`, `0025`.

Primary question:

> Can location/representation/proof flexibility be formalized as sound abstract domains instead of ad-hoc metadata?

### 2. Fabrice Rastello & Florent Bouchez Tichadou (eds.) — SSA-based Compiler Design

Why:

- dedicated modern reference on SSA construction/destruction, liveness, information propagation, redundancy elimination, code generation and register allocation;
- directly relevant to the P3/P4 uncertainty around SSA destruction, phi staging and what reaches RA.

Primary question:

> Which location/value facts can remain explicit through SSA destruction instead of becoming frame identity?

### 3. Michael D. Miller & Mitchell A. Thornton — Multiple-Valued Logic: Concepts and Representations

Why:

- mathematical MVL systems plus alternative data representations;
- unusually close match to the new `REPRESENTATION_FLEXIBILITY` research direction.

Primary question:

> Which representations of the same ternary function make compiler analysis and target implementation cheaper?

### 4. Representations of Multiple-Valued Logic Functions

Why:

- focuses on functional, spectral and decision-diagram representations of multiple-valued functions;
- ternary/quaternary examples can seed exact synthesis and alternative IR experiments.

Primary question:

> Is a truth-table/direct-op IR the best form for S3 trit optimization, or can spectral/decision-diagram forms expose stronger simplifications?

### 5. Daniel Kroening & Ofer Strichman — Decision Procedures: An Algorithmic Point of View, 2e

Why:

- SAT/SMT, bit-vectors, arrays, pointer logic, linear arithmetic and theory combination;
- practical bridge from `Logic in Tehran` to bounded machine-usable proof facts;
- directly useful for exact research oracles and potential proof validation.

Primary question:

> Can small compiler facts/transformations be checked by bounded decision procedures without turning normal compilation into theorem proving?

### 6. Franz Baader & Tobias Nipkow — Term Rewriting and All That

Why:

- reduction systems, termination, confluence, completion, unification and equational reasoning;
- highly relevant to canonicalization, peephole/equality optimization and a future ternary algebra simplifier.

Primary question:

> Can S3 have a terminating/confluent semantic rewrite layer for ternary and arithmetic identities with machine-checked rule properties?

## Tier B — High-value disruptive connections

### 7. Droste, Kuich & Vogler (eds.) — Handbook of Weighted Automata

Why:

- weighted transitions model cost/resources/probability;
- covers semirings, fixed points, weighted logic and weighted-automata algorithms;
- may unify state minimization with codegen/materialization costs.

Primary question:

> Can a weighted automaton/semiring represent alternative lowering paths and choose a minimum-cost semantic realization?

### 8. Hennessy, Patterson & Kozyrakis — Computer Architecture: A Quantitative Approach, 7e

Why:

- current quantitative architecture reference;
- memory hierarchy, ILP, SIMD/vector, domain-specific architectures and ISA principles;
- critical when our mathematical cost model needs to approximate real x86/modern-machine behavior.

Primary question:

> Which structural compiler metrics actually predict modern-machine cost, and where are our static cost weights misleading?

### 9. Cygan et al. — Parameterized Algorithms

Why:

- treewidth, separators, kernelization, exact algorithms, matroids and parameterized complexity;
- supports a disruptive policy: exact/strong optimization on structurally simple compiler regions, heuristics elsewhere.

Primary question:

> Are hard backend problems tractable on low-treewidth/small-pressure CFG or interference regions?

### 10. Ebbinghaus & Flum — Finite Model Theory, 2e

Why:

- descriptive complexity, fixed-point logics, automata/logic connections, Datalog and logical reductions;
- connects bounded proof facts, finite-state optimization and computational expressiveness.

Primary question:

> What fact/query language gives S3 useful optimization expressiveness while keeping evaluation tractable?

### 11. Boyd & Vandenberghe — Convex Optimization

Why:

- convexity, duality, relaxations and numerical solution structure;
- useful primarily for deriving lower bounds/relaxations for discrete compiler optimization models.

Primary question:

> Can hard discrete placement/allocation problems admit useful convex relaxations whose dual variables become interpretable resource prices?

### 12. Nocedal & Wright — Numerical Optimization, 2e

Why:

- robust numerical optimization methods and practical convergence engineering;
- potentially useful for offline auto-tuning of compiler cost-model parameters and continuous relaxations.

Primary question:

> Can cost weights be calibrated from measurements systematically rather than becoming hand-tuned magic constants?

## Tier C — Specialized follow-ups

### 13. Beyond Binary Memory Circuits: Multiple-Valued Logic

Use if ternary packing/memory becomes promising. Focus: mathematical MVL representation and multiple-valued SRAM/DRAM/TCAM/Flash.

### 14. Lidl & Niederreiter — Introduction to Finite Fields and their Applications

Use if ternary/base-3 coding, algebraic packing or finite-field transforms become relevant. Do not assume S3 trits form `GF(3)` until operations are checked.

### 15. Polyanskiy & Wu — Information Theory: From Coding to Learning

Use after Cover/Thomas if the information-loss thread produces a real probabilistic workload model and needs a more modern finite-block/statistical perspective.

## Suggested acquisition order

If only five are added next:

```text
1. Principles of Abstract Interpretation
2. SSA-based Compiler Design
3. Multiple-Valued Logic: Concepts and Representations
4. Decision Procedures: An Algorithmic Point of View
5. Term Rewriting and All That
```

If the immediate priority becomes ternary research, swap the order to:

```text
1. Multiple-Valued Logic: Concepts and Representations
2. Representations of Multiple-Valued Logic Functions
3. Term Rewriting and All That
4. Principles of Abstract Interpretation
5. Handbook of Weighted Automata
```
