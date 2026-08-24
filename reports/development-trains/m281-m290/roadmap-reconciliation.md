# M2.81–M2.90 roadmap reconciliation

## ORIGINAL_PLAN

M2.81 canonical IR model; M2.82 expression lowering; M2.83 control-flow
lowering; M2.84 ownership/reference lowering; M2.85 verifier; M2.86 canonical
serialization; M2.87 composed closure; M2.88 canary; M2.89 checkpoint.

## ACTUAL_M281

Canonical IR data model — complete as bounded historical candidate; exact
structural hardening added in this correction.

## ACTUAL_M282

Expression lowering — complete as bounded historical candidate; exact
structural hardening added in this correction.

## ACTUAL_M283

Call and aggregate-result lowering — HISTORICAL, COMPLETE. This preserves PR
#246 and is not renamed retroactively.

## REVISED_M284_M290

M2.84 control-flow plus remaining aggregate-lowering closure; M2.85
ownership/reference lowering; M2.86 S3 IR verifier; M2.87 canonical IR
serialization; M2.88 composed lowering closure; M2.89 lowering canary; M2.90
IR/lowering checkpoint.

NO_REQUIRED_GATE_DROPPED=YES
