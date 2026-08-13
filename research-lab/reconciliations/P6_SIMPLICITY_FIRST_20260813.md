# P6 simplicity-first discovery reconciliation

## Checkpoint

The campaign started from post-P5 `origin/main=a08ee420e9bd0734a28363d60fc0f5f3e1169fb4`
and research head `c3d3517831fece35eacafae45f4cd6f7a96e9bc2`. P5 remained closed;
the original checkout and its two untracked artifacts were preserved.

## Two-track evidence

The 15-workload O1 profile kept JSMN as the heaviest native shape. Aggregate
post-P5 O1 output was 290658 instructions, 16814716 `.text` bytes, 74031
memory operands, 44591 frame accesses, 76034 branches, and 45579 address
calculations. Dynamic totals included 118595 bounds checks, 47240 loads, 71355
stores, and 17539 calls.

The simplicity track found 7351 static `movabs rax, immediate` plus immediate
consumer materializations; 7347 were signed-imm32 eligible. The emulator
recorded 200250 eligible dynamic TCONST events. The smallest sound challenger
was direct TCONST-to-consumer lowering through the existing `_write_register`.

## Conceptual result

Conceptual compression was useful: the temporary register added no semantic,
safety, or target information for eligible non-F64 constants. Complexity
flexibility remains `PARTIAL`, a useful research lens but not a new permanent
architectural dimension. No mathematical model was needed. Global operand-form
optimization did not earn extra coverage over the local challenger.

## Production outcome

P6 was implemented as `P6_DIRECT_NON_F64_TCONST_IMMEDIATE` in commit
`b9ac7d9e8370f013889b8efc9acaed0429447ac2`, PR #175. The first exact-candidate
full suite exposed one stale physical-residency expectation; the contract was
corrected to assert direct physical writes and absence of the old bridge. The
new exact-head full suite passed with exit 0. PR #175 passed all 11 natural CI
checks and merged as `69f5908687123a9ad7a4659b5133f815f08377b1`.

Against the post-P5 baseline, O1 native instructions changed `290658 -> 283311`
(-7347, -2.529%) and `.text` changed `16814716 -> 16667776` (-146940,
-0.874%). Memory operands, frame accesses, branches, and address calculations
were unchanged. Runtime samples remain characterization-only and no speedup is
claimed.

P7 is not started and shutdown remains unauthorized.
