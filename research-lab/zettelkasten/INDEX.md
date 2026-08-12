# S3 Zettelkasten Index

## Seed notes

| ID | Type | Status | Atomic idea |
|---|---|---|---|
| [[S3-ZK-0001]] | PERMANENT | SUPPORTED | Preserve location flexibility before physical allocation. |
| [[S3-ZK-0002]] | BRIDGE | SUPPORTED | Materialization is a decision, not a default logical-value state. |
| [[S3-ZK-0003]] | HYPOTHESIS | OPEN | Value representation may admit a useful residence lattice. |
| [[S3-ZK-0004]] | HYPOTHESIS | OPEN | Separate representation facts may compose better as a reduced product domain. |
| [[S3-ZK-0005]] | HYPOTHESIS | OPEN | Restricted materialization placement may reduce to min-cut/min-cost flow. |
| [[S3-ZK-0006]] | PERMANENT | SUPPORTED | RA cannot fix value identity already destroyed upstream. |
| [[S3-ZK-0007]] | HYPOTHESIS | OPEN | Tiny-CFG exact optimization can provide an optimality oracle. |
| [[S3-ZK-0008]] | QUESTION | OPEN | Restricted feasible resident sets may exhibit matroid-like exchange structure. |
| [[S3-ZK-0009]] | ARCHITECTURE | OPEN | Compiler quality can be studied as preservation/loss of future representation choices. |
| [[S3-ZK-0010]] | BRIDGE | OPEN | Approximation should be introduced only where it buys convergence/cost. |
| [[S3-ZK-0011]] | PERMANENT | SUPPORTED | Fixed-point convergence strategy is an engineering precision/cost parameter. |
| [[S3-ZK-0012]] | QUESTION | OPEN | Residence benefit may be submodular in useful restricted domains. |
| [[S3-ZK-0013]] | PERMANENT | SUPPORTED | Current RA already consumes whole-function CFG liveness/cross-block vregs; RA OFF vs ON is a critical control. |
| [[S3-ZK-0014]] | HYPOTHESIS | OPEN | Lazy materialization may require dual forward-availability and backward-necessity analyses. |

## Current high-value connection cluster

```text
                 S3-ZK-0007 Exact Oracle
                         |
                         v
S3-ZK-0005 Min-Cut -> S3-ZK-0002 Materialization <- S3-ZK-0001 Location Flexibility
         |               |                                 |
         |               v                                 v
         |        S3-ZK-0014 Forward/Backward        S3-ZK-0006 RA downstream
         |               |                                 |
         |               v                                 v
         +-------> S3-ZK-0003 Lattice               S3-ZK-0009 Information Loss
                         |                                 |
                         v                                 v
                  S3-ZK-0004 Product               S3-ZK-0013 Current RA fact
                         |
                         v
                  S3-ZK-0010 Precision
                         |
                         v
                  S3-ZK-0011 Convergence

S3-ZK-0008 Matroid? <----> S3-ZK-0012 Submodular?
```

## Promotion queue

Research ideas currently worth experimentally testing first:

1. `S3-ZK-0013` controlled RA OFF vs RA ON structural/runtime comparison on identical workloads;
2. `S3-ZK-0007` exact oracle for tiny CFG/value-placement problems;
3. `S3-ZK-0005` binary materialization min-cut formulation;
4. `S3-ZK-0014` forward-availability/backward-necessity frontier vs exact oracle;
5. `S3-ZK-0003`/`0004` sound residence domain;
6. `S3-ZK-0009` explicit location-flexibility loss instrumentation;
7. `S3-ZK-0008`/`0012` proof or counterexample search for richer combinatorial structure.
