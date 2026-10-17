"""Deterministic, bounded Reliability Lab harness for the S3 compiler."""
from __future__ import annotations
import argparse, hashlib, json, random, sys, time
from dataclasses import dataclass, asdict
from pathlib import Path
from bootstrap.s3.pipeline import compile_source, run_source

GENERATOR_VERSION = "reliability-valid-v1"
MAX_SOURCE_BYTES = 4096
MAX_LITERAL_MAGNITUDE = 100
VALID_TEMPLATES = (
    "fn main() -> tryte:\n    return {a} + {b}\n",
    "fn add(a: tryte, b: tryte) -> tryte:\n    return a + b\n\nfn main() -> tryte:\n    return add({a}, {b})\n",
)
MALFORMED_TEMPLATES = (
    "fn main() -> tryte:\n    return (",
    "fn main( -> tryte:\n    return {a}\n",
    "fn main() -> tryte:\n    return {a} + * {b}\n",
    "fn main() -> tryte:\n    return {a}\nthis is invalid\n",
)

def source_sha(source: str) -> str: return hashlib.sha256(source.encode()).hexdigest()

def generate_valid(seed: int) -> str:
    rng=random.Random(seed); template=rng.choice(VALID_TEMPLATES)
    a=rng.randint(-MAX_LITERAL_MAGNITUDE,MAX_LITERAL_MAGNITUDE); b=rng.randint(-MAX_LITERAL_MAGNITUDE,MAX_LITERAL_MAGNITUDE)
    return template.format(a=a,b=b)[:MAX_SOURCE_BYTES]

def generate_malformed(seed: int) -> str:
    rng=random.Random(seed); return rng.choice(MALFORMED_TEMPLATES).format(a=rng.randint(-9,9),b=rng.randint(-9,9))

def mutate(source: str, seed: int) -> str:
    rng=random.Random(seed); tokens=source.split()
    if not tokens: return source
    operation=rng.choice(("DELETE_TOKEN","DUPLICATE_TOKEN","REPLACE_LITERAL","INSERT_INVALID_TOKEN"))
    index=rng.randrange(len(tokens))
    if operation=="DELETE_TOKEN": del tokens[index]
    elif operation=="DUPLICATE_TOKEN": tokens.insert(index,tokens[index])
    elif operation=="REPLACE_LITERAL": tokens[index]=str(rng.randint(-9,9))
    else: tokens.insert(index,"@@invalid@@")
    return " ".join(tokens)[:MAX_SOURCE_BYTES]

@dataclass(frozen=True)
class CaseResult:
    seed:int; source_sha:str; mode:str; classification:str; expected:object=None; actual:object=None; signature:str=""

def run_case(source: str, seed: int, mode: str, timeout_seconds: float=2.0) -> CaseResult:
    digest=source_sha(source); start=time.monotonic()
    try:
        if mode=="valid":
            expected=run_source(source, optimization="O0")
            actual=run_source(source, optimization="O1")
            cls="PASS" if expected==actual else "MISCOMPILE"
            sig=f"{expected!r}|{actual!r}" if cls!="PASS" else ""
        else:
            compile_source(source, optimization="O0"); expected=None; actual=None; cls="INVALID_ACCEPTED"; sig="accepted-malformed-input"
    except Exception as exc:
        expected=actual=None; cls="VALID_REJECTED" if mode=="valid" else "PASS"; sig=type(exc).__name__+":"+str(exc).splitlines()[0][:120]
    if time.monotonic()-start>timeout_seconds: cls="TIMEOUT"; sig="bounded-run-timeout"
    return CaseResult(seed,digest,mode,cls,expected,actual,sig)

def campaign(campaign_id: str, seed_start: int, valid_cases: int, malformed_cases: int) -> dict:
    results=[run_case(generate_valid(seed_start+i),seed_start+i,"valid") for i in range(valid_cases)]
    results += [run_case(generate_malformed(seed_start+100000+i),seed_start+100000+i,"malformed") for i in range(malformed_cases)]
    counts={k:sum(r.classification==k for r in results) for k in sorted({r.classification for r in results})}
    return {"schema":"s3.reliability.report.v1","campaign_id":campaign_id,"source_sha":"unknown-at-harness-level","seed_start":seed_start,"generator_version":GENERATOR_VERSION,"case_count":len(results),"counts":counts,"results":[asdict(r) for r in results]}

def minimize(source: str, predicate) -> str:
    lines=source.splitlines(True); changed=True
    while changed and len(lines)>1:
        changed=False
        for i in range(len(lines)):
            candidate="".join(lines[:i]+lines[i+1:])
            if candidate and predicate(candidate): lines=lines[:i]+lines[i+1:]; changed=True; break
    return "".join(lines)

def replay(path: Path) -> int:
    metadata=json.loads((path/"metadata.json").read_text(encoding="utf-8")); source=(path/"input.s3").read_text(encoding="utf-8")
    result=run_case(source,int(metadata["seed"]),metadata.get("mode","valid")); print(json.dumps(asdict(result),sort_keys=True)); return 0 if result.classification==metadata["failure_class"] else 1

def main(argv=None):
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    c=sub.add_parser("campaign"); c.add_argument("--id",default="reliability-smoke-20260823"); c.add_argument("--seed",type=int,default=1); c.add_argument("--valid",type=int,default=100); c.add_argument("--malformed",type=int,default=100); c.add_argument("--report",type=Path,required=True)
    g=sub.add_parser("generate"); g.add_argument("--seed",type=int,required=True); g.add_argument("--malformed",action="store_true")
    r=sub.add_parser("replay"); r.add_argument("case",type=Path)
    args=parser.parse_args(argv)
    if args.command=="generate": print(generate_malformed(args.seed) if args.malformed else generate_valid(args.seed)); return 0
    if args.command=="replay": return replay(args.case)
    report=campaign(args.id,args.seed,args.valid,args.malformed); args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"campaign_id":args.id,"case_count":report["case_count"],"counts":report["counts"]},sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
