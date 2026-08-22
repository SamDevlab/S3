# M2.02 Linux x86-64 Native Conformance

BASE_SHA=`8a044a28ca9f37c95697d7fa42c55f10ecf0b299`

FINAL_SHA=`8a044a28ca9f37c95697d7fa42c55f10ecf0b299`

FILES_CHANGED=none

PRODUCTION_CHANGE=NO

TEST_CHANGE=NO

LINUX_X86_64_NATIVE_CONFORMANCE=DEFERRED_BY_ENVIRONMENT

DIFFERENTIAL_CORRECTNESS=PARTIAL

ABI=PASS_STRUCTURAL

DETERMINISM=PASS_STRUCTURAL

The focused native and differential suites passed their hosted and structural
portions. Native execution was not available on this Windows host: GCC is not
installed and WSL has no configured distribution. Skips remain environment
deferments, not PASS evidence.

T1=PASS_FOCUSED_STRUCTURAL

T2=PASS_FOCUSED_NATIVE_CONTRACTS

T3=NOT_RUN

T4=NOT_RUN

BENCHMARKS=NOT_RUN

DEFERMENTS=Linux x86-64 native execution unavailable on the current host.

BLOCKERS=ENVIRONMENT

STATUS=PARTIAL
