# Candidate Scorecard: S3 Milestones 1.39-1.50

Scores are 0-5. Positive columns are direct value; risk, maintenance,
platform cost, and semantic complexity are penalties. The score is decision
support, not an automatic selector. Themes were capped at 25 and finalists at
12 selected milestones plus five alternates.

| Theme | Utility | App | Self-host | Eco | Foundation | Feasible | Testable | Determinism | Binary fit | Ternary value | Risk | Maint | Platform | Semantic | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Owned buffers and dynamic text | 5 | 5 | 5 | 4 | 5 | 3 | 5 | 5 | 5 | 2 | 4 | 3 | 1 | 4 | Selected 1.39 |
| Ordered vectors/byte collections | 5 | 5 | 5 | 4 | 5 | 3 | 5 | 5 | 5 | 2 | 4 | 3 | 1 | 4 | Selected 1.40 |
| Deterministic maps/sets | 5 | 5 | 5 | 4 | 4 | 3 | 4 | 5 | 5 | 2 | 4 | 3 | 1 | 4 | Selected 1.41 |
| Explicit result/error flow | 5 | 5 | 5 | 4 | 5 | 3 | 5 | 5 | 5 | 2 | 4 | 3 | 1 | 4 | Selected 1.42 |
| Scoped resources/capabilities | 5 | 5 | 4 | 5 | 5 | 3 | 4 | 4 | 5 | 2 | 5 | 4 | 2 | 5 | Selected 1.43 |
| Small layered standard library | 5 | 5 | 5 | 5 | 4 | 4 | 5 | 5 | 5 | 2 | 3 | 3 | 1 | 3 | Selected 1.44 |
| Deterministic build graph/lockfile | 5 | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 2 | 3 | 3 | 2 | 3 | Selected 1.45 |
| S3 user test runner | 4 | 4 | 5 | 4 | 4 | 4 | 5 | 5 | 5 | 2 | 2 | 2 | 1 | 2 | Selected 1.46 |
| C ABI and Python buffer interop | 5 | 5 | 3 | 5 | 4 | 3 | 4 | 4 | 5 | 1 | 5 | 4 | 3 | 5 | Selected 1.47 |
| Capability-scoped networking | 5 | 5 | 3 | 5 | 4 | 3 | 4 | 4 | 5 | 1 | 5 | 4 | 4 | 5 | Selected 1.48 |
| WASI target/provider | 4 | 5 | 3 | 5 | 4 | 2 | 3 | 4 | 5 | 1 | 5 | 5 | 5 | 5 | Selected 1.49 |
| Incremental self-hosted component | 5 | 4 | 5 | 4 | 5 | 2 | 4 | 5 | 5 | 2 | 5 | 4 | 2 | 5 | Selected 1.50 |
| Restricted generic parameters | 4 | 4 | 4 | 4 | 3 | 2 | 3 | 3 | 5 | 1 | 5 | 4 | 1 | 5 | Alternate |
| Linux ARM64 backend | 3 | 4 | 2 | 4 | 3 | 2 | 3 | 3 | 5 | 1 | 5 | 5 | 5 | 5 | Alternate |
| Windows x86-64 backend | 3 | 3 | 1 | 3 | 3 | 2 | 3 | 3 | 4 | 1 | 5 | 5 | 4 | 5 | Alternate |
| Parser/lexer migration | 4 | 3 | 5 | 3 | 4 | 2 | 3 | 4 | 5 | 1 | 5 | 5 | 1 | 5 | Alternate |
| Source-correlated debug/DWARF | 4 | 3 | 4 | 4 | 3 | 2 | 3 | 4 | 5 | 1 | 5 | 4 | 3 | 5 | Alternate |
| Traits/interfaces | 3 | 3 | 3 | 4 | 3 | 1 | 2 | 2 | 5 | 1 | 5 | 5 | 1 | 5 | Deferred |
| Language threads/channels | 4 | 4 | 2 | 4 | 2 | 1 | 2 | 2 | 4 | 1 | 5 | 5 | 3 | 5 | Deferred |
| Atomics/memory ordering | 3 | 3 | 1 | 3 | 2 | 1 | 2 | 2 | 5 | 1 | 5 | 5 | 3 | 5 | Deferred |
| Async/event language | 4 | 4 | 2 | 4 | 2 | 1 | 2 | 2 | 4 | 1 | 5 | 5 | 3 | 5 | Deferred |
| Public package registry | 3 | 4 | 3 | 5 | 3 | 2 | 3 | 3 | 4 | 1 | 5 | 5 | 2 | 4 | Deferred |
| Full Unicode/grapheme model | 3 | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 4 | 1 | 4 | 4 | 1 | 4 | Deferred |
| Full parser self-hosting | 4 | 3 | 5 | 3 | 4 | 1 | 2 | 4 | 5 | 1 | 5 | 5 | 1 | 5 | Deferred |
| GPU/SIMD provider | 3 | 3 | 2 | 3 | 2 | 1 | 2 | 2 | 4 | 2 | 5 | 5 | 5 | 5 | Deferred |

## Selection reading

The selected twelve score well because they compose: text and buffers feed
collections; collections and errors feed resources; resources and the standard
library feed build/test and interop; interop and capabilities feed networking
and WASI; the whole chain feeds one self-hosted component. The high-risk
platform and language-semantic themes were not selected merely because they
have high ecosystem visibility.

The five alternates are genuine alternatives, not hidden commitments. They
should be reconsidered only when the stated evidence triggers in
`POST_1_50_DEFERRED_CANDIDATES.md` occur.
