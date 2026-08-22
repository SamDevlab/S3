# M2.40 S3 1.0 Release Candidate Gate

The single authorized full-lineage T4 completed exactly once on the candidate
documentation head `a779776c55a38e2b31a9448f97ee7885729a75be`. The tested source
remained frozen at `e202bc9c13afc88169365376b041b4fa12dd8bf9`; only reports and
certification evidence were added after the source gates.

T4 used the Windows `s3test.v1` full profile with `390` selected modules:
`390` passed, `0` failed, `0` timed out, and exit `0`. The pytest output
contains `82` derived skipped cases. No timeout record exists. The raw
transcript and status record are preserved under
`reports/certification/m240-rc-t4-20260822/`.

`FULL_LINEAGE_T4=PASS` and `S3_1_0_RC_CANDIDATE=YES`. The result is a release
candidate readiness decision only: no merge, tag, release, shutdown, or reboot
was performed or authorized by this campaign.
