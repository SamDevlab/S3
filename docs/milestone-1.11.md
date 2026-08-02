# Milestone 1.11 - Third-Stage Self-Hosting

Status: Implementation complete locally in Draft PR #127; user validation pending.

Milestone 1.11 selects small third-stage self-hosting components that benefit
from aggregate returns and explicit structured result APIs while keeping Python
as the reference compiler and default path.

## Selected Components

The selected third-stage components are:

- result-width classifier: maps fixed-layout width facts to a nominal result;
- assembly header classifier: recognizes supported Assembly artifact versions
  and returns explicit success/error variants;
- call-result cell planner: models ordered result cells for a call-like shape.

Each component is intentionally pure, deterministic, file-system-free, and
small enough to compare against a Python reference harness.

## Rejected Candidates

The parser, lexer, optimizer, backend, linker, complete CLI, and filesystem
tools remain rejected for this stage. They require richer text handling, dynamic
collections, broad diagnostics, host integration, or platform behavior.

## Adoption Status

All third-stage components remain differential references. None is adopted as
the default compiler path. Python remains the reference implementation.

## Validation Status

Coverage for the selected component shapes is authored but not executed by the
agent after the no-agent-testing policy change. User validation is required
before changing the Draft PR status.
