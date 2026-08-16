# Milestone 1.50 — Portable Component Gate

M1.50 retains exactly one bounded component: the existing Assembly renderer
subset. Its portable gate is `M149-G11`: the component must compile as
`wasm32-wasip1-s3`, execute under the M1.49 certification runtime without
undeclared imports, and produce byte-identical logical output to the existing
Python renderer oracle for the locked fixture corpus.

The component memory budget is **8 MiB maximum linear memory**. This is larger
than the current bounded fixture corpus and leaves room for renderer buffers,
while remaining materially below the global runtime ceiling. Exceeding it is
a deterministic resource failure. This does not claim complete self-hosting or
promote the candidate to the default compiler.
