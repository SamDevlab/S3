# M2.04 macOS ARM64 Native Execution

BASE_SHA=`4aadb56a17a11828760f5d424c2ea3d544ad74f3`

FINAL_SHA=`4aadb56a17a11828760f5d424c2ea3d544ad74f3`

FILES_CHANGED=none

PRODUCTION_CHANGE=NO

TEST_CHANGE=NO

ENVIRONMENT=NOT_MACOS_ARM64

MACHO=PASS_STRUCTURAL

ABI=PASS_STRUCTURAL

EXECUTE=DEFERRED_BY_ENVIRONMENT

DEFER_REASON=The current host is Windows x64; no real macOS ARM64 execution
environment is attached. Linux AArch64 evidence is not substituted for macOS.

Focused tests passed for Mach-O identity, AAPCS64 call layout, deterministic
emission, compiler lowering, and explicit execution deferment.

T1=PASS

T2=PASS_STRUCTURAL

T3=NOT_RUN

T4=NOT_RUN

BENCHMARKS=NOT_RUN

DEFERMENTS=macOS ARM64 execution deferred by environment.

BLOCKERS=ENVIRONMENT

STATUS=STRUCTURAL_ONLY
