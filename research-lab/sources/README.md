# Research Sources

The research branch stores **notes about sources**, not the copyrighted source PDFs themselves.

When a future chat needs to inspect exact passages, reattach/retrieve the user's copies.

## Initial corpus

### Aho, Lam, Sethi, Ullman — Compilers: Principles, Techniques, and Tools, 2e

Use for:

- basic blocks and flow graphs;
- code generation;
- global register allocation;
- instruction selection;
- Ershov/Sethi-Ullman register requirements;
- data-flow analysis;
- fixed-point equations;
- dominators and loops;
- partial redundancy elimination.

Primary S3 bridge:

> Storing all live values at block boundaries can create the very stores/reloads S3 is trying to eliminate; global information should decide what must survive and how.

### Davey & Priestley — Introduction to Lattices and Order, 2e

Use for:

- partially ordered sets;
- lattices and complete lattices;
- products and constructions;
- CPOs;
- fixed-point theorems;
- domain-oriented mathematical foundations.

Primary S3 bridge:

> Define value-representation knowledge as an ordered abstract domain only if the proposed states truly form a useful order with sound joins/meets.

### Ahuja, Magnanti, Orlin — Network Flows: Theory, Algorithms, and Applications

Use for:

- paths, cycles, residual networks;
- max flow / min cut;
- minimum-cost flow;
- node potentials;
- primal-dual algorithms;
- optimality conditions;
- sensitivity and scaling.

Primary S3 bridge:

> Test whether materialization boundaries can be represented as cut/flow decisions whose cost equals stores, reloads, copies, or preservation operations.

### Nielson, Nielson, Hankin — Principles of Program Analysis

Use for:

- Data Flow Analysis;
- Constraint Based Analysis;
- Abstract Interpretation;
- Type and Effect Systems;
- monotone frameworks;
- complete lattices and fixed points;
- widening/narrowing;
- Galois connections;
- combining analyses.

Primary S3 bridge:

> Separate concrete compiler facts from abstract properties, construct conservative analyses, and control the precision/cost tradeoff explicitly.

### Alexander Schrijver — Combinatorial Optimization: Polyhedra and Efficiency, Volumes A–C

Use for:

- paths and flows;
- matching and covering;
- matroids;
- greedy optimality structure;
- matroid intersection/union;
- submodular functions and polymatroids;
- coloring and stable sets;
- polyhedral/combinatorial min-max viewpoints.

Primary S3 bridge:

> Do not assume a compiler choice is inherently heuristic: first ask whether a restricted version has hidden combinatorial structure that admits an exact or bounded algorithm.

## Source discipline

Every literature-derived Zettel should distinguish:

```text
WHAT THE SOURCE ACTUALLY ESTABLISHES
```

from:

```text
THE NEW S3 CONNECTION WE INFER FROM IT
```

For example, the Network Flows book establishes min-cost-flow theory. It does **not** establish that S3 materialization placement is a min-cost-flow problem. That bridge is an S3 hypothesis until proved.
