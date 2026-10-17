import json
from pathlib import Path
from tools.reliability_lab import *

def test_seeded_generation_and_mutation_are_replayable():
    assert generate_valid(7)==generate_valid(7)
    assert generate_valid(7)!=generate_valid(8)
    assert mutate(generate_valid(7),3)==mutate(generate_valid(7),3)

def test_runner_classifies_valid_and_malformed():
    assert run_case(generate_valid(1),1,"valid").classification=="PASS"
    assert run_case(generate_malformed(1),1,"malformed").classification=="PASS"
    assert "INVALID_ACCEPTED" not in {run_case(generate_malformed(i), i, "malformed").classification for i in range(20)}

def test_minimizer_preserves_synthetic_failure():
    source="a\nb\nkeep\nc\n"
    minimized=minimize(source,lambda s:"keep" in s)
    assert minimized=="keep\n"

def test_report_is_machine_readable(tmp_path:Path):
    report=campaign("test",1,3,3)
    path=tmp_path/"report.json"; path.write_text(json.dumps(report))
    loaded=json.loads(path.read_text()); assert loaded["case_count"]==6; assert loaded["schema"].endswith("v1")

def test_source_sha_is_stable():
    source=generate_valid(4); assert source_sha(source)==source_sha(source)

def test_replay_and_timeout_classification(tmp_path:Path):
    source=generate_valid(5); case=tmp_path/"case"; case.mkdir()
    (case/"input.s3").write_text(source)
    (case/"metadata.json").write_text(json.dumps({"seed":5,"mode":"valid","failure_class":"PASS"}))
    assert replay(case)==0
    assert run_case(source,5,"valid",timeout_seconds=0).classification=="TIMEOUT"
