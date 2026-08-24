"""M2.85 bounded control-flow lowering candidate with exact observables."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json

class M285Error(ValueError): pass
@dataclass(frozen=True)
class M285Instruction:
    opcode:str; result:int|None=None; operands:tuple[int,...]=(); targets:tuple[int,...]=(); immediate:int|None=None
@dataclass(frozen=True)
class M285Block:
    id:int; instructions:tuple[M285Instruction,...]
@dataclass(frozen=True)
class M285Program:
    blocks:tuple[M285Block,...]; register_count:int

def _validate(p:M285Program):
    if not p.blocks or p.register_count<0: raise M285Error('invalid shape')
    ids=[b.id for b in p.blocks]
    if ids!=list(range(len(ids))): raise M285Error('non-deterministic block ids')
    defined=set()
    for bi,b in enumerate(p.blocks):
        for i in b.instructions:
            if any(x<0 or x>=p.register_count for x in i.operands): raise M285Error('invalid operand')
            if any(x<0 or x>=len(p.blocks) for x in i.targets): raise M285Error('invalid target')
            if i.opcode not in {'const','add','sub','branch','cond_branch','return','loop_back'}: raise M285Error('unsupported opcode')
            if i.opcode=='return' and bi != len(p.blocks)-1 and i.targets: raise M285Error('return target')
            if i.result is not None:
                if i.result in defined or not 0<=i.result<p.register_count: raise M285Error('invalid result')
                defined.add(i.result)
    return p

def exact_structure(p:M285Program):
    _validate(p)
    return {'format':'s3.m285.control-flow.v1','register_count':p.register_count,'blocks':[{'id':b.id,'instructions':[{'opcode':i.opcode,'result':i.result,'operands':list(i.operands),'targets':list(i.targets),'immediate':i.immediate} for i in b.instructions]} for b in p.blocks]}
def canonical_bytes(p): return (json.dumps(exact_structure(p),sort_keys=True,separators=(',',':'))+'\n').encode()
def canonical_sha256(p): return hashlib.sha256(canonical_bytes(p)).hexdigest()

def if_fixture():
    return M285Program((M285Block(0,(M285Instruction('const',0,immediate=1),M285Instruction('cond_branch',operands=(0,),targets=(1,2)))),M285Block(1,(M285Instruction('const',1,immediate=10),M285Instruction('branch',targets=(3,)))),M285Block(2,(M285Instruction('const',2,immediate=20),M285Instruction('branch',targets=(3,)))),M285Block(3,(M285Instruction('return',operands=(1,)),))),3)
def nested_branch_fixture():
    return M285Program((M285Block(0,(M285Instruction('const',0,immediate=1),M285Instruction('cond_branch',operands=(0,),targets=(1,2)))),M285Block(1,(M285Instruction('cond_branch',operands=(0,),targets=(3,4)),)),M285Block(2,(M285Instruction('branch',targets=(4,)),)),M285Block(3,(M285Instruction('const',1,immediate=3),M285Instruction('branch',targets=(4,)))),M285Block(4,(M285Instruction('return',operands=(0,)),))),2)
def bounded_loop_fixture():
    return M285Program((M285Block(0,(M285Instruction('const',0,immediate=0),M285Instruction('branch',targets=(1,)))),M285Block(1,(M285Instruction('const',1,immediate=1),M285Instruction('loop_back',operands=(1,),targets=(1,2)))),M285Block(2,(M285Instruction('return',operands=(0,)),))),2)

def verifier_interop(p):
    _validate(p)
    if any(i.opcode in {'branch','cond_branch','loop_back'} and not i.targets for b in p.blocks for i in b.instructions): return False
    return True
