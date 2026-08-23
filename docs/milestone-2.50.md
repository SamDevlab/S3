# M2.50 Product and Toolchain Integration Checkpoint

M2.50 integrates the M2.41-M2.49 development train through the explicit
`level-c` profile in `tools/s3test.py`.

The profile selects exactly one focused test shard for each completed
milestone, in deterministic order:

- M2.41 workspace semantic graph
- M2.42 LSP project intelligence
- M2.43 Linux native conformance
- M2.44 dynamic HPACK
- M2.45 signed registry consumption
- M2.46 async/network soak
- M2.47 repeatability analysis
- M2.48 experiment promotion policy
- M2.49 cross-target evidence

Level-C is an integration checkpoint, not T4. It does not execute the global
suite, does not create benchmark evidence, and does not turn platform skips
into native passes. Environment-specific evidence remains explicit in the
test report.
