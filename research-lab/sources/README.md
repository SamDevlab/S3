# Research Sources

The research branch stores **notes about sources**, not the copyrighted source PDFs themselves.

When a future chat needs to inspect exact passages, reattach/retrieve the user's copies. Never infer an exact theorem from these catalog notes alone.

## Core compiler / optimization corpus

### Aho, Lam, Sethi, Ullman — Compilers: Principles, Techniques, and Tools, 2e

Use for basic blocks/flow graphs, code generation, global register allocation, instruction selection, Ershov/Sethi-Ullman register requirements, data-flow, fixed points, dominators/loops, and PRE.

Primary S3 bridge: storing all live values at block boundaries can create the stores/reloads S3 is trying to eliminate; global information should decide what must survive and how.

### Davey & Priestley — Introduction to Lattices and Order, 2e

Use for posets, lattices/complete lattices, products, CPOs, fixed-point theorems, and domain-oriented foundations.

Primary S3 bridge: define representation knowledge as an ordered abstract domain only if the states truly form a sound/useful order.

### Ahuja, Magnanti, Orlin — Network Flows: Theory, Algorithms, and Applications

Use for residual networks, max-flow/min-cut, minimum-cost flow, node potentials, primal-dual algorithms, optimality conditions, sensitivity and scaling.

Primary S3 bridge: test whether restricted materialization/representation boundaries can be represented as cut/flow decisions whose costs correspond to stores, reloads, conversions or preservation operations.

### Nielson, Nielson, Hankin — Principles of Program Analysis

Use for Data Flow Analysis, Constraint Based Analysis, Abstract Interpretation, Type/Effect Systems, monotone frameworks, fixed points, widening/narrowing, Galois connections and combined analyses.

Primary S3 bridge: separate concrete compiler facts from abstract properties and control the precision/cost tradeoff explicitly.

### Alexander Schrijver — Combinatorial Optimization: Polyhedra and Efficiency, Volumes A–C

Use for flows, matching/covering, matroids, greedy structure, submodular functions/polymatroids, coloring/stable sets and polyhedral min-max viewpoints.

Primary S3 bridge: before assuming a compiler choice is inherently heuristic, test whether a restricted domain exposes exact/bounded combinatorial structure.

## Expanded mathematical / ternary / information corpus

### Siegfried Gottwald — A Treatise on Many-Valued Logics

Source establishes/organizes truth-degree structures, many-valued truth functions/connectives, finite many-valued systems, functional completeness questions, algebraic structures and applications.

Primary S3 bridges:

- do not equate the semantic `trit` with one physical integer encoding;
- compare the exact S3 trit algebra against known many-valued systems without changing S3 semantics to fit a named logic;
- search for a cost-useful internal ternary operation basis;
- use product/order ideas when modeling ternary semantic/representation states.

Related: `S3-ZK-0016`, `0018`, `0023`.

### Zvi Kohavi & Niraj K. Jha — Switching and Finite Automata Theory, 3e

Source covers combinational logic/synthesis, finite-state machine equivalence/minimization, state assignment, partition lattices, decomposition, information flow and information-lossless machines.

Primary S3 bridges:

- minimize semantic control/state before binary branch lowering;
- use partitions as dependency/information bounds for finite state;
- define required-information contracts across compiler lowering boundaries.

Related: `S3-ZK-0019`, `0020`, `0027`.

### Thomas M. Cover & Joy A. Thomas — Elements of Information Theory

Source covers entropy, relative entropy, mutual information, data-processing inequality, coding, Markov processes and information-theoretic inequalities.

Primary S3 bridges:

- distinguish deterministic compiler information loss from genuine probabilistic entropy;
- use mutual-information/data-processing intuition to ask what downstream phases can recover after upstream collapse;
- explore representation/coding density for ternary data only under a defined workload/probability model.

Related: `S3-ZK-0021`, `0027`.

