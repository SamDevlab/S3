# Proof-Gated Value-Cost Findings

## Scope and provenance

These are research-only Linux x86-64 native characterizations against the
S3 1.11 control source. The transformations run after O1 compilation in an
isolated experiment tool; neither is wired into the production optimizer.
Candidates were checked against benchmark references and baseline native
outputs. All timing below is `CHARACTERIZATION_ONLY`; there is no native
speedup claim and no production promotion.

```text
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
EXPERIMENT_TOOL_SHA256=6315aa6cc92c67457a651f19d657b86d6f24d4c690e35d3aa0257cb1aca03777
NATIVE_TARGET=Linux x86-64
OPTIMIZATION=O1
INSTRUCTION_BUDGET=PER
HARDWARE_COUNTERS=UNAVAILABLE_BY_POLICY (perf_event_paranoid=4)
```

The final artifact-aware evidence is:

- `evidence/EXP-S3-111-VALUE-COST-001-artifacts.json`, SHA-256
  `8a834acf62d0b0314d34fcf62a81a639409d97a260980a7eb4c770a37940d3a7`.
- `evidence/EXP-S3-111-VALUE-COST-002-artifacts.json`, SHA-256
  `376718d5df154f383a35f6eb0ee7bd0a9207a8e5d76b170f5cd79aa0bb9a06ba`.
- `evidence/EXP-S3-111-VALUE-COST-002-confirmatory.json`, SHA-256
  `c65304d9bfec1bdca20f4092322bdafc20ff2bc8150b33f22e69094bfb868330`.

Earlier reports remain preserved, not overwritten: `...001-final.json`
and `...002.json` were produced with the earlier tool SHA
`5c162c0105bc1b5f3ee4ca0904df5a57f77e22467b0d5e6c8680e87c117c06d4`;
`...001-run2.json` preserves another earlier run. They are historical
measurements, not the latest schema/tool identity.

The two newest S3 point-cloud trials and independent Bench trial use the same
native artifacts: baseline SHA-256
`fc640b39ef8c97304a45800bd48a7b5a779c046858f41988b6b87fff142bbd07`,
candidate SHA-256
`5557cc8de4c9d065ade26a11449bc8961a2059d10a4266809a63938b4194a714`.

## Structural results

The columns are candidate-minus-baseline static native-object deltas, not
runtime costs. Positive memory-reference deltas are structural regressions.

| Experiment / workload | Eligible | `.text` | Instructions | Memory refs | Stack refs | Branches | Frame bytes | Peak-live / stack-resident delta | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SSA substitution / energy | 2 | -350 | -26 | -10 | -10 | -8 | -16 | 0 / 0 | Select |
| SSA substitution / point cloud | 2 | -350 | -26 | -10 | -10 | -8 | -16 | 0 / 0 | Select |
| SSA substitution / raster | 6 | -942 | -78 | -3 | -3 | -24 | -48 | +1 / +16 | Reject |
| STORE-to-LOAD / energy | 12 | -758 | -36 | +48 | +48 | -18 | +16 | +3 / +35 | Reject |
| STORE-to-LOAD / point cloud | 39 | -3,007 | -123 | +3 | +3 | -62 | +80 | +5 / +30 | Reject |
| STORE-to-LOAD / raster | 18 | -437 | -52 | +228 | +228 | -26 | +48 | +3 / +133 | Reject |

Both transformations preserve reference correctness and exact baseline vs
candidate outputs in all workloads. The STORE-to-LOAD candidate reduces
`.text`, static instructions, and branches, but increases memory/stack
references and register-pressure indicators. The current strict
Pareto-plus-pressure guard therefore rejects it in every workload. This
guard is a conservative policy, not an empirically validated predictor of
runtime direction.

## Timing evidence

The point-cloud STORE-to-LOAD candidate has a replicated, workload-specific
timing signal on the same exact binaries:

| Run | Protocol | Baseline / candidate median ratio | 95% interval | Classification |
| --- | --- | ---: | ---: | --- |
| Earlier S3 run (`...002.json`) | Paired S3 characterization | 1.0256 | [1.0107, 1.0381] | NO_MATERIAL_CHANGE_WITHIN_5_PERCENT |
| S3 artifact-aware run #1 (`...002-artifacts.json`) | 3 warmups, 21 alternating pairs, 1,000 iterations/sample | 1.1110 | [1.0926, 1.1280] | MATERIAL_IMPROVEMENT |
| S3 confirmatory run (`...002-confirmatory.json`) | Same paired protocol, new seed | 1.0879 | [1.0789, 1.1379] | MATERIAL_IMPROVEMENT |
| Bench independent run (`candidate-replay/EXP-S3-111-VALUE-COST-002-point-timing.json`) | Interleaved, 3 warmups, 21 samples, 1,000 calls/sample | 1.0904 | [1.0617, 1.1801] | MATERIAL_IMPROVEMENT |

For the Bench run, baseline and candidate medians were 17,929.709 and
16,834.066 ns/call. It validates the same exact native binary SHAs and exact
equal output hash. The independent timing report SHA-256 is
`45517665fac2ccd9b7612ef921708c84c80416f8c629ca7c1044ae37630d70cb`.
Its timing helper SHA-256 is
`761550a64532ed3d471b1a76a90d3decc5ada38bdc094defbe40f71f397fe448`;
the replay helper SHA-256 is
`b163828224d67bc7404726f165804dc846fd8d0d9fe26119598e25d568d79116`.

The initial earlier result did not cross the 5% materiality threshold, so
the history is retained as evidence of variability rather than erased. The
two newer S3 trials and one independent Bench trial agree on a material
point-cloud signal, but this does not establish a microarchitectural cause,
generalize to other workloads, validate the static guard, or authorize
selection. Energy and raster timing remain inconclusive or below the
materiality threshold. Hardware counters remain unavailable by host policy
and were not bypassed.

## Decision

`EXP-S3-111-VALUE-COST-002` is a real trade-off frontier: exact candidate
correctness and a replicated point-cloud characterization signal coexist
with worsened static memory/stack traffic and pressure. The candidate
remains rejected by the unchanged conservative gate and is research-only.
The performance cause and applicability boundary are open questions; no
compiler default, production optimizer, PER semantics, or strict
floating-point behavior changed.
