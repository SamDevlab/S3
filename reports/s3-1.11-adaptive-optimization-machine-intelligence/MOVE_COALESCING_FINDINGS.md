# Same-Color Copy Emission Experiment

## Provenance and safety contract

```text
SCAN=EXP-S3-111-MOVE-COALESCE-001
PROTOTYPE=EXP-S3-111-MOVE-COALESCE-002
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
SCAN_TOOL_SHA256=4ddd30e5165e582d5d5dcd31cc29dbbe7dac7c5bad64c9d6c1228d365380de47
PROTOTYPE_TOOL_SHA256=29be943f30a15d51192ded78c793b8390e23e4d87551af255c5732aa272a7503
PROTOTYPE_REPORT_SHA256=b0426937e5a0cecd91fa3824036db8ce46d695c7470f5d7f09cb371f63688be0
TARGET=Linux x86-64
OPTIMIZATION=O1 plus research-only STORE-to-LOAD candidate
INSTRUCTION_BUDGET=PER_INSTRUCTION
```

An initial static scan omitted the `r15` reservation used by the real PER
allocator. It is retained as
`evidence/EXP-S3-111-MOVE-COALESCE-001-unreserved-r15-diagnostic.json` and
is explicitly superseded. The corrected scan reserves `r15` and exactly
matches the value-cost allocation report.

## Eligibility scan

The baseline and SSA-substitution programs contain no Assembly `TMOV` in the
three measured functions. STORE-to-LOAD materializes 85 copies:

| Workload | TMOV | Same physical register | Distinct physical registers | Any stack endpoint |
| --- | ---: | ---: | ---: | ---: |
| Energy | 15 | 7 | 2 | 6 |
| Point cloud | 47 | 17 | 25 | 5 |
| Raster | 23 | 6 | 12 | 5 |
| Total | 85 | 30 | 39 | 16 |

Only the 30 same-color cases enter the prototype. Distinct-register and
stack-endpoint copies remain untouched. The allocator's full-function color
assignment proves the source/destination share a location at all program
points; this is narrower than general copy coalescing.

## Prototype and correctness

The isolated emitter subclass omits only the data movement for a `TMOV`
whose distinct virtual source and destination have the same non-stack
physical register. It retains the normal PER `dec r15` and limit check for
the logical Assembly instruction, retains source initialization checking,
and marks the destination initialized through the existing helper. A focused
fixture verifies the two register-to-register moves disappear while the
budget decrement remains exactly once.

The native candidate passed the workload reference and exact
STORE-to-LOAD-vs-candidate output equality for all three workloads. The
production emitter, O1 pipeline, defaults, and budget semantics were not
changed.

## Native structure and paired timing

All deltas are same-color candidate minus the original STORE-to-LOAD
candidate. Timing uses 3 warmups, 21 alternating pairs and 1,000 calls per
sample; the class remains `CHARACTERIZATION_ONLY`.

| Workload | Same-color copies omitted | `.text` bytes | Instructions | Memory / stack / branches / frame | Store-to-load ÷ candidate median ratio | 95% interval | Result |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| Energy | 7 | -42 | -14 | 0 / 0 / 0 / 0 | 1.0232 | [0.9909, 1.0731] | INCONCLUSIVE |
| Point cloud | 17 | -102 | -34 | 0 / 0 / 0 / 0 | 0.9937 | [0.9266, 1.0374] | INCONCLUSIVE |
| Raster | 6 | -36 | -12 | 0 / 0 / 0 / 0 | 0.9937 | [0.9876, 1.0042] | NO_MATERIAL_CHANGE_WITHIN_5_PERCENT |

The result demonstrates a narrow structural opportunity: the current
research candidate has same-color `TMOV` bodies that can be omitted without
changing measured output or logical PER accounting. It does not demonstrate
a material runtime benefit. In particular, it does not explain or reproduce
the STORE-to-LOAD point-cloud signal; removing 17 same-color copies did not
produce a material timing change.

```text
SAME_COLOR_COPY=SUPPORTED_STRUCTURALLY
GENERAL_COPY_COALESCING=NOT_TESTED
MATERIAL_RUNTIME_BENEFIT=NOT_ESTABLISHED
ALLOCATOR_CAUSALITY=NOT_ESTABLISHED
PRODUCTION_PROMOTION=NO
PMU=UNAVAILABLE_BY_POLICY_NOT_PROBED_AGAIN
```
