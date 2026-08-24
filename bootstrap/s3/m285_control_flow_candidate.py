"""M2.85 bounded control-flow lowering candidate with exact observables."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from bootstrap.s3.pipeline import run_source
from bootstrap.s3.lexer import SyntaxMode

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
            if i.opcode not in {'const','add','sub','call','branch','cond_branch','return','loop_back'}: raise M285Error('unsupported opcode')
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

def _candidate_source(p):
    s=['fn lowered_block_count() -> tryte:\n    return '+str(len(p.blocks))]
    s.append('fn lowered_register_count() -> tryte:\n    return '+str(p.register_count))
    for bi,b in enumerate(p.blocks):
        s.append(f'fn lowered_block_id_{bi}() -> tryte:\n    return {b.id}')
        s.append(f'fn lowered_instruction_count_{bi}() -> tryte:\n    return {len(b.instructions)}')
        for ii,i in enumerate(b.instructions):
            fields={'opcode':{'const':1,'add':2,'sub':3,'branch':4,'cond_branch':5,'return':6,'loop_back':7}[i.opcode],'result':-1 if i.result is None else i.result,'operand_count':len(i.operands),'target_count':len(i.targets),'immediate_present':0 if i.immediate is None else 1,'immediate':0 if i.immediate is None else i.immediate}
            for field,value in fields.items(): s.append(f'fn lowered_{field}_{bi}_{ii}() -> tryte:\n    return {value}')
            for oi,value in enumerate(i.operands): s.append(f'fn lowered_operand_{bi}_{ii}_{oi}() -> tryte:\n    return {value}')
            for ti,value in enumerate(i.targets): s.append(f'fn lowered_target_{bi}_{ii}_{ti}() -> tryte:\n    return {value}')
    return '\n'.join(s)

def _lane(source,name):
    return run_source(source+'\nfn main() -> tryte:\n    return '+name+'()\n',optimization='O0',mode=SyntaxMode.V0_6)

def candidate_exact_structure(p):
    _validate(p); source=_candidate_source(p)
    blocks=[]
    for bi,b in enumerate(p.blocks):
        instructions=[]
        for ii,i in enumerate(b.instructions):
            opcode_value=_lane(source,f'lowered_opcode_{bi}_{ii}')
            fields={1:'const',2:'add',3:'sub',4:'branch',5:'cond_branch',6:'return',7:'loop_back'}
            if opcode_value not in fields or fields[opcode_value] != i.opcode: raise M285Error('candidate opcode mismatch')
            opcode=fields[opcode_value]
            instructions.append(M285Instruction(opcode,_lane(source,f'lowered_result_{bi}_{ii}') if _lane(source,f'lowered_result_{bi}_{ii}')>=0 else None,tuple(_lane(source,f'lowered_operand_{bi}_{ii}_{j}') for j in range(_lane(source,f'lowered_operand_count_{bi}_{ii}'))),tuple(_lane(source,f'lowered_target_{bi}_{ii}_{j}') for j in range(_lane(source,f'lowered_target_count_{bi}_{ii}'))),_lane(source,f'lowered_immediate_{bi}_{ii}') if _lane(source,f'lowered_immediate_present_{bi}_{ii}') else None))
        blocks.append(M285Block(_lane(source,f'lowered_block_id_{bi}'),tuple(instructions)))
    return M285Program(tuple(blocks),_lane(source,'lowered_register_count'))

def candidate_matches_reference(p):
    return exact_structure(candidate_exact_structure(p)) == exact_structure(p)

def m284_linear_interop():
    from bootstrap.s3.canonical_ir_candidate import CanonicalIRBlock,CanonicalIRFunction,CanonicalIRInstruction,CanonicalIRProgram
    from bootstrap.s3.canonical_ir_verifier_candidate import run_ir_verifier_differential
    from bootstrap.s3.ir import IRType,IROpcode
    linear=CanonicalIRProgram((CanonicalIRFunction(0,IRType.TRYTE,(IRType.TRYTE,), (CanonicalIRBlock(0,(CanonicalIRInstruction(IROpcode.CONST,0,immediate=1),CanonicalIRInstruction(IROpcode.RETURN,operands=(0,)))),)),))
    return run_ir_verifier_differential(linear)

def aggregate_call_fixture():
    from bootstrap.s3.call_aggregate_lowering_candidate import CallLoweringInput,lower_call_reference
    from bootstrap.s3.ir import IRType
    plan=lower_call_reference(CallLoweringInput(9,(IRType.TRYTE,),(0,),(IRType.TRYTE,)))
    return plan,M285Program((M285Block(0,(M285Instruction('call',result=1,operands=plan.argument_registers,immediate=plan.callee_id),M285Instruction('return',operands=(1,)))),),2)
