# M2.44 HTTP/2 Dynamic HPACK

## WHY_NOW

The HTTP/2 boundary previously decoded only static fields and literal values
without indexing. M2.44 closes the bounded protocol gap needed for dynamic
header compression while keeping production networking deferred.

## ARCHITECTURAL_DECISION

`HPACKDecoder` owns bounded dynamic-table state. Each header block is decoded
against a private working copy and state is published only after the complete
block succeeds. The configured maximum table size is an upper bound for peer
table-size updates, and entries larger than the active limit are discarded as
required by RFC 7541. Header count, retained decoded bytes, integer expansion,
string size, and Huffman output remain bounded.

## IMPLEMENTATION_SUMMARY

- Added stateful indexed and literal-with-incremental-indexing decoding.
- Added dynamic name lookup, table-size updates, eviction, and oversize-entry
  rejection.
- Added literal-without-indexing and never-indexed field handling for dynamic
  names.
- Added a local RFC 7541 Huffman decoder with malformed-code, EOS, padding,
  and output-bound rejection.
- Added focused M2.44 coverage and impact/shard metadata.
- Kept the release surface explicitly deferred for production HTTP/2
  networking despite the bounded decoder capability.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- `python -m json.tool tests/test-impact.json`: PASS
- Focused HTTP/2, release-surface, contract, and adversarial tests: 21 passed.
- T2 M2.44: 4 selected, 4 passed, exit 0.
- T3 M2.44 shard: 1 selected, 1 passed, exit 0.
- `git diff --check`: PASS.

## BENCHMARK_RELEVANCE

None. This milestone adds bounded protocol decoding and correctness checks;
no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

This milestone provides the bounded HPACK decoder only. Socket transport,
HTTP/2 stream scheduling, flow control, continuation-frame assembly, and
production networking remain deferred capabilities.
