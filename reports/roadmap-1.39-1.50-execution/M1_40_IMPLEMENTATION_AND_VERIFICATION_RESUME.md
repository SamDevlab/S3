# M1.40 Implementation and Verification Resume

## Checkpoint

    MILESTONE=1.40
    TITLE=Deterministic Ordered User Collections
    BASE_IMPLEMENTATION=6cea5b5
    IMPLEMENTATION_HEAD=c9fc6f4
    REMOTE_WRITES=NO

M1.40 adds the closed source types tryte_vector, i64_vector, and f64_vector.
They share the M1.39 move, borrow, allocator, exact-capacity, and deterministic
trap contract. The physical representation is a private descriptor with
element-specific widths; no public generic syntax or pointer value was added.

## Evidence

    FOCUSED_M140=PASS (10 tests)
    SHARED_REGRESSION=PASS
    COMPILEALL=PASS
    DIFF_CHECK=PASS
    FULL_SUITE_INITIAL_DIAGNOSTIC=FAIL (one legacy string diagnostic)
    LEGACY_DIAGNOSTIC_REPAIR=PASS
    FULL_SUITE_TERMINAL=YES
    FULL_SUITE_EXIT=0

The first complete run exposed only a changed legacy IR-verifier message for
string arithmetic. The verifier now preserves the existing string diagnostic
and uses a separate dynamic-value diagnostic for vector values. The complete
suite was rerun on the corrected candidate and exited zero.

Linux x86-64 evidence was collected on s3-vm through the installed cc
toolchain. Probes covered i64 mutation/reserve/get (7), i64 pop (5), i64
clone/slice/get (5), f64 reserve/capacity (2), and tryte push/get (364).
Hosted fixed-seed reference traces and O0/O1 equivalence also passed.

## Contract closure

    M1_40_STATUS=COMPLETE
    M1_41_STATUS=NOT_STARTED
    GENERAL_PARAMETRIC_GENERICS=NO
    NATIVE_VECTOR_DESCRIPTOR_ABI=PASS_LINUX_X86_64_SSH
    DIFFERENTIAL_REFERENCE_TRACE=PASS
    NEXT_MILESTONE=1.41

No GitHub, PR, push, merge, benchmark, Docker, virtualization, or shutdown
action was performed.
