# S3 0.36 — Segmented BigInt and Lucas-Lehmer Performance Lab

**Status**: closed

## Objective
This milestone temporarily interrupts the S3 rendering pipeline to conduct an experimental numerical performance laboratory. We implemented an exact segmented big integer library using both logical base-300 limbs (canonical to S3 buffers) and dense physical binary limbs (30-bit blocks).

We successfully ran Lucas-Lehmer tests on the Mersenne primes $M_{44497}$ and $M_{44501}$.

## Implementation Notes
- **Experimental Code**: This code is a performance lab prototype. It does not introduce a native BigInt type into the compiler proper.
- **Hardware Profile**: Measured on Ryzen 5 3400G.
- **Engines**: `python-int` native (used as baseline) against our `binary-limbs-sequential` and parallel engines.
- **Orchestration**: The system imposes a mandatory ETA limit and a hard memory/time watchdog via `multiprocessing`.

## Conclusion
The physical binary chunks work correctly, successfully matching Python's native output for all known small and large positive/negative test cases. The sequential engine ETA was ~4000 seconds for $M_{44497}$, compared to ~15 seconds for `python-int` (which leverages GMP under the hood). Parallel chunks reduced this slightly but are bound by Python's multiprocessing inter-process communication overhead.

## Recommendation for 0.37
We recommend closing this experimental lab and returning to the S3 textual renderer self-hosting effort (e.g. S3 0.37 for strings and calls). No AI acceleration claims are made, although techniques for block reduction can be extrapolated for data analysis workloads in the future.
