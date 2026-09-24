# P2H Exclusion Manifest

Selected P2 is `1a76e341098b54a639fec22eecea362cc243c46f`. Rejected P2H starts
at `6f320242e3c1ebbb0d2ac5d6d85272ab375e5333`; current PR #310 head is
`b2178088e0c17738058a92a64ea6c2971530d5cd`.

The exact P2-to-P2H difference changes four files: `emitter.py`, the focused
test, `EXPERIMENTAL_VALIDATION.md`, and adds `HARDENING_REPORT.md` (268
insertions, 52 deletions overall).

| File | Classification | Integration disposition |
| --- | --- | --- |
| `bootstrap/s3/backends/x86_64/emitter.py` | `P2H_HARDENING` | Exclude post-P2 emitter rewrite |
| `tests/test_exact_segment_instruction_budget.py` | `P2H_TESTS` | Do not attribute the 142-line P2H test addition to selected P2 |
| `reports/s3-exact-segment-budget/EXPERIMENTAL_VALIDATION.md` | `P2H_DOCS` | Do not substitute P2H validation outcomes |
| `reports/s3-exact-segment-budget/HARDENING_REPORT.md` | `P2H_DOCS` | Historical rejection evidence, not a product prerequisite |

Later #310 documentation may contain more history, but none changes selected
P2 identity. A clean integration must use the selected P2 commits, not the
current #310 head.

```text
P2H_EXECUTABLE_DELTA_EXCLUDED=YES
P2H_TEST_DELTA_EXCLUDED=YES
PR310_CURRENT_HEAD_SAFE_TO_MERGE_AS_P2=NO
P2H_SELECTED=NO
```

P2H failed its predeclared structural materiality gate. That rejection does
not invalidate the selected P2 evidence.
