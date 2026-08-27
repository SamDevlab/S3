# Stage05 authoritative postfix parser oracle

Purpose: give the paired Stage05 repair an exact repository-backed parser contract while the current right-parenthesis diagnostic build is in flight.

This document does not change the active atomic task and does not authorize another build, foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3, or T4.

## Repository-backed positive behavior

`tests/test_parser_postfix.py` establishes these as valid postfix forms under V0.6:

```text
f()
f(a, b)
a[0]
a.b
(a).b
f().value
pkg.function()
factory()[0]
functions[0]()
consume(pkg.make().value)
a[0].b(c)[1]
(factory())[0]
```

Important implications for the current `helper(1)` blocker:

1. call syntax is a postfix suffix on an already-parsed primary/callee;
2. a complete `)` after the argument list is a valid close token, not an invalid expression token;
3. grouping and call parentheses are distinct but composable parser roles;
4. call arguments preserve source order;
5. a call result may continue through later postfix/infix syntax.

## Repository-backed negative boundary

The same test suite makes these distinctions explicit:

```text
f(1       -> parse error: expected ')' after arguments
f(a,)     -> parse error: expected argument after ','
```

Therefore a complete `f(1)` / `helper(1)` must not use either fail-closed path.

This is particularly useful for the current right-parenthesis probe:

- if the candidate sees `)` and sets `parse_ok=0` because the argument parser treats it as an unexpected token, the candidate disagrees with the authoritative postfix grammar;
- if the candidate successfully closes the call and then falls through into a generic `)` rejection, that is also a grammar mismatch;
- if the candidate decrements shared parenthesis state twice, grouped/postfix compositions such as `(factory())[0]` and `(a).b` are at regression risk.

## Parser implementation model

The repository parser follows this shape:

```text
_parse_postfix
  -> parse primary atom
  -> if LEFT_PAREN follows, enter _finish_call
     -> parse zero or more argument expressions
     -> COMMA separates arguments
     -> consume RIGHT_PAREN exactly once
     -> return CallExpression
  -> continue other postfix suffixes
```

The current Stage05 candidate does not need to copy the hosted parser implementation, but its observable grammar must match this behavior.

## Use after the current diagnostic returns

Do not patch from this document alone. First use the raw before/after close-state values from `STAGE05_RIGHT_PAREN_CLOSE_PROBE.md` to prove where `parse_ok` changes.

Then choose one repair only:

- `ARGUMENT_STOP_AT_RIGHT_PAREN` if invalidity exists before call close;
- `CALL_CLOSE_SINGLE_CONSUMPTION_OR_DEPTH` if invalidity appears inside close;
- `POST_CALL_FALLTHROUGH_OR_FRAME_RESTORE` if close state itself is valid but a later parser step invalidates the expression.

After the eventual fix, the clean binary should preserve both:

```text
grouping control: valid
helper(1): valid call
```

and strict Stage05 semantics must still prove `I/O/R/C/A` with `Z 7` for the valid call fixture.
