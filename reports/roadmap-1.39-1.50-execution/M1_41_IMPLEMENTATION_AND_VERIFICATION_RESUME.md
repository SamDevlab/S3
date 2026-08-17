# M1.41 Implementation and Verification Resume

## Checkpoint

    MILESTONE=1.41
    TITLE=Deterministic Maps and Sets
    BASE_IMPLEMENTATION=c9fc6f4
    IMPLEMENTATION_HEAD=88d32a4
    REMOTE_WRITES=NO

M1.41 adds the closed source types `i64_map` and `i64_set`. They reuse the
M1.39 allocator, move, borrow, limit, and deterministic trap contract. Maps
store ordered i64 key/value pairs; sets store ordered i64 values. The native
representation is private and uses 16-byte map entries or 8-byte set entries.

## Evidence

    FOCUSED_M141=PASS (7 tests)
    SHARED_REGRESSION=PASS (40 tests)
    COMPILEALL=PASS
    DIFF_CHECK=PASS
    FULL_SUITE_TERMINAL=YES
    FULL_SUITE_EXIT=0
    NATIVE_LINUX_X86_64=PASS

Linux probes on `s3-vm` covered map lengths after one and two inserts,
insertion-order `key_at`, value lookup, replacement, middle removal,
explicit reserve, clone, set duplicate suppression, set middle removal, and
set clone. An initial native failure was traced to both lookup helpers reading
from the descriptor rather than its payload base. The runtime was corrected in
the implementation commit and all native probes then passed.

## Contract closure

    M1_41_STATUS=COMPLETE
    M1_42_STATUS=NOT_STARTED
    GENERAL_PARAMETRIC_GENERICS=NO
    NATIVE_MAP_SET_GATE=PASS_LINUX_X86_64_SSH
    ORDERED_LOOKUP=PASS
    FULL_SUITE_TERMINAL=YES
    FULL_SUITE_EXIT=0
    NEXT_MILESTONE=1.42

No GitHub, PR, push, merge, benchmark, Docker, virtualization, or shutdown
action was performed.
