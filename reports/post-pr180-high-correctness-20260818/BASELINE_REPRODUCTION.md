# Post-PR180 Baseline Reproduction

Base: `76030c5d5428e47f6839c219c4930db4cb1862d8`

Both HIGH findings reproduced before production changes.

## PR180-PKG-001

The controlled diamond graph admitted conflicting reachable references to
`core`. Forward manifest insertion produced `('X', 'aaaaaaa')`; reversed
insertion produced `('Y', 'bbbbbbb')`. The baseline selected the first
reference instead of rejecting the inconsistent identity.

Result: `PKG_BASE_REPRODUCED=YES`

## PR180-THREAD-001

A controlled admission window allowed two callers to pass the capacity check
for `ThreadRuntime(max_active=1)`. The baseline admitted two workers.

Result: `THREAD_BASE_REPRODUCED=YES`

No full suite, benchmark, CI rerun, push, PR, merge, or shutdown was used.
