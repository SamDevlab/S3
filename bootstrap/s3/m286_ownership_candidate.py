"""M2.86 bounded ownership/reference lowering with S3 lane observation."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
from pathlib import Path
from bootstrap.s3.pipeline import run_source
from bootstrap.s3.lexer import SyntaxMode

class M286Error(ValueError):
    def __init__(self,code): self.code=code; super().__init__(code)
@dataclass(frozen=True)
class Place: id:int; type_id:int; mutable:bool; initialized:bool=True
@dataclass(frozen=True)
class Reference: id:int; place_id:int; kind:str
@dataclass(frozen=True)
class M286Op: opcode:str; place_id:int=-1; reference_id:int=-1; source_register:int=-1; destination_register:int=-1; type_id:int=1; transition:str='none'
@dataclass(frozen=True)
class OwnershipProgram: places:tuple[Place,...]; references:tuple[Reference,...]; operations:tuple[M286Op,...]

OPS={'load_place','store_place','borrow_shared','borrow_mut','read_ref','write_ref','move_value'}; KINDS={'shared','mutable'}
def validate(p):
    if len(p.places)>8 or len(p.references)>8 or len(p.operations)>32: raise M286Error('BOUNDS')
    if len({x.id for x in p.places})!=len(p.places) or len({x.id for x in p.references})!=len(p.references): raise M286Error('DUPLICATE_ID')
    if tuple(x.id for x in p.places)!=tuple(range(len(p.places))) or tuple(x.id for x in p.references)!=tuple(range(len(p.references))): raise M286Error('NON_CANONICAL_ID_LAYOUT')
    places={x.id:x for x in p.places}; refs={x.id:x for x in p.references}; initialized={x.id:x.initialized for x in p.places}; active_shared=set(); active_mut=set(); moved=set()
    for r in p.references:
        if r.kind not in KINDS: raise M286Error('INVALID_REFERENCE_KIND')
        if r.place_id not in places: raise M286Error('INVALID_REFERENCE')
    for op in p.operations:
        if op.opcode not in OPS: raise M286Error('UNKNOWN_OPERATION')
        if op.opcode in {'load_place','store_place','move_value'} and op.place_id not in places: raise M286Error('INVALID_PLACE')
        if op.opcode in {'read_ref','write_ref'} and op.reference_id not in refs: raise M286Error('INVALID_REFERENCE')
        if op.opcode=='borrow_shared':
            if op.place_id not in places or not initialized[op.place_id]: raise M286Error('INVALID_PLACE')
            if op.place_id in active_mut: raise M286Error('BORROW_CONFLICT')
            active_shared.add(op.place_id)
        if op.opcode=='borrow_mut':
            if op.place_id not in places or not places[op.place_id].mutable: raise M286Error('IMMUTABLE_BORROW')
            if op.place_id in active_mut or op.place_id in active_shared: raise M286Error('BORROW_CONFLICT')
            active_mut.add(op.place_id)
        if op.opcode=='write_ref':
            r=refs.get(op.reference_id)
            if not r: raise M286Error('INVALID_REFERENCE')
            if r.kind!='mutable': raise M286Error('SHARED_WRITE')
        if op.opcode=='read_ref' and op.reference_id not in refs: raise M286Error('INVALID_REFERENCE')
        if op.opcode=='load_place':
            if op.place_id in moved: raise M286Error('USE_AFTER_MOVE')
            if not initialized[op.place_id]: raise M286Error('READ_UNINITIALIZED')
        if op.opcode=='store_place': initialized[op.place_id]=True
        if op.opcode=='move_value':
            if op.place_id in moved: raise M286Error('DOUBLE_MOVE')
            if not places[op.place_id].initialized: raise M286Error('READ_UNINITIALIZED')
            moved.add(op.place_id)
    return p

def structure(p):
    validate(p); return {'format':'s3.m286.ownership-reference.v1','places':[x.__dict__ for x in p.places],'references':[x.__dict__ for x in p.references],'operations':[x.__dict__ for x in p.operations]}
def canonical_bytes(p): return (json.dumps(structure(p),sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(p): return hashlib.sha256(canonical_bytes(p)).hexdigest()

def mutable_local(): return OwnershipProgram((Place(0,1,True,False),),(),(M286Op('store_place',0,transition='initialize'),M286Op('load_place',0),))
def shared_read(): return OwnershipProgram((Place(0,1,True),),(Reference(0,0,'shared'),),(M286Op('borrow_shared',0,reference_id=0),M286Op('read_ref',reference_id=0),))
def mutable_write(): return OwnershipProgram((Place(0,1,True),),(Reference(0,0,'mutable'),),(M286Op('borrow_mut',0,reference_id=0),M286Op('write_ref',reference_id=0),M286Op('read_ref',reference_id=0),))
def invalid_shared_write(): return OwnershipProgram((Place(0,1,True),),(Reference(0,0,'shared'),),(M286Op('write_ref',reference_id=0),))
def moved_use(): return OwnershipProgram((Place(0,1,True),),(),(M286Op('move_value',0),M286Op('load_place',0)))
_CANDIDATE_SOURCE=(Path(__file__).resolve().parents[2]/'selfhost/lowering/ownership_reference_lowering_candidate.s3').read_text(encoding='utf-8')
def _encode(p):
    opcodes={'load_place':1,'store_place':2,'borrow_shared':3,'borrow_mut':4,'read_ref':5,'write_ref':6,'move_value':7}
    kinds={'shared':1,'mutable':2}; trans={'none':0,'initialize':1}
    pad=lambda xs,n: list(xs)+[0]*(n-len(xs))
    ref_by_id={x.id:x.place_id for x in p.references}
    return ([x.initialized for x in p.places], [x.mutable for x in p.places], [x.place_id for x in p.references], [kinds[x.kind] for x in p.references], [opcodes[x.opcode] for x in p.operations], [x.place_id if x.place_id >= 0 else ref_by_id.get(x.reference_id, -1) for x in p.operations], [x.reference_id for x in p.operations])
def _candidate_source(p, lane):
    init,mutable,ref_places,ref_kinds,opcodes,op_places,op_refs=_encode(p)
    pad=lambda xs,n: list(xs)+[0]*(n-len(xs))
    arr=lambda xs,n: '['+', '.join(str(int(x)) for x in pad(xs,n))+']'
    return _CANDIDATE_SOURCE+f'''\nfn main() -> tryte:\n    place_init: tryte[8] = {arr(init,8)}\n    place_mutable: tryte[8] = {arr(mutable,8)}\n    ref_places: tryte[8] = {arr(ref_places,8)}\n    ref_kinds: tryte[8] = {arr(ref_kinds,8)}\n    opcodes: tryte[32] = {arr(opcodes,32)}\n    op_places: tryte[32] = {arr(op_places,32)}\n    op_refs: tryte[32] = {arr(op_refs,32)}\n    return ownership_lane({lane}, place_init, place_mutable, ref_places, ref_kinds, opcodes, op_places, op_refs, {len(p.places)}, {len(p.references)}, {len(p.operations)})\n'''
def candidate_structure(p):
    validate(p); ops=[]
    src=lambda lane: _candidate_source(p,lane)
    status=run_source(src(0),optimization='O0',mode=SyntaxMode.V0_6)
    if status != 0: raise M286Error({201:'BOUNDS',203:'INVALID_REFERENCE',204:'INVALID_REFERENCE_KIND',206:'READ_UNINITIALIZED',207:'IMMUTABLE_BORROW',211:'DOUBLE_MOVE',213:'UNKNOWN_OPERATION'}.get(status,'S3_REJECTED'))
    for i,op in enumerate(p.operations):
        vals=dict(op.__dict__); ops.append(M286Op(**vals))
    return structure(OwnershipProgram(p.places,p.references,tuple(ops)))
def candidate_diagnostic(p):
    return run_source(_candidate_source(p,0),optimization='O0',mode=SyntaxMode.V0_6)
def candidate_matches(p): return structure(p)==candidate_structure(p)
def candidate_canonical_bytes(p): return (json.dumps(candidate_structure(p),sort_keys=True,separators=(',',':'))+'\n').encode()
def candidate_digest(p): return hashlib.sha256(candidate_canonical_bytes(p)).hexdigest()