### Donald E. Knuth — The Art of Computer Programming, Volume 4A: Combinatorial Algorithms, Part 1

Use for disciplined combinatorial generation/search and exact small-problem algorithms.

Primary S3 bridge: build bounded exact oracles and systematic counterexample searches rather than trusting a heuristic because it succeeds on selected cases.

Related: `S3-ZK-0007`, `0018`.

### Graham, Knuth, Patashnik — Concrete Mathematics, 2e

Use for recurrences, sums, elementary number theory, binomial coefficients, generating functions, discrete probability and asymptotic methods.

Primary S3 bridge: derive exact cost/complexity formulas and validate heuristic weights/recurrences instead of accumulating unexplained constants.

### Hopcroft, Motwani, Ullman — Introduction to Automata Theory, Languages, and Computation, 2e

Use for finite automata, state equivalence/minimization, formal languages, decidability and complexity.

Primary S3 bridge: recognize compiler regions that are finite state, prove observational equivalence, minimize them before selecting a physical state encoding, and use complexity theory to bound where exact analysis should stop.

Related: `S3-ZK-0019`.

### Roland & Shiman — Strategic Computing: DARPA and the Quest for Machine Intelligence, 1983–1993

Historical/organizational source rather than an algorithm textbook. Covers ambitious research programs, architectures, infrastructure, demonstrations and technology transition.

Primary S3 bridge: keep a strict maturity ladder from idea -> prototype -> counterexample-tested model -> S3 integration experiment -> production candidate. Do not confuse a striking demo with production maturity.

Related: `S3-ZK-0026`.

### Enayat, Kalantari, Moniri (eds.) — Logic in Tehran

Proceedings source spanning mathematical logic, arithmetic/model theory, quantifier elimination, explicit definability, bounded arithmetic and computability topics.

Primary S3 bridges:

- investigate bounded proof/fact languages rather than an unconstrained theorem prover;
- preserve cheap facts across lowering boundaries;
- ask whether useful optimizer facts admit simpler normal/quantifier-free representations.

Related: `S3-ZK-0022`, `0025`.

### Hafiz Md. Hasan Babu — Multiple-Valued Computing in Quantum Molecular Biology, Volume 2

Source presents multiple-valued/ternary operations, sequential circuits, memories, programmable devices and ternary processor components across quantum/DNA-oriented substrates.

Primary S3 bridge is **virtualization, not hardware imitation**:

- ternary semantic operations can exist independently of one physical substrate;
- conversion between representations has cost and should be explicit;
- research a ternary virtual ISA / representation-selection layer for ordinary S3 targets;
- no quantum/DNA backend is implied.

Related: `S3-ZK-0016`, `0018`, `0023`, `0024`.

## Current synthesis

The expanded corpus now supports three connected flexibility dimensions:

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF/KNOWLEDGE_FLEXIBILITY
```

Potential long-term pipeline model:

```text
LOGICAL VALUE
   |
   +-- semantic facts
   +-- legal representations
   +-- location flexibility
   +-- proof/validity facts
   |
constraints accumulate
   |
choices collapse only when required
   |
materialization / representation / physical resource assignment
```

This is a research direction, not an established production architecture.

## Source discipline

Every literature-derived Zettel must distinguish:

```text
WHAT THE SOURCE ACTUALLY ESTABLISHES
```

from:

```text
THE NEW S3 CONNECTION WE INFER FROM IT
```

Examples:

- Network Flows establishes flow/cut theory; it does **not** establish that general S3 register allocation is min-cut.
- Information Theory establishes entropy/data-processing results; it does **not** justify assigning arbitrary entropy values to compiler phases.
- Babu presents ternary hardware/substrate designs; it does **not** establish that S3 should implement a quantum/DNA backend.
- Gottwald catalogs many-valued systems; it does **not** mean S3's existing trit semantics equal Łukasiewicz/Kleene/Post logic without factual comparison.
