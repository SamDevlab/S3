# S3 0.37 Tiled BigInt Square Performance Lab

## Hardware Profile
- **OS**: Windows
- **CPU**: AMD Ryzen 5 3400G with Radeon Vega Graphics    
- **Logical CPUs**: 8
- **Physical Cores**: 4

## Kernel Comparison (1024 limbs, dense-random)

| Kernel | Time (s) | Speedup vs Python | Status |
|---|---|---|---|
| python-int | 0.001519 | 1.00x | completed |
| schoolbook | 0.307924 | 0.00x | completed |
| symmetric | 0.103337 | 0.01x | completed |
| tiled-16 | 0.122322 | 0.01x | completed |
| tiled-32 | 0.111396 | 0.01x | completed |
| tiled-64 | 0.103813 | 0.01x | completed |
| tiled-128 | 0.102637 | 0.01x | completed |
| tiled-16-P1 | 0.419577 | 0.00x | completed |
| tiled-16-P2 | 0.372296 | 0.00x | completed |
| tiled-16-P4 | 0.408369 | 0.00x | completed |
| tiled-32-P1 | 0.396327 | 0.00x | completed |
| tiled-32-P2 | 0.356496 | 0.00x | completed |
| tiled-32-P4 | 0.413200 | 0.00x | completed |
| tiled-64-P1 | 0.402682 | 0.00x | completed |
| tiled-64-P2 | 0.356510 | 0.00x | completed |
| tiled-64-P4 | 0.385484 | 0.00x | completed |
| tiled-128-P1 | 0.399591 | 0.00x | completed |
| tiled-128-P2 | 0.344517 | 0.00x | completed |
| tiled-128-P4 | 0.425314 | 0.00x | completed |
| python-int | 0.001441 | 1.05x | completed |
| schoolbook | 0.351804 | 0.00x | completed |
| symmetric | 0.112370 | 0.01x | completed |
| tiled-16 | 0.134319 | 0.01x | completed |
| tiled-32 | 0.143162 | 0.01x | completed |
| tiled-64 | 0.128892 | 0.01x | completed |
| tiled-128 | 0.119389 | 0.01x | completed |
| tiled-16-P1 | 0.533428 | 0.00x | completed |
| tiled-16-P2 | 0.481213 | 0.00x | completed |
| tiled-16-P4 | 0.524223 | 0.00x | completed |
| tiled-32-P1 | 0.554297 | 0.00x | completed |
| tiled-32-P2 | 0.453985 | 0.00x | completed |
| tiled-32-P4 | 0.512558 | 0.00x | completed |
| tiled-64-P1 | 0.538398 | 0.00x | completed |
| tiled-64-P2 | 0.441715 | 0.00x | completed |
| tiled-64-P4 | 0.564855 | 0.00x | completed |
| tiled-128-P1 | 0.471849 | 0.00x | completed |
| tiled-128-P2 | 0.478857 | 0.00x | completed |
| tiled-128-P4 | 0.499969 | 0.00x | completed |

## Tile Tuning (1024 limbs, dense-random)

| Tile | Workers | Time (s) | Efficiency | Status |
|---|---|---|---|---|
| 8 | 1 | 0.147389 | - | completed |
| 8 | 1 | 0.621274 | 0.24 | completed |
| 8 | 2 | 0.505035 | 0.15 | completed |
| 8 | 4 | 0.539612 | 0.07 | completed |
| 16 | 1 | 0.152252 | - | completed |
| 16 | 1 | 0.558368 | 0.27 | completed |
| 16 | 2 | 0.451910 | 0.17 | completed |
| 16 | 4 | 0.566927 | 0.07 | completed |
| 32 | 1 | 0.164182 | - | completed |
| 32 | 1 | 0.494244 | 0.33 | completed |
| 32 | 2 | 0.466967 | 0.18 | completed |
| 32 | 4 | 0.553638 | 0.07 | completed |
| 64 | 1 | 0.127939 | - | completed |
| 64 | 1 | 0.513510 | 0.25 | completed |
| 64 | 2 | 0.476347 | 0.13 | completed |
| 64 | 4 | 0.559520 | 0.06 | completed |
| 128 | 1 | 0.131113 | - | completed |
| 128 | 1 | 0.526740 | 0.25 | completed |
| 128 | 2 | 0.483086 | 0.14 | completed |
| 128 | 4 | 0.520510 | 0.06 | completed |
| 256 | 1 | 0.158023 | - | completed |
| 256 | 1 | 0.506686 | 0.31 | completed |
| 256 | 2 | 0.440612 | 0.18 | completed |
| 256 | 4 | 0.541051 | 0.07 | completed |

**Best sequential tile**: 64 (0.127939 s)

## Scaling Analysis

| Limbs | Tile | Workers | Time (s) | Status |
|---|---|---|---|---|
| 512 | 64 | 1 | 0.029415 | completed |
| 512 | 64 | 1 | 0.405424 | completed |
| 512 | 64 | 2 | 0.394388 | completed |
| 512 | 64 | 4 | 0.465933 | completed |
| 1024 | 64 | 1 | 0.168524 | completed |
| 1024 | 64 | 1 | 0.526588 | completed |
| 1024 | 64 | 2 | 0.449878 | completed |
| 1024 | 64 | 4 | 0.521227 | completed |
| 2048 | 64 | 1 | 0.566433 | completed |
| 2048 | 64 | 1 | 1.208707 | completed |
| 2048 | 64 | 2 | 0.819599 | completed |
| 2048 | 64 | 4 | 0.821679 | completed |

### Empirical Scaling (Sequential)
| Size | Time (s) | Alpha |
|---|---|---|
| 512->1024 | 0.405424->0.526588 | 0.38 |
| 1024->2048 | 0.526588->1.208707 | 1.20 |

### Calibration (1024 limbs)
| Kernel | Status | Median Iter (ms) |
|---|---|---|
| schoolbook | completed | 295.38 |
| symmetric | completed | 97.60 |
| tiled-16 | completed | 110.88 |
| tiled-32 | completed | 105.40 |
| tiled-64 | completed | 102.52 |
| tiled-128 | completed | 104.05 |
| schoolbook | completed | 359.18 |
| symmetric | completed | 110.14 |
| tiled-16 | completed | 136.79 |
| tiled-32 | completed | 125.49 |
| tiled-64 | completed | 135.65 |
| tiled-128 | completed | 121.16 |

## Conclusion
Tiled bigint square evaluation complete.
