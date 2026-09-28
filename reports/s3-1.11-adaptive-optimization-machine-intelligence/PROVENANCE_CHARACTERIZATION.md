# Native Move, Control, and Address Provenance Characterization

## Evidence identity

```text
EXPERIMENT=EXP-S3-111-MOVE-CTRL-ADDR-001
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
OBSERVATORY_SCHEMA=1.1.0
PROFILE_SCHEMA=3
OUTPUT_SHA256=a1323b265f05ce328d0154e8a31b0bea8f47c25123ee83af9abfdae312bd4c77
CLASSIFICATION=SUPPORTED_STRUCTURALLY_WITH_LINEAGE_LIMIT
```

The analyzer validates exact `git_head`, `git_tree`, clean-source marker, and
workload source SHA before joining. The schema does not carry workload ID in
the observatory provenance, so the analyzer derives it by a unique exact
source-SHA match in the logical profile; ambiguous/missing matches fail
closed.

## Broad hot-structure context

Full-profile aggregate weights are distinct from the bounded hot-block list.
The full static weighted categories are:

| Workload | MOVE | CONTROL_FLOW | STACK | UNKNOWN | Total weight |
| --- | ---: | ---: | ---: | ---: | ---: |
| energy | 51,326 | 44,140 | 15,918 | 28,846 | 140,398 |
| point cloud | 43,064 | 38,437 | 14,797 | 24,898 | 121,197 |
| raster | 28,594 | 28,933 | 9,773 | 18,460 | 85,806 |

The profile's displayed hot-block subset contains 20 blocks/workload. Joining
each static native instruction row to its containing profiled block and
multiplying by that block's logical entry visits yields this bounded
structural visit weight:

| Workload | MOVE | CONTROL_FLOW | MEMORY_ACCESS | STACK | UNKNOWN |
| --- | ---: | ---: | ---: | ---: | ---: |
| energy | 51,218 | 43,996 | 15,882 | 169 | 28,585 |
| point cloud | 42,298 | 37,704 | 14,530 | 0 | 24,468 |
| raster | 24,422 | 24,306 | 8,629 | 0 | 15,123 |

This subset is not all blocks and the product of static instruction rows by
block-entry visits is not a retired-instruction count, taken-edge profile,
runtime share, or cost attribution.

## What lineage does and does not establish

The observatory associates machine move rows with Assembly source opcodes.
In the bounded profiled blocks, the largest move lineages include:

| Workload | `TLOAD` | `TSTORE` | `TCONST` | `TADD` | `TCALL` |
| --- | ---: | ---: | ---: | ---: | ---: |
| energy | 14,168 | 7,432 | 12,779 | 4,200 | 2,688 |
| point cloud | 12,744 | 5,552 | 10,428 | 4,224 | 0 |
| raster | 7,364 | 2,840 | 6,400 | 2,400 | 736 |

These are *opcode associations*: lowering an Assembly operation may emit
several machine moves. They do not determine whether a move is a semantic
copy, SSA copy, allocator copy, ABI argument/return move, save/restore,
constant materialization, or address temporary. The current observer does
not expose that causal reason. Therefore semantic move-category attribution
remains `PARTIAL`, and allocator redesign is not justified by this result.

The control join similarly records native branch mnemonics and associated
Assembly opcodes, but does not prove whether a branch is a user condition,
loop backedge, bounds check, budget check, error path, dispatch, or which
edge was taken. Edge-profile or richer compiler-origin facts are required
before such claims.

## Address-pattern census

Across each complete native object, recognized bracketed memory operands
classify as follows:

| Workload | Base + displacement | Base + scaled index | Base only | RIP-relative |
| --- | ---: | ---: | ---: | ---: |
| energy | 245 | 49 | 21 | 19 |
| point cloud | 429 | 96 | 34 | 12 |
| raster | 467 | 90 | 37 | 25 |

This lexical census is not an eligibility count for S3 Assembly address
strength reduction. It motivates a separate provenance/affine eligibility
probe; no address rewrite has been tested or promoted.

## Reproducibility

```text
TOOL=tools/s3_111_observatory_attribution.py
FOCUSED_TESTS=8 passed
PROFILE_SHA256=cb41a728b1af004835dda6df008db0eed6956165fb2f031a969776a0dd288434
```
