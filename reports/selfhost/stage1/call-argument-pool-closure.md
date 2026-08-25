# Stage1 Call Argument Pool Closure

Checkpoint A for PR #268 closes the measured call-argument capacity blocker.

The exact native audit measured 736 call arguments across 656 calls, with a
maximum arity of 4 and a first unstorable index of 729 in the previous
bounded representation. The selected representation is three bounded banks:
`[365, 365, 16]`, for a total capacity of 746 and ten explicitly documented
headroom slots. Call metadata preserves start bank, start slot, and count;
the verifier checks bank/slot ranges and the absolute `start + count <= 746`
bound.

The post-fix instrumented native run recorded:

```text
S3_STAGE1_CALL_ARGS 736 4 1 617 15 3 20 736 729 -1
```

Therefore `IR_CALL_ARGUMENT_POOL_CAPACITY=PASS` and no argument was dropped.
The audit instrumentation was then removed from the clean source. The clean
canonical self-source run still exits 2 with `S3_STAGE1_EMITTER_BLOCKED` and
zero assembly bytes. This is a separate, honest blocker: the current emitter
implements only the literal-return multi-function subset and does not yet
consume the preserved parameter, local, expression, call, and control-flow
data needed for general emission.

Consequently `SELF_EMIT=BLOCKED`, `STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED`, and
Stage3 remains unstarted. No fake Stage2 artifact was produced.
