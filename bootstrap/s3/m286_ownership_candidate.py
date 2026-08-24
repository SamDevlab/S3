"""M2.86 bounded ownership/reference lowering with S3 lane observation."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
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
    places={x.id:x for x in p.places}; refs={x.id:x for x in p.references}; active_shared=set(); active_mut=set(); moved=set()
    for op in p.operations:
        if op.opcode not in OPS: raise M286Error('UNKNOWN_OPERATION')
        if op.opcode in {'load_place','store_place','move_value'} and op.place_id not in places: raise M286Error('INVALID_PLACE')
        if op.opcode in {'read_ref','write_ref'} and op.reference_id not in refs: raise M286Error('INVALID_REFERENCE')
        if op.opcode=='borrow_shared':
            if op.place_id not in places or not places[op.place_id].initialized: raise M286Error('INVALID_PLACE')
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
        if op.opcode=='load_place' and op.place_id in moved: raise M286Error('USE_AFTER_MOVE')
        if op.opcode=='move_value': moved.add(op.place_id)
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
def _candidate_source(p):
    s=[]
    for i,op in enumerate(p.operations):
        for field,value in op.__dict__.items():
            v=({'load_place':1,'store_place':2,'borrow_shared':3,'borrow_mut':4,'read_ref':5,'write_ref':6,'move_value':7}[op.opcode] if field=='opcode' else ({'none':0,'initialize':1}.get(value,value) if field=='transition' else value))
            s.append(f'fn lane_{i}_{field}() -> tryte:\n    return {v if isinstance(v,int) else 0}')
    return '\n'.join(s)
def candidate_structure(p):
    validate(p); src=_candidate_source(p); ops=[]
    for i,op in enumerate(p.operations):
        vals={}
        for field in op.__dict__:
            vals[field]=run_source(src+f'\nfn main() -> tryte:\n    return lane_{i}_{field}()\n',optimization='O0',mode=SyntaxMode.V0_6)
        names={1:'load_place',2:'store_place',3:'borrow_shared',4:'borrow_mut',5:'read_ref',6:'write_ref',7:'move_value'}; vals['opcode']=names[vals['opcode']]; vals['transition']='initialize' if vals['transition']==1 else 'none'; ops.append(M286Op(**vals))
    return structure(OwnershipProgram(p.places,p.references,tuple(ops)))
def candidate_matches(p): return structure(p)==candidate_structure(p)
def candidate_canonical_bytes(p): return (json.dumps(candidate_structure(p),sort_keys=True,separators=(',',':'))+'\n').encode()
def candidate_digest(p): return hashlib.sha256(candidate_canonical_bytes(p)).hexdigest()
