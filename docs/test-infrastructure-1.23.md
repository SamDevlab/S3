# Milestone 1.23 Test Gates

The six pytest capabilities are orthogonal and may be combined:

- `s3_fast`: deterministic first-response correctness;
- `s3_contract`: explicit IR, optimizer, ABI, frame, renderer, allocator, or backend invariants;
- `s3_differential`: semantic comparison between execution or compilation modes;
- `s3_native`: native toolchain or executable behavior;
- `s3_slow`: deliberately expensive/stress correctness cases;
- `s3_benchmark`: s3bench infrastructure and schema correctness, not performance campaigns.

Canonical commands are `pytest -m "s3_fast"`, `pytest -m "s3_contract"`, `pytest -m "s3_differential"`, `pytest -m "s3_native"`, `pytest -m "s3_slow"`, and `pytest -m "s3_benchmark"`. The full suite remains the unfiltered `python -m pytest` command. A targeted or fast pass never substitutes for the final full regression gate.

`s3_slow` is reserved for intentionally expensive tests. The large tokenizer corpus cases identified by the 1.23 renovation audit remain unhidden as accidental-slow inputs for Milestone 1.24. Performance timing and benchmark campaigns remain outside the correctness fast gate.

The implicit-register contract inventory covers the actual backend sequences `rep stosb`, `syscall`, and `div/idiv`. `rep stosb` overlaps allocatable `rdi`/`rcx` and is required to preserve them in the RA-enabled metadata path. Runtime `syscall` and division sequences are standalone runtime regions and are not allocator-managed logical-value regions.
