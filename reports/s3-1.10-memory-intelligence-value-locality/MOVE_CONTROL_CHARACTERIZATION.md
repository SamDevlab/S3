# S3 1.10 Move and Control Characterization

This is a bounded reuse of the correctness-checked S3 1.9 logical profile and
native Observatory v4 artifacts. It does not rebuild or retime the workloads.

## Provenance and scope

The profile is
`reports/s3-1.9-native-observatory-optimization-discovery/evidence/profiling/logical-dynamic-profile-v3.json`
(SHA-256 `2e1fbc56321bb840349b9b6d933dcaca0912a0edac811a1cfed92898b46f0cb6`).
The native-observatory inputs are pinned by the profile and are:

| Workload | Observatory v4 SHA-256 | Source SHA-256 |
| --- | --- | --- |
| energy | `277ac55caf5393f7558494cdb2d313ab7803e1a25dd7387624d0faa076b10719` | `a146f2ec7bd7f9bf72ea35c04026174874012acdb31541d805bf5f0a4a613c84` |
| point cloud | `c555fe8f3b7b1e59f883ea23749c9272dd3f1c0f858330dfedec0abb107896f3` | `59e752e91159ece4e3a813bc8586f338544ddac52e4b5e755a219d85779238e9` |
| raster | `cccfccb17f3e9a18c40464aab88c1ef2833e8510480d3d40b7b5fe7ed3b854b2` | `6d5d8081991d05e7f89ebe6965bb6664b8f11c33595e062c1b165b0a44c9763e` |

The profile weights static native machine-syntax counts in each mapped
Assembly block by observed logical block entries. Its own scope excludes
runtime-helper execution and function prologue/epilogue instructions outside
profiled blocks. It is a **dynamic structural estimate**, not retired
instructions, hardware events, or runtime attribution. A lowered ternary
branch may skip instructions within a counted block.

## Weighted machine-syntax categories

| Workload | Structural weight | MOVE | CONTROL_FLOW | MOVE + CONTROL_FLOW | UNKNOWN |
| --- | ---: | ---: | ---: | ---: | ---: |
| energy | 140,398 | 51,326 (36.558%) | 44,140 (31.439%) | 67.997% | 28,846 (20.546%) |
| point cloud | 121,197 | 43,064 (35.532%) | 38,437 (31.714%) | 67.247% | 24,898 (20.543%) |
| raster | 85,806 | 28,594 (33.324%) | 28,933 (33.719%) | 67.043% | 18,460 (21.514%) |

The Observatory's machine-syntax classifier labels `mov*` and `xchg` as
`MOVE`, and `j*`, `ret`, and `retq` as `CONTROL_FLOW`. Those broad categories
do not reveal whether a move is semantic, ABI, allocator, or temporary, nor
whether a branch is a loop backedge, ternary arm, bounds check, error path, or
other control transfer. No such finer attribution is inferred here.

The highest weighted blocks include the energy loop body
(`energy_series_aggregation/while_body_33`, 168 logical entries, 74,592
structural weight), point-cloud loop bodies
(`point_cloud_summary/while_body_63` and `while_body_30`, 64 entries each,
38,400 and 31,680 weight), and raster's
`raster_window_statistics/while_body_69` (64 entries, 9,792 weight). These
identify where finer attribution would be most useful, but do not establish
that moves or branches dominate runtime.

## Findings and next bounded questions

- RQ5 is **PARTIAL**: broad MOVE weight is substantial in profiled hot blocks,
  but move origin/role is not classified finely enough to authorize
  coalescing or other optimization.
- RQ6 is **PARTIAL**: broad control-flow weight is substantial, but branch
  kinds and dynamic taken/not-taken behavior are not resolved by block-entry
  counters. No branch optimization is authorized by this evidence.
- Whole-object native-origin attribution remains incomplete (the inherited
  Observatory reports 4,733/7,239 native instructions as unmapped overall).
  The inherited profile states that instructions inside its profiled Assembly
  blocks are mapped; the whole-object gap and the profiled-block join are
  different scopes.
- The useful next experiment, if pursued, is to classify mapped native
  instructions inside selected hot blocks by source Assembly origin and
  control-flow edge, while keeping block-entry counts explicitly structural.
  Runtime or hardware causality would require a separate qualified method.

No source transformation, compiler default, or production policy changed.
