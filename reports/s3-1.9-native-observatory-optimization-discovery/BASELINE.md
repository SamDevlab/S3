# S3 1.9 Baseline Checkpoint

## Scope and provenance

This is an initial research checkpoint, not a final campaign conclusion. The
compiler baseline is S3 `211b1aecec756be42516322429720018f54001e7` with tree
`08289d214832e856d46e14ef941239649e9f4063`. The working campaign branch is
`feat/s3-1.9-native-observatory-optimization-discovery`; the source checkout
used for the measured run was clean at that exact revision.

The independent-lab candidate base is S3-Benchmarks
`e5ff385d26ea6ec89d13cf1955bfa5438e56a266`. Historical functional freeze
references remain separate: S3 1.8 `b8f446a5ea2b24b948a263cb955f426c5d0f48ce`
and S3-Benchmarks 1.8 `0f5a5c212ea0daa7260ac8c914b5e41b965239b3`.

## Native workload run

The bounded Linux x86-64 runs used three warmups, 21 samples, 1,000 iterations
per sample, paired ordering seed 1501, 10,000 bootstrap resamples, and a 5%
materiality threshold. Setup and compilation were excluded; same-process C ABI
calls were timed, so equal FFI overhead remains included. Correctness passed
for all builds before timing. Each run is characterization, not a default
promotion or a universal performance claim.

Raw evidence:

- `evidence/baseline/native-workload-benchmark-v1.json`
- SHA-256: `6ddd6fb9a8fd6a3c656b6ac0970d1e5ba5f44e05cea59da8aaefd888cb15deaa`
- Native object hashes: `evidence/baseline/native-artifact-sha256sums.txt`
- Host: Linux x86-64, kernel `7.0.0-31-generic`; compiler/toolchain provenance
  is recorded in the raw JSON.
- PMU counters: unavailable by policy (`perf_event_paranoid=4`); no dynamic
  hardware-counter or spill claim is made.

O1 PER object observations:

| Workload | `.text` bytes | ELF bytes | Function bytes | Instructions | Memory-operand instructions | Branches | Calls | Frame bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| energy | 36,304 | 160,584 | 15,179 | 2,754 | 953 | 789 | 1 | 2,144 |
| point cloud | 58,112 | 258,832 | 26,063 | 4,732 | 1,601 | 1,367 | 1 | 3,648 |
| raster | 68,491 | 312,136 | 31,216 | 5,666 | 1,898 | 1,715 | 1 | 4,192 |

Median nanoseconds per call and paired ratio versus PER:

| Workload | PER | EXACT | EXACT/PER | HYBRID | HYBRID/PER |
| --- | ---: | ---: | ---: | ---: | ---: |
| energy | 19,056.135 | 18,339.890 | 1.0229, inconclusive | 18,634.354 | 1.0868, inconclusive |
| point cloud | 13,371.121 | 12,389.221 | 1.0806, material improvement | 12,300.643 | 1.0860, material improvement |
| raster | 12,813.622 | 11,318.139 | 1.0958, material improvement | 11,986.508 | 1.0530, inconclusive |

Compact-EA showed no material change for these three workloads. The small
sample of workloads and single run limit generalization. PER remains the
default; EXACT/HYBRID are not promoted.

The `Function bytes`, `Instructions`, memory, branch, call, and frame columns
above describe the exported workload symbol; `.text` and ELF bytes describe
the containing FFI shared object. They are intentionally separate accounting
domains.

The independent-lab 21-sample recharacterization is
`SamDevlab/S3-Benchmarks:reports/s3-1.9-native-observatory-lab/experiments/EXP-S3-19-NATIVE-OBS-001.json`.
The first direct run's raw SHA-256 is
`6ddd6fb9a8fd6a3c656b6ac0970d1e5ba5f44e05cea59da8aaefd888cb15deaa`; the
independent replication's raw SHA-256 is
`897fade8e52d459bf505c89d52a3f307196757d0ea1ea99e993914e968a9e721`.
Point-cloud showed material paired EXACT and HYBRID classifications in both
runs. Raster EXACT repeated as material while HYBRID stayed inconclusive.
Energy changed from inconclusive to material for both EXACT and HYBRID, so
those energy conclusions remain INCONCLUSIVE across runs. This disagreement is
preserved, not averaged away. The RQ6 result is PARTIAL; PER remains the
default, and no broad policy recommendation follows.

