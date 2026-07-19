# S3 0.37 — Tiled BigInt Square Performance Lab

**Status**: closed

## Objective

This milestone investigates whether a tiled (blocked) approach to bigint squaring can improve the performance bottleneck identified in S3 0.36. The S3 0.36 laboratory established a segmented bigint implementation (BinaryLimbBigInt with 30-bit limbs) and demonstrated that the schoolbook square kernel is the dominant cost in Lucas–Lehmer testing. This milestone evaluates three kernel variants:

1. **schoolbook baseline** — the original O(L²) double loop with per-product carry
2. **symmetric** — exploits a[i]·a[j] = a[j]·a[i], computing only the upper triangle and doubling off-diagonal terms
3. **tiled** — divides the logical product matrix into tiles of configurable size, processes only tiles where tile_j ≥ tile_i, and aggregates results via diagonal accumulators without materializing an L×L matrix

All kernels operate on the same 30-bit limb representation (base 2³⁰) and produce bit-exact results matching Python's native `int`.

## Implementation Notes

- **No L×L matrix materialization** — the tiled kernel accumulates directly into a 1D array of length 2L (diagonal indices i+j)
- **Symmetry across tiles** — only tiles with tile_j ≥ tile_i are processed; off-diagonal tiles contribute 2× the product
- **Persistent process pool** — parallel execution uses a single `ProcessPoolExecutor` per run; tiles are batched across workers
- **Phase-level metrics** — calibration, comparison, tuning, and scaling commands report separate timings
- **Timeout protection** — all benchmarks run under a hard timeout with process cleanup (`terminate` + `join`)

## Engines Evaluated

| Engine | Description |
|--------|-------------|
| python-int | Python's native `int` (GMP-backed) — reference only |
| schoolbook | Baseline double loop with per-product carry |
| symmetric | Upper-triangle only, off-diagonal ×2, single carry pass |
| tiled-* | Tiled sequential with tile sizes 8, 16, 32, 64, 128, 256 |
| tiled-*-P1/2/4 | Tiled parallel with 1, 2, 4 workers |

## Workloads

Three deterministic input patterns with fixed seed:

- **dense-random** — limbs uniformly distributed in [0, 2³⁰−1]
- **max-carry** — all limbs = 2³⁰−1 (stresses carry propagation)
- **sparse** — ~1/8 limbs non-zero (observes work avoidance potential)

## Hardware Profile

- **OS**: Windows
- **CPU**: AMD Ryzen 5 3400G with Radeon Vega Graphics
- **Logical CPUs**: 8
- **Physical Cores**: 4

## Key Findings

### Sequential Performance (1024 limbs, dense-random)

| Kernel | Time (s) | vs Schoolbook | vs Symmetric |
|--------|----------|---------------|--------------|
| schoolbook | 0.35 | 1.00× | 3.1× |
| symmetric | 0.11 | 0.32× | 1.00× |
| tiled-64 (best) | 0.13 | 0.37× | 1.15× |

**Symmetric is ~3× faster than schoolbook** by halving the number of products and moving carry out of the inner loop.

**Tiled sequential is slightly slower than symmetric** (1.15×) due to tile overhead (loop management, bounds checks) without parallelism benefit.

### Parallel Performance (1024 limbs, dense-random, best tile 64)

| Workers | Time (s) | Speedup vs Sequential | Efficiency |
|---------|----------|----------------------|------------|
| 1 | 0.53 | 0.25× | 25% |
| 2 | 0.45 | 0.29× | 14% |
| 4 | 0.52 | 0.25× | 6% |

**Parallel execution is slower than sequential** due to:
- Process spawning overhead
- IPC serialization/deserialization of limb arrays
- Aggregation and final carry in parent process
- Python's `multiprocessing` overhead dominates at this problem size

### Scaling Behavior (dense-random, tile 64, sequential)

| Limbs | Time (s) | Alpha (empirical) |
|-------|----------|-------------------|
| 512 | 0.03 | — |
| 1024 | 0.17 | 2.5 |
| 2048 | 0.57 | 1.8 |

Theoretical O(L²) predicts alpha = 2.0. Empirical alpha ranges 1.8–2.5, consistent with quadratic growth. The higher alpha at 512→1024 may reflect Python loop overhead becoming less dominant.

### Workload Comparison (1024 limbs)

| Pattern | Symmetric (s) | Tiled-64 (s) |
|---------|---------------|--------------|
| dense-random | 0.11 | 0.13 |
| max-carry | 0.10 | 0.12 |
| sparse | 0.07 | 0.07 |

Sparse workload shows no difference because all kernels still iterate over all tile pairs (no sparsity exploitation implemented).

## Conclusion

**Tiling does not improve sequential performance** over the symmetric kernel for pure Python implementation. The symmetric optimization (exploiting mathematical symmetry + deferred carry) already captures most of the available algorithmic improvement.

**Parallel tiling is counterproductive** at this problem size (1024–2048 limbs) due to Python's multiprocessing overhead (IPC, process spawn, aggregation). The break-even point would likely require much larger operands (thousands of limbs) or a compiled backend (C/Cython/Rust).

**No L×L matrix was materialized** in any kernel. Memory usage remains O(L) for all implementations.

## Recommendation for 0.38

- **Do not pursue Karatsuba** at this stage. The schoolbook bottleneck is already mitigated by the symmetric kernel (~3× speedup). Karatsuba would add significant complexity (recursive logic, base case thresholds, extra allocations) for marginal benefit on operand sizes < 5000 limbs.
- **Close this experimental lab** and return to the S3 textual renderer self-hosting effort.
- **Future work**: If larger operand sizes become relevant, evaluate tiled multiplication in a compiled extension (C/Cython) where cache locality and parallelism can be realized without Python overhead.

## Validation

- All kernels bit-exact against Python `int` for dense, max-carry, sparse patterns up to 2048 limbs
- Tiled tiles tested: 8, 16, 32, 64, 128, 256
- Workers tested: 1, 2, 4
- Timeout and process cleanup verified
- Golden diagnostics: passed
- S3 program checks: passed
- All unit tests: 44 passed