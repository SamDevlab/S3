# S3-EXP-0031 - P8 final proof-guided native initialization-check elision

STATUS=SUPPORTED_AND_MERGED_PR_178

BASE=631b51e70562a33183ac14d0be5bbe2ddd140779
CANDIDATE=87eb49cd19a78570f07d66ce7982650c8b422210
PR=178
MERGE=5dd6844607ba3a2d5830ed836fb9026eed86d0fb

QUESTION=Can the native consumer remove only proven redundant register-init checks without transporting a forgeable public proof?

MODEL=CONSERVATIVE_NATIVE_RECOMPUTATION

PROOF=The emitter computes a fail-closed function-level fixed point from existing Assembly CFG and use/def facts. Exact safe sites are keyed by block, instruction, and register. Unknown, invalidated, call-visible, reference-visible, slice-visible, address-taken, loop-unsafe, join-unsafe, and public/untrusted cases retain the checked path.

POPULATION=P8.3 safe static sites 416; P8.3 safe dynamic events 1660; native-consumable sites 402; native-consumable dynamic events 1558; production fact match 416/416.

NATIVE_EFFECT=Across 12 workloads at O0/O1, 24 pairs preserved semantics. Register-init checks 550->148, static instructions 20903->20099, branches 4746->4344, text 107709->102646, loads/stores 10175->10175.

FULL_SUITE=Exact candidate HEAD 87eb49cd19a78570f07d66ce7982650c8b422210; exit 0; 2026-08-14T01:42:19Z to 2026-08-14T02:50:17Z.

NEGATIVE_RESULT=Generic proof transport and public Assembly metadata are unnecessary and unsafe for this bounded consumer. Runtime and compile-time measurements were not collected under a comparable protocol.

CONCLUSION=P8_PROOF_GUIDED_NATIVE_INIT_CHECK_ELISION is implemented and merged. P9 is not started and reboot is not authorized by this research checkpoint.