## Observatory prototype and first workload attribution

`tools/s3_native_observatory.py` creates plain and DWARF-line-instrumented
ELF64 x86-64 relocatable objects, requires byte-identical `.text`, parses
sections and function symbols, and reports machine instructions with either
an Assembly-origin mapping or explicit `UNMAPPED`. v4 also parses raw
instruction encodings to account for `.text` bytes as attributed, unmapped, or
undecoded; it does not fill gaps by inference. It does not measure dynamic
execution or PMU events.

The tool ran on the three continuity workloads at the same S3 source commit and
O1/PER baseline configuration. These are structural observations from
`generate_native_assembly`, not timings and not the FFI shared objects used by
the native-workload timing harness.

| Workload | `.text` bytes | Instructions | Mapped / unmapped instructions | Mapped fraction | Attributed / unmapped / undecoded bytes | `.text` SHA-256 | v4 JSON SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| point cloud | 58,106 | 11,151 | 4,216 / 6,935 | 37.8083% | 22,864 / 35,242 / 0 | `427e701b884297feb6b4877bf33c9108e03b3872cfe7d8d2c78f87613b138b06` | `4a02da5d8e65194e018ca3f902a62a192d04442d81bc1a6a7898ca34d106e426` |
| raster | 68,482 | 13,034 | 5,125 / 7,909 | 39.3202% | 27,721 / 40,761 / 0 | `c2ea9faec2a3487d8f8f486f56c6506c77023e442633311fe02a1cbef917e7d2` | `6a3eb1c63c54a031d47064ddf8574df650cdf6a184e0dd4e0259b69cad3c31f2` |
| energy | 36,295 | 7,239 | 2,506 / 4,733 | 34.6180% | 13,525 / 22,770 / 0 | `59ec376454f4588bcea23965932945254186e43b8f32898d0868ca84d61a2c01` | `f4794705de73e4a4e4f77607c757a585e3185376eaa5a99fa37c820947238eb2` |

Raw reports are under `evidence/observatory/`; v1-v3 are retained and v4 adds
raw-encoding byte accounting. Each records source SHA, source commit/tree,
tool SHA, generated assembly SHA, codegen-report SHA, compiler,
readelf/objdump versions, object hashes and explicit unknown counts. The source
commit/tree is `211b1aecec756be42516322429720018f54001e7` /
`08289d214832e856d46e14ef941239649e9f4063`; compiler inputs remained at that
revision. The v4 tool SHA is
`248563a0e642b25b1f9540341ad15a5a3c081ddfe4195b737ad8036fb25796ba`.

Point-cloud was observed twice. Both runs had identical `.text` size/hash,
machine-instruction rows, function rows, and plain-object SHA. The complete
DWARF-instrumented object differed in size by 16 bytes and therefore in its
whole-object hash; debug metadata is not bit-identical across output locations.
The measured code section and attribution were stable.
The repeat report SHA-256 is
`0d8a94c267b250db78a99b05e19b80bc9a72f23fdcd7b3161f6d060a177c0b11`; v4
reproduced the same `.text` hashes and instruction/mapping counts. The embedded
point-cloud codegen-report digest is
`a6606f28330a2f35082800dbf49fd5b37ed1158efe8f544af362e52481ca093f`.

### Reconciliation of instruction-origin counts

The Observatory reports 6,935 unmapped point-cloud `.text` instructions. The
pinned codegen report
`reports/s3-1.8-machine-intelligence-portable-compute/evidence/baseline/engineering.point-cloud-summary.v1.codegen.json`
reports 6,399 under `summary.unattributed_generated_runtime`. These are
different, disjoint scopes, not conflicting totals:

```text
whole .text unmapped                       6,935
source-function unmapped: point_cloud      527
source-function unmapped: main                9
unattributed generated runtime            6,399
527 + 9 + 6,399                            6,935
```

