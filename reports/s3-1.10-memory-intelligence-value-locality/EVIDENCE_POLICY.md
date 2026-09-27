# S3 1.10 Evidence Retention Policy

- Pin every experiment to repository, commit, tree, tool/input hashes, target,
  workload, and protocol. A branch name alone is not provenance.
- Correctness gates precede timing. If correctness fails, preserve the failure
  and do not characterize the candidate as a performance result.
- Keep raw output local by default. Commit compact final reports, protocol,
  hashes, canonical summaries, and raw data only when it carries independent
  scientific value or is needed to reproduce a disputed result.
- Preserve negative results when they close a distinct hypothesis. Do not
  preserve every rerun that only regenerates the same schema or summary.
- Do not copy the 1.9 Observatory JSON into the 1.10 tree. Reference its
  canonical paths and hashes in `BASELINE.md`; those immutable files remain in
  Git history.
- For any large new artifact, record why it must be versioned, its size and
  SHA-256, generation command, pinned inputs, and a compact summary. Prefer a
  single final report plus a manifest over a sequence of near-identical
  versions.
- Compact JSON/JSONL or compression is acceptable only if protocol, inputs,
  hashes, outcomes, and negative findings remain recoverable.
- Before publication, report total newly added evidence bytes, largest files,
  and count of committed intermediate artifacts. Do not remove user files or
  rewrite historical evidence to reduce repository size.
