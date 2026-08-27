# Stage 07 — S5 deterministic serialization

Goal: emit the frozen S3IR2 v2 protocol deterministically and close S5 without promoting incomplete semantic state.

Required record family:

```text
F/B/V/M/I/O/R/C/A/T/Z
```

Only `Z 31` is complete. If any S1-S4 dependency is unresolved, use a lower mask or fail closed.

Required qualification for each focused fixture:

- candidate run produces a parseable v2 stream;
- internal v2 verifier passes;
- strict hosted/candidate semantic conformance passes;
- completeness is `Z 31`;
- repeat the same fixture at least three times and require byte-identical stream output;
- preserve stream SHA256 and conformance JSON.

Exit gate:

```text
S1=PASS
S2=PASS
S3=PASS
S4=PASS
S5_CANONICAL_SERIALIZATION=PASS
FOCUSED_V2_CONFORMANCE=PASS
DETERMINISTIC_REPEAT=PASS
```

Re-check the live control branch before Stage 08.
