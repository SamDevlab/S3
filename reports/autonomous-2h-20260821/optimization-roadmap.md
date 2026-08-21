# Optimization Roadmap

This roadmap separates correctness and reproducibility debt from native
performance hypotheses. The LICM fix is the only production change retained
by this campaign.

| Priority | Evidence | Expected benefit | Risk | Dependencies | Suggested milestone |
| --- | --- | --- | --- | --- | --- |
| P0 | LICM previously depended on CFG set iteration and changed native output across hash seeds. | Preserve reproducible compiler artifacts. | High if ordering is changed without semantic tests. | Cross-seed regression and native correctness. | M2.01 determinism hardening |
| P1 | S3-O1 remains roughly 1.14x-1.35x C-GCC-O2 on the short six-fixture characterization; no stable causal timing delta was isolated here. | Reduce real native runtime overhead. | High; current sample spread is material. | Longer paired native protocol and hot-path attribution. | M2.02 native hot-path study |
| P2 | S3-O1 generated 48,784 instructions and 1,117,536 text bytes for the reference short campaign. | Reduce code size and instruction pressure. | Medium; structural reduction may not improve runtime. | Stable assembly and per-function attribution. | M2.03 code-size analysis |
| P3 | Stack operations (7,440) and loads/stores (24,445) remain substantial in the JSMN O1 artifact. | Reduce spills and memory traffic. | High; representation and memory effects are observable. | Liveness/interference evidence and differential tests. | M2.04 register/memory study |
| P4 | LICM determinism correction changed no O1 structural counters under the controlled seed. | Find general memory-state materialization opportunities. | High; avoid removing observable stores. | Observer-aware semantic proof. | M2.05 memory-state optimization |
| P5 | Branch count is 12,524 for the O1 artifact, but no isolated branch-cost experiment was run. | Reduce control-flow overhead. | Medium; branch removal can alter semantics. | Profiled hot loops and differential coverage. | M2.06 CFG/codegen study |
| P6 | The benchmark harness has six small fixtures and uses a short smoke mode for this campaign. | Improve workload breadth and statistical confidence. | Low. | Preserve exact provenance and methodology. | M2.07 benchmark breadth |
| P7 | Current evidence is JSMN-specific and does not establish general workload behavior. | Validate compiler behavior on real non-JSMN programs. | Medium. | External workload contracts. | M2.08 workload expansion |
| P8 | Python 3.14 compatibility remains a separate portability concern. | Maintain supported toolchain coverage. | Low for native compiler output. | Isolated Python 3.14 reproduction. | M2.09 portability follow-up |

No optimization candidate met the evidence threshold for implementation in this
campaign. In particular, the A/B/B/A timings were not stable enough to promote
a native optimization.
