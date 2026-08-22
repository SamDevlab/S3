# M2.08 Reproducible Cross-Target Install

BASE_SHA=`905edbe8b726c5ce360bbf1afc63283267fda543`

FINAL_SHA=`905edbe8b726c5ce360bbf1afc63283267fda543`

FILES_CHANGED=none

PRODUCTION_CHANGE=NO

TEST_CHANGE=NO

LINUX_X86_INSTALL=PARTIAL

REPRODUCIBILITY=PASS_CONTRACT

LINUX_AARCH64_INSTALL=DEFERRED_BY_ENVIRONMENT

MACOS_ARM64_INSTALL=DEFERRED_BY_ENVIRONMENT

INSTALL_SMOKE=PASS_HOSTED_CONTRACT

The focused toolchain distribution, AArch64 artifact, Mach-O artifact, and
release stability suites passed their available contract coverage. Linux
native installation and the non-host targets cannot be certified on the
current Windows x64 host without the required target environments.

T1=PASS

T2=PASS_FOCUSED_INSTALL_SUBSYSTEM

T3=NOT_RUN

T4=NOT_RUN

BENCHMARKS=NOT_RUN

DEFERMENTS=Linux native, Linux AArch64 execution, and macOS ARM64 execution
remain environment dependent.

BLOCKERS=ENVIRONMENT

STATUS=PARTIAL
