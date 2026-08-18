# Smart Testing Strategy

## Existing Foundation

M1.46 already owns manifest validation, deterministic discovery/order, bounded
hosted execution, optional native differential execution, explicit capability
denials, and `s3.test-report.v1`. The new layer is deliberately a thin
development orchestrator and does not replace that semantic runner.

## Tiers

| Tier | Meaning | Default use |
|---|---|---|
| T0 | syntax/import, schema, diff, manifest, tiny smoke | every small edit |
| T1 | directly affected files selected by `tests/test-impact.json` | normal implementation loop |
| T2 | complete milestone/subsystem profile | coherent feature change |
| T3 | bounded cross-subsystem shards with persisted per-file results | cross-cutting changes |
| T4 | complete repository certification | merge/release/global impact only |

`tools/s3test.py` supports `plan`, `sanity`, `affected`, `milestone`, `shard`,
`resume`, and `full`. `plan` emits changed file, selected test, reason, tier,
native requirement, and timeout. Selection is sorted and explainable.

## Correctness and Resume Contract

The fingerprint includes HEAD, staged/unstaged/untracked diff content, Python
version, platform, selected tests, impact-map version, and orchestrator version.
`.s3-test-state/` is ignored. A cached PASS is reusable only when the exact
fingerprint matches; otherwise resume fails closed. Each selected file runs in
its own outer process with a bounded timeout. A timeout is persisted as
`TIMEOUT`, while a non-zero pytest exit is `FAIL`.

After a failure, rerun the exact file once, repair, rerun its T1/T2 closure,
and only then resume invalidated T3/T4 nodes. Never restart all successful
nodes merely because one independent node failed. Automatic reruns are bounded
to two attempts per failing node by policy.

## Full Suite Policy

`FULL_SUITE_REQUIRED_WHEN`:

- merge candidate or release candidate;
- explicit user request;
- parser/semantic/IR contract with global impact;
- impact manifest marks the change `global_impact`;
- certification cannot be safely partitioned.

`FULL_SUITE_NOT_REQUIRED_WHEN`:

- docs-only or report-only work;
- narrow runtime fix with valid T1/T2/T3 evidence;
- isolated test addition;
- environment-only rerun;
- repairing one known failure node;
- roadmap research.

The historical post-1.50 full-suite evidence is therefore consumed rather than
restarted. A later T4 failure must preserve successful shard state and resume
only failed or fingerprint-invalidated nodes.

## Focused Validation

The orchestrator self-tests cover dynamic and native impact selection,
docs-only selection, changed-test selection, cross-cutting expansion, stable
ordering, fingerprint changes, state persistence, failure retention, timeout
classification, stale-cache rejection, and explainability. Focused validation
passed: `21 passed` including the existing M1.46 runner tests.
