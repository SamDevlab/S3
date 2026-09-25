# Full-suite transcript reconciliation

The first, invalid environment attempt is preserved byte-for-byte as the
`full-suite-linux-x86_64.txt` entry in
`full-suite-linux-x86_64-invalid.zip`. The uncompressed transcript SHA-256 is
`2b7aca630e8f9c01987ebe696b8956819037ed1da01769a884d20d8d94ee489c`; the
archive SHA-256 is
`e83571a3ac560aa1dd68d37c67dcc45e20ff39ade0dc136e852201aac530cefc`. It ran
from an extracted source archive without `.git`;
renderer golden checks that read `git show HEAD:<path>` therefore could not
use the repository object database. One unrelated Zig native test also failed
to create compiler output because the VM root filesystem had no free space.
That attempt reported 4,257 passed, 51 failed, 1 skipped, 113 errors, and 91
subtests; it is not the final correctness result.

Its header says `FULL_SUITE_TREE=7f8c1ab55b3a06eab6e0d78a7e792014e8b15f3e`.
That manually recorded tree value was wrong. The exact commit
`7ae48ce88b7ca8648feea7a79674f8cc46edb9a8` has tree
`e548d623311fedaa86c8f3261c3e1f7305b5f504`, as verified in the repository
and the retry transcript. The historical transcript and its original SHA-256
are retained without edits inside the archive.

The valid retry, `full-suite-linux-x86_64-gitbundle.txt`, used a Git bundle
clone at that exact commit/tree, confirmed clean Git status and the golden
blob, and placed temporary Zig caches on `/dev/shm`. It completed with 4,379
passed, 1 skipped, 572 subtests passed, zero failed, exit 0, in 3,918.79
seconds. Its SHA-256 is
`617746ee76807f146b84d10a742b96ec19c4ea47a5a92b022a2d7f51df1e54b6`.
