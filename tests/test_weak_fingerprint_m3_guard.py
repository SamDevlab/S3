from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_legacy_mod181_is_not_used_as_exact_match_gate():
    for name in ('canonical_ir_candidate.py','expression_lowering_candidate.py','call_aggregate_lowering_candidate.py'):
        text=(ROOT/'bootstrap'/'s3'/name).read_text(encoding='utf-8')
        assert 'match(self) -> bool' in text
        match=text.split('def match(self) -> bool:',1)[1].split('\n',4)[0:4]
        assert 'identity' not in '\n'.join(match)

def test_m278_is_bounded_evidence_only():
    assert 'M278_IDENTITY_MOD181=BOUNDED_EXPERIMENTAL_EVIDENCE_ONLY' in (ROOT/'reports'/'development-trains'/'v3-evidence-audit-20260823'/'notes.md').read_text()
