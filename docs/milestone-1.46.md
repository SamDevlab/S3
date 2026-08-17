# Milestone 1.46 - Reproducible S3 Test Runner

Status: COMPLETE.

## Delivered contract

- convention-based `s3 test` entrypoint over manifest-declared S3 sources;
- deterministic discovery and lexicographic test ordering;
- fixed seed, bounded timeout, frame and instruction limits;
- hosted reference execution and Linux x86-64 native differential execution;
- explicit capability declaration and capability-denial results;
- machine-readable `s3.test-report.v1` reports with stable result taxonomy;
- timeout, resource-limit, and infrastructure failures kept distinct.

The runner does not add a property-testing language, debugger, benchmark
framework, or replacement for compiler CI. Native unavailability is an
explicit `SKIP`; a native toolchain/build failure is an infrastructure
failure.

## Verification

- focused runner tests: PASS (7);
- hosted deterministic ordering and report identity: PASS;
- resource-limit and capability-denial classification: PASS;
- compileall: PASS;
- diff check: PASS;
- Linux x86-64 native fixture over `s3-vm`: PASS (`program returned: 2`);
- full suite on exact candidate `bf34bd0597b310facd8bf74e837a90ac1ccdd2e4`:
  terminal exit 0;
- no benchmark, remote write, Docker, virtualization, or shutdown action.

## Boundary

M1.46 is closed. M1.47 is the bounded Python Stable ABI and buffer boundary.
Linux C/Python certification remains an environment-specific gate for M1.47;
the accepted environment policy is documented in the future-toolchain reports.
