# Milestone 1.35 - Dynamic Values

This milestone establishes an explicit tagged scalar value boundary for
runtime-facing APIs. The closed set is `trit`, `tryte`, `i64`, and `f64`.

Dynamic values retain their tag, reject implicit numeric conversion, and reuse
the existing checked numeric domains. Heap allocation, references, pointers,
dynamic strings, and unbounded containers remain outside this milestone.
