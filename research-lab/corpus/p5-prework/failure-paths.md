# P5 prework failure-path corpus

The source language and current Assembly pipeline are not equivalent for every
address operation, so failure-path validation uses the existing IR-level
contracts in `tests/test_initialization_analysis.py` and native diagnostic
tests. The cases are definite initialization, definite uninitialization,
branch joins, maybe-initialized runtime checks, immutable writes and loop fixed
points.