The 536 function-local unmapped instructions have a source-function symbol
but no exact Assembly-origin span (including function prologue/epilogue
scaffolding). The remaining 6,399 are outside those source-function spans and
form the runtime bucket. v3 symbol classification independently partitions
all 6,935 as 5,189 `SOURCE_FUNCTION_UNMAPPED`, 1,732
`S3_RUNTIME_HELPER_SYMBOL`, and 14 `S3_ENTRY_STUB`. Symbol class is not
instruction-level Assembly attribution. The stored codegen JSON's raw Windows
bytes differ from canonical JSON bytes due checkout line endings; its counts
are used for this scope reconciliation.

## Logical dynamic profiling

`evidence/profiling/logical-dynamic-profile-v3.json` records logical block
visits from a separate correctness-checked native build. Instrumentation uses
balanced `pushfq; inc [rip+counter]; popfq` at each S3 Assembly block label;
baseline and instrumented outputs both match the independent expected results
and each other for all three workloads. The report pins S3 commit/tree,
compiler-source hashes, generated assembly, codegen reports, and baseline and
profiled shared objects. No timing or PMU data was collected; PMU is
unavailable by policy.

| Workload | Logical block visits | Estimated uninstrumented structural weight | Largest dynamic block | Largest weighted mapped origins |
| --- | ---: | ---: | --- | --- |
| energy | 2,036 | 140,398 | `while_body_33`: 168 visits, 74,592 weight | memory 72,465; constants 25,641; compute 20,241 |
| point cloud | 1,304 | 121,197 | `while_body_63`: 64 visits, 38,400; `while_body_30`: 64 visits, 31,680 | memory 63,438; compute 24,900; constants 21,360 |
| raster | 1,622 | 85,806 | `while_body_69`: 64 visits, 9,792; `switch_negative_115`: 46 visits, 9,200 | memory 41,378; constants 15,856; compute 12,094 |

Structural weight is static native instructions per Assembly block multiplied
by observed block entries. It is not a retired-instruction count: a lowered
ternary branch can skip instructions within its source block. The profile
excludes runtime-helper execution and 347/536/640 static native function
instructions per call outside the profiled Assembly blocks (energy,
point-cloud, raster). All native instructions inside profiled blocks had an
Assembly-origin mapping; whole-object unknown counts remain as above. Exact
opcode totals, including dynamic `TCALL` and memory operations, are in the raw
JSON.

The leading structural observation is not a runtime-cause claim: memory
origins account for roughly 48-52% of the profiled dynamic structural weight,
with control flow, constants, moves and compute also substantial. The
observation covers three fixed small datasets; it does not establish scaling,
cycles, or hardware execution counts.

## Initial optimization experiment signal

The independent paired 21-sample protocol in
`SamDevlab/S3-Benchmarks:reports/s3-1.9-native-observatory-lab/evidence/confirmation-v1/native-workload-benchmark-v1.json`
also tested O0/O1, PER/EXACT_SEGMENT/LOOP_HYBRID, and Compact-EA after
correctness checks. O0 versus O1 was within the predeclared 5% no-material-
change interval for all three workloads. Compact-EA was not applied to these
functions, so its timing cells are not measurements of transformed code.
EXACT_SEGMENT showed repeated material paired improvements for point cloud and
raster; energy differed between original and replication and remains
INCONCLUSIVE across runs. LOOP_HYBRID repeated as material for point cloud;
raster remains inconclusive and energy disagreed across runs. These are
budget-accounting policy candidates, not a compiler-optimizer change. PER
remains the default and no policy is promoted.

### EXP-S3-19-OPT-001: exact-cell local mutable-load forwarding

The bounded Linux x86-64 experiment tested a non-production IR rewrite:
forward a mutable `LOAD` only when the same memory object, unchanged index
register version, initialization flag, and result type recur within one basic
block. Stores, calls, references, terminators, unknown operations, index/result
redefinitions, and block boundaries invalidate facts. The rewrite preserves
one IR operation by replacing the later load with `MOVE`; it does not alter the
production pipeline and performed no timing or PMU measurement.

The candidate and baseline native outputs matched each other and the
independent references for all workloads. Across 220 mutable loads, zero met
the exact forwarding precondition:

