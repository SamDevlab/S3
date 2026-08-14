# S3-EXP-0030 - Path-complete memory-state necessity attribution

STATUS=COMPLETE_NO_VALID_TARGET_YET

MODEL=CFG reachability + use/def + worklist fixed-point definite register/memory state + conservative call/reference/slice/failure handling

INPUTS=exact production HEAD 631b51e70562a33183ac14d0be5bbe2ddd140779; 12 representative workloads; O0/O1; Windows emulator and Linux native profile

STATIC_PROOF=1587 assembly-boundary sites classified as NECESSARY, CONDITIONALLY_NECESSARY, PROVABLY_ACCIDENTAL, or UNKNOWN. Static coverage is 79.8361688720857%.

DYNAMIC_WEIGHTING=4350 observed events; 1859 accidental, 1538 conditional, 901 necessary, 52 unknown. Dynamic pair observation coverage is 22/24 because TADDR is unsupported by the existing emulator for both slice_reference pairs.

STRONGEST_SUBCLASS=definite non-address-taken REGISTER_INIT_CHECK without call/reference/slice visibility; 1660 dynamic events, 416 static sites, 11 workloads.

FALSIFIER=an invalid public Assembly input that needs uninitialized-register diagnostics, a call/reference/slice observer, or a failure-path distinction before the alleged replacement.

COVERAGE=loops reached a fixed point; calls and aliases downgrade affected rows; failure and early-return observers remain in the site records; TADDR remains an explicit dynamic gap.

COUNTEREXAMPLES=public runtime proof transport is absent; native reduction was not measured; the emulator boundary cannot be treated as a native materialization metric.

RESULT=NO_VALID_TARGET_YET

NEXT=only revisit after a proof-bearing Assembly contract with exact checked fallback and a measured emulator cost benefit exists.
