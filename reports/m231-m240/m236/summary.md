# M2.36 Developer Tooling Stabilization

`M2_36_TOOLING_STABILITY=PARTIAL`

The LSP now exposes deterministic workspace symbols, resolves uniquely
declared symbols across open documents, keeps duplicate declarations local,
accepts cancellation notifications, rejects stale versions, and rejects
duplicate/non-ASCII framing headers. Existing formatter, docs, CLI, workspace,
test-framework, and build-profile contracts remain covered by their focused
tests. Full multi-file semantic project resolution remains experimental.
