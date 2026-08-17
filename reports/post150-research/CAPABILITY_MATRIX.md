# Verified Capability Matrix

Status values are `YES`, `NO`, `LIMITED`, `STRUCTURAL_ONLY`, or
`DEFERRED_CERTIFICATION`. The matrix distinguishes implemented semantics from
environment-specific certification.

| Capability | Status | Evidence |
|---|---|---|
| trit / tryte | YES | ai-capabilities, numeric tests |
| i64 / f64 | YES | numeric source and E2E tests |
| static arrays / records / enums / pattern matching | YES | composite specs and focused tests |
| safe references | YES | memory spec and reference semantic tests |
| raw pointers | NO | AI guide explicitly excludes them |
| owned dynamic bytes / text | YES | dynamic-buffer spec, runtime, tests |
| vectors / maps / sets | LIMITED | specialized families; no generic identity |
| move / borrow / clone / drop | LIMITED | bounded dynamic contract; aggregate nesting excluded |
| composite ownership | NO | M1.39 and composite-types exclusions |
| generics / traits / interfaces | NO | AI guide and README |
| errors | YES | structured result/error spec and tests |
| exceptions | NO | AI guide |
| modules / build / lockfile | YES | module and build-graph contracts |
| test runner | YES | M1.46 runner plus local smart orchestrator |
| C ABI / Python ABI | LIMITED | bounded buffer ABI; environment certification deferred |
| TCP | LIMITED | provider and fake/structural tests; Linux certification deferred |
| DNS / UDP / TLS / async | NO | network and capability contracts |
| Linux x86-64 | DEFERRED_CERTIFICATION | backend exists; native environment unavailable here |
| WASI | STRUCTURAL_ONLY | deterministic Preview1 artifact; runtime not certified |
| Windows native / macOS native | NO | capability metadata |
| ARM64 | DEFERRED_CERTIFICATION | no backend certification |
| O0 / O1 | YES | optimizer and differential tests |
| self-hosting | LIMITED | incremental Assembly renderer; Python remains authority |
| authoritative bootstrap implementation | YES | capability manifest and package metadata |

Machine-readable form: `CAPABILITY_MATRIX.json`.
