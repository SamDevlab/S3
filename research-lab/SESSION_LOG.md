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

Additional user-supplied sources cataloged:

```text
Gottwald — A Treatise on Many-Valued Logics
Kohavi/Jha — Switching and Finite Automata Theory 3e
Cover/Thomas — Elements of Information Theory
Knuth — TAOCP 4A Combinatorial Algorithms Part 1
Graham/Knuth/Patashnik — Concrete Mathematics 2e
Hopcroft/Motwani/Ullman — Introduction to Automata Theory, Languages, and Computation 2e
Roland/Shiman — Strategic Computing
Enayat/Kalantari/Moniri — Logic in Tehran
Hafiz Md. Hasan Babu — Multiple-Valued Computing in Quantum Molecular Biology Vol. 2
```

Research synthesis expanded from one flexibility dimension to three:

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF_KNOWLEDGE_FLEXIBILITY
```

Created Zettels `S3-ZK-0016..0027` covering:

- semantic ternary abstraction;
- representation flexibility;
- exact ternary operation-basis search;
- state-machine minimization;
- partition-based information dependencies;
- compiler information-loss metrics;
- proof/fact preservation;
- ternary virtual ISA;
- ternary conversion graphs;
- bounded compiler fact language;
- research demonstration vs maturity discipline;
- information-lossless lowering contracts.

Created `research-lab/hypotheses/TERNARY_VIRTUALIZATION.md`.

Created experiments:

```text
S3-EXP-0009 ternary semantics/lowering map
S3-EXP-0010 ternary basis oracle
S3-EXP-0011 state minimization
S3-EXP-0012 ternary representation graph
S3-EXP-0013 compiler information-loss boundary audit
```

Updated:

```text
HANDOFF.md
STATE.json
NEW_CHAT_PROMPT.md
sources/README.md
zettelkasten/INDEX.md
experiments/README.md
```

Important discipline recorded:

- current S3 trit semantics are source of truth;
- do not assume a named three-valued logic without truth-table comparison;
- quantum/DNA computing literature is architecture/representation inspiration, not a backend commitment;
- Shannon entropy is not a decorative compiler metric; a probability model is required;
- state/representation information should be preserved only when downstream benefit can be demonstrated;
- `Strategic Computing` is used to reinforce that a successful demonstration is not production maturity.

Current combined priority:

```text
RA OFF/ON causal control
+
>=50-value location/frame attribution
+
compiler-boundary information-loss audit
+
exact current S3 ternary semantics map
↓
select experiments based on causal evidence
↓
only then select a production P4 mechanism
```

No production code was changed on `main`.
No production PR was opened.
P4 production implementation remains unselected.
