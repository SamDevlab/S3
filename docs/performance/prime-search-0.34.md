# S3 0.34 Prime Search Benchmark Report

## Hardware Profile
- **OS**: Windows
- **CPU**: AMD Ryzen 5 3400G with Radeon Vega Graphics    
- **Logical CPUs**: 8
- **Physical Cores**: 4

## Best Configuration
- **Segment Size**: 65536 bytes
- **Workers**: 4

## Full Benchmark Results
| Limit | Simple Sieve (ms) | Seq Sieve (ms) | Par Sieve (ms) | Speedup | Count |
|---|---|---|---|---|---|
| 1000000 | 141.36 | 71.36 | 296.84 | 0.24x | 78498 |
| 10000000 | 1854.14 | 930.80 | 519.17 | 1.79x | 664579 |
| 100000000 | N/A | 7920.80 | 3038.12 | 2.61x | 5761455 |
