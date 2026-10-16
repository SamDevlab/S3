# Executable learning path

The short lessons under `ecosystem/learning_path/lessons` are compiled and run
by `ecosystem/learning_path/s3-test.toml`. The path then graduates into the
five independent application projects. Each lesson has an expected integer
result, and the standard S3 test runner executes the source; the expected value
is not a documentation-only assertion.

| Stage | Lesson | What to notice | Expected result |
|---|---|---|---:|
| 1 | `01-first-program.s3` | Module declaration, typed `main`, return | 42 |
| 2 | `02-functions-and-types.s3` | Typed function parameter/result and function call | 126 |
| 3 | `03-control-flow.s3` | Mutable local, loop and accumulation | 15 |
| 4 | `04-records.s3` | Record declaration, construction and field access | 42 |
| 5 | `05-three-way-comparison.s3` | S3's three-way comparison and exhaustive `match` | 7 |
| 6 | `06-modules.s3` + `06-metrics.s3` | Importing a second S3 module | 42 |
| 7 | `data-quality` application | Vectors, fixtures, reusable packages, validation | 10701 |
| 8 | `graph-paths` application | Records, collections, traversal and reachability | 309 |
| 9 | `regression-analysis` application | `s3.v1.science`, numerical check and bounded ternary reuse | 210 |
| 10 | `event-log` application | Strict parsing, malformed input and error status | 30615 |
| 11 | `balanced-state` application | Signed range boundaries and reversible encoding | 53007 |
| 12 | VS Code + project workflow | Diagnostics, navigation, formatting, build and explicit run | See each project manifest |

Run lessons with:

```powershell
python -m bootstrap.s3.cli test ecosystem/learning_path/s3-test.toml
```

For applications, run `python -m ecosystem.application_lab run`. Common early
mistakes include omitting `module main`, using a type that does not match a
function's declared result, assuming ordinary two-way Boolean comparison where
the lesson uses `<=>`, and reading summary extrema without checking status.
The lessons deliberately avoid claiming FFI or native support; those tracks
remain unsupported until separately qualified.