| Workload | Loads before | Forwarded | Loads after | Correctness |
| --- | ---: | ---: | ---: | --- |
| energy | 44 | 0 | 44 | PASS |
| point cloud | 91 | 0 | 91 | PASS |
| raster | 85 | 0 | 85 | PASS |

Classification: `REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS`. This rejects
only the tested same-block exact-cell rule on these pinned O1 workloads; it
does not refute broader memory-origin reduction, alias-aware value locality,
or cross-block dataflow. The precise evidence is
`evidence/optimizations/EXP-S3-19-OPT-001-local-load-forwarding.json`
(SHA-256 `9f7ed0341f867203ca4c464d5f14f3951ab88371a564c4a8292d4c3334f2d571`).
It pins the S3 commit/tree, Linux/Python/native compiler, and hashes of the
experimental driver and focused tests.

The initial ranking is preserved as
`evidence/optimizations/discovery-ranking-v2.json`; ranking v3 below supersedes
it for current reference and allocator triage. V2 preserves the broad
memory-origin hypothesis as open, records the exact local rule as rejected,
and keeps structural scores separate from measured runtime. Neither this
result nor the repeated budget-policy timings promote a production optimization
or default.

### Current reference and allocator facts in discovery ranking v3

Three O1 reference reports were generated with the campaign-base compiler for
the exact workload source SHA-256 values already pinned by Observatory v4 and
the dynamic profile. The reports are under `evidence/references/`; each records
commit `211b1aecec756be42516322429720018f54001e7`, source syntax 0.6, the
analysis/tool hashes, and a dirty worktree flag caused by the local research
artifacts. No tracked production/compiler source was changed in this phase.
Across 8 modeled references, all 8 have known origins and `NO_ESCAPE`; 3 are
mutable and no unknown effects were counted. The analysis itself explicitly
keeps `transformation_authorized=false` and documents what it does not prove.
These are diagnostic facts, not a safety certificate or transformation
authority.

The ranker now consumes the current v4 per-function allocation records as
well: 1,024 virtual registers across eight functions, six static
stack-resident virtuals in one function, and maximum peak liveness of 11.
`dynamic_spills` remains `NOT_MEASURED`; static stack residence is not a spill
counter and cannot explain observed native stack/memory structure. Accordingly,
this evidence does not select allocator replacement. Ranking v3 preserves the
same tier-first ordering and scores as v2; the added facts refine scope and
triage without manufacturing a causal score or granting optimization
authority. The local forwarding experiment remains rejected for the exact
same-block rule, while broader memory-origin investigation remains open.

### Current vector-legality triage

The existing analyzer was rerun at O1 against the same three pinned workload
source files. The current reports in `evidence/vector-legality/` cover five
loops: zero are proven vectorizable, zero are proven illegal, and all five
remain `UNKNOWN`. Every loop reports the same missing proof families:
canonical affine induction, access-range/immutable-origin proof, and general
inter-iteration memory dependence. This is current-source evidence that the
existing analysis did not reduce the 1.8 unknown frontier; it does not justify
SIMD or parallel execution. No vector-analysis implementation was changed.

Do not compare the Observatory's whole-`.text` instruction count with the
older benchmark's `static_machine_instructions` field: the latter disassembles
only the exported workload symbol. The benchmark compiles the FFI-specific
`generate_ffi_assembly` path, while this tool emits the standalone generic
native path and counts every function in the ELF `.text`. The separately
reported baseline `.text` byte totals also differ by 6–9 bytes between these
generation paths. A same-artifact comparison requires instrumentation of the
same FFI object and is not claimed here.

## Open constraints

- The S3 reference/effect/escape analyses have not yet been extended by this
  checkpoint; current workload reports exercise their existing experimental
  coverage only.
- Machine IR, allocator changes, SIMD, and a second target remain research
  questions, not implemented capabilities.
- The independent benchmark executor has completed one pinned 21-sample
  replication; arbitrary-SHA replay and a broader historical replay protocol
  remain unqualified.
- Existing 1.7 evidence did not establish material benefit on the three main
  hot kernels; this 1.8 characterization uses the current PER baseline and
  must not be conflated with that historical result.
