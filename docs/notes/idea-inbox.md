# S3 Idea Inbox

This file is a non-roadmap inbox for speculative language and compiler ideas.

Items here are **not commitments**, **not scheduled milestones**, and **not evidence that a feature is viable**. They exist so an explored idea and its reasoning are not lost.

## 2026-09-19 — Implicit function signatures and automatic numeric-width inference

**Status:** DEFERRED / LIKELY NOT VIABLE IN THE AGGRESSIVE FORM  
**Roadmap status:** NOT PLANNED  
**Current self-hosting impact:** NONE

### Explored syntax

Current explicit form:

```s3
fn soma(a: i64, b: i64) -> i64:
    return a + b
```

Explored concise form:

```s3
fn soma(a, b):
    return a + b
```

The idea has two distinct parts and they should not be conflated:

1. **Signature type inference**
   - infer parameter and return semantic types from operations, call sites, constraints, or generic type variables;
   - keep explicit types available where contracts require them.

2. **Automatic numeric representation selection**
   - treat an integer semantically as an integer first;
   - use compile-time range analysis to choose an adequate physical width such as i8/i16/i32/i64/i128;
   - for loops/accumulators, analyze the possible result range before code generation and choose a sufficient width from the beginning of execution.

### Example motivation

A loop accumulator may begin with a very small value but grow beyond a narrow integer range. The explored idea was for the compiler to determine the required width automatically rather than requiring the programmer to select i32 or i64 manually.

The preferred interpretation was **static selection before execution**, not changing a variable from i32 to i64 dynamically while a loop is running.

Dynamic widening would complicate:

- stack layout;
- registers;
- SSA values;
- ABI stability;
- optimization;
- arrays and structures;
- native code generation;
- FFI boundaries.

### Why the aggressive version is currently considered impractical

- parameter types may not be inferable from a function body alone;
- unconstrained functions such as `fn identity(x): return x` naturally introduce generic type variables;
- operator overloading can leave multiple valid type solutions;
- unknown runtime inputs prevent many useful range proofs;
- loops and control flow require increasingly sophisticated range analysis;
- recursion and cross-function calls require interprocedural constraint solving;
- ABI, FFI, binary formats, networking and exported interfaces require stable concrete layouts;
- automatic numeric-width inference would add a substantial type/range-analysis subsystem;
- runtime width promotion would be particularly expensive and complex.

### Possible limited ideas worth reconsidering later

After the current self-hosting/frontend work is mature, separately evaluate:

- optional return-type inference;
- limited local parameter inference;
- generic type variables for structurally obvious cases;
- compile-time range optimization **after semantic types are already known**;
- explicit physical integer widths at ABI/FFI/public boundaries.

### Current decision

Do **not** alter the active self-hosting roadmap for this idea.

Continue the current native frontend/self-hosting campaign with explicit types as the stable language target.

If this idea is revisited, treat signature inference and numeric-width/range optimization as separate research milestones with explicit feasibility tests.
