# M1.49 Architecture Options

| Option | S3 fit | Tooling/runtime | Cost/risk | Decision |
|---|---|---|---|---|
| WASI Preview 1 core module | High: direct i32/i64/f64 plus linear-memory descriptors; maps to current IR and M1.48 blocking profile | Mature `wasi_snapshot_preview1` and Wasmtime Preview 1 support | Low-to-medium; explicit ABI work, no component lowering | **Selected** |
| WASI 0.2 / Component Model | Medium: canonical lift/lower and WIT are powerful but require a new component ABI and resource model | Stable direction, but adds component tooling and interface versioning | Very high; conflicts with current no-component IR and no async semantics | Rejected for M1.49 |
| WASI 0.3/component async path | Low: introduces async/future/stream semantics excluded by M1.48 | Evolving official design | Very high; would expand roadmap semantics | Rejected |

The selected option is the only one that closes M1.49 without adding a new
language-level component or concurrency model.
