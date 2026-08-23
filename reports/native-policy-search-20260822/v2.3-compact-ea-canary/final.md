# ABL V2.3 Compact-EA Experimental Canary Gate

{
  "benchmarks": "NOT_RUN",
  "branch": "experiment/native-policy-search-20260822",
  "campaign": "S3-ABL-V2.3-COMPACT-EA-EXPERIMENTAL-CANARY-GATE-20260822",
  "coverage": {
    "canary_applied_functions": 37,
    "canary_compact_ea_applications": 91,
    "canary_requests": 91,
    "canary_safety_rejections": 54,
    "indexed_candidates": 107,
    "no_fabrication": true,
    "status": "INSUFFICIENT_FOR_TARGET",
    "target": 100
  },
  "hard_regressions": 0,
  "modes": {
    "canary": "explicit_opt_in",
    "default": "off",
    "shadow_identity": true
  },
  "negative_controls": {
    "controls": [
      {
        "fallback_identity": true,
        "function_fingerprint": "c5c99f545856cd161e2de74c29264ef9a79eac56431e581788a9bb8c101967a5",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cd1ca7828b6e8d5d2bd48bf183df2cd0e803effee0841a7f3d141e9d68d581d2",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cb37c917f9f8bc19606dd1200e0ebe279781d2b481e285cf76154e40f3ccf6d8",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "f10205e4080012d7920d09da60cc3ce8402eecd551b16614357dab0ab99b6635",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8c2deadf0b366f05d524052d095f4af7ec5972872371322d79689f7ed15e4629",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "58faf82defe5a873b59b7f546a68263d8a56dd3848219f4efa78d07f39cbd917",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "e40d488584927fe47268c1521f53328cfd90475fb8b3debb6f584eac67ccde3b",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "9a5c79ebd113751f4010bc3c7ea32499420d82acfb41525ae2604b739ec41227",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8c2deadf0b366f05d524052d095f4af7ec5972872371322d79689f7ed15e4629",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "ae773760465223ce30ad73cff98d2b1b1dd7c7d851c4867504a7bb950e29a6cc",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cd1ca7828b6e8d5d2bd48bf183df2cd0e803effee0841a7f3d141e9d68d581d2",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "56d62fc583637d7d9dcad84a22d1734a697ff75f4cdffde48d07cae387a708eb",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cacafbd008cd84bb23c1caa047c5b2914090ca6008754b657bab40695067c605",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cb37c917f9f8bc19606dd1200e0ebe279781d2b481e285cf76154e40f3ccf6d8",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "6298ce38bd7be81fb9668ac0f7f7ec6582f3bc1a36fa2807c2d8dbc70fe5b299",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "ae773760465223ce30ad73cff98d2b1b1dd7c7d851c4867504a7bb950e29a6cc",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "9a5c79ebd113751f4010bc3c7ea32499420d82acfb41525ae2604b739ec41227",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8c2deadf0b366f05d524052d095f4af7ec5972872371322d79689f7ed15e4629",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "60f28f2cf3a4a9da63c4467120ec83987565746dde90367853426990969252cc",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "ae773760465223ce30ad73cff98d2b1b1dd7c7d851c4867504a7bb950e29a6cc",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cb37c917f9f8bc19606dd1200e0ebe279781d2b481e285cf76154e40f3ccf6d8",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "56d62fc583637d7d9dcad84a22d1734a697ff75f4cdffde48d07cae387a708eb",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "58faf82defe5a873b59b7f546a68263d8a56dd3848219f4efa78d07f39cbd917",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "f10205e4080012d7920d09da60cc3ce8402eecd551b16614357dab0ab99b6635",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "e40d488584927fe47268c1521f53328cfd90475fb8b3debb6f584eac67ccde3b",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "56d62fc583637d7d9dcad84a22d1734a697ff75f4cdffde48d07cae387a708eb",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "56d62fc583637d7d9dcad84a22d1734a697ff75f4cdffde48d07cae387a708eb",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "cacafbd008cd84bb23c1caa047c5b2914090ca6008754b657bab40695067c605",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "d1791856c85a59992b6ca1ac8c78e2c1bbe255b56828a0eb22885c9ead627968",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "b2799ea6338b20cb3e9701d01278d74c5cf4c380271ae7ee335a4ffdfb272711",
        "reason": "canary_safety_fallback:calls_or_cross_call_liveness_present"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "8b028d8ada6da5c953b33f7584379f381bb45ae219812305e0abbe6c03387597",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "777601916e1ddbb276f45a09439bb163c1f2e9da300ee4cfde5c5ec33427e373",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "749c9b5edb640efa45075697dfbfd9b657c12388c845aa5240c7e5092bda60f6",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      },
      {
        "fallback_identity": true,
        "function_fingerprint": "aceeafdd6e438069f88e51089399eab9da6036a41276bc338cb01747dfd1d5b1",
        "reason": "canary_safety_fallback:no_indexed_memory_operations"
      }
    ],
    "fallback_count": 54,
    "fallback_identity": true,
    "status": "PASS"
  },
  "next_recommended_action": "V2.4_COMPACT_EA_CANARY_GENERALIZATION_AND_SOAK",
  "pr": 190,
  "pr190_merged": false,
  "pr190_ready": "NO",
  "production_policy_changed": "NO",
  "publication_head": "e59b63d5eaeacda85373bfe48eff3309bc18398e",
  "qualification": {
    "coverage": "INSUFFICIENT_FOR_TARGET",
    "next": "V2.4_COMPACT_EA_CANARY_GENERALIZATION_AND_SOAK",
    "qualification": "YES_RESEARCH_ONLY",
    "t0": "PASS",
    "t1": "PASS",
    "t2": "PASS",
    "t3": "PASS"
  },
  "schema": "s3.native-policy-search.v23.compact-ea-canary",
  "structural_effects": {
    "baseline_metrics": {
      "branches": 18208,
      "frame_bytes": 17088,
      "instructions": 104693,
      "leas": 3722,
      "loads": 96,
      "movs": 33489,
      "spills_reload": 1434,
      "stack_ops": 1434,
      "stores": 1015,
      "text_bytes": 3213977,
      "total_load_store": 1111
    },
    "canary_metrics": {
      "branches": 18208,
      "frame_bytes": 17088,
      "instructions": 104602,
      "leas": 3722,
      "loads": 96,
      "movs": 33398,
      "spills_reload": 1434,
      "stack_ops": 1434,
      "stores": 1015,
      "text_bytes": 3212430,
      "total_load_store": 1111
    },
    "canary_minus_off": {
      "branches": 0,
      "frame_bytes": 0,
      "instructions": -91,
      "leas": 0,
      "loads": 0,
      "movs": -91,
      "spills_reload": 0,
      "stack_ops": 0,
      "stores": 0,
      "text_bytes": -1547,
      "total_load_store": 0
    },
    "timing": "NOT_RUN"
  },
  "t0": "PASS",
  "t1": "PASS",
  "t2": "PASS",
  "t3": "PASS",
  "timing": "NOT_RUN",
  "v23_source_lock": "e59b63d5eaeacda85373bfe48eff3309bc18398e"
}

## Terminal Qualification Summary

- `V23_SOURCE_LOCK`: `e59b63d5eaeacda85373bfe48eff3309bc18398e`
- final candidate head: `c0010ffdc1090749de3856fc8757fa16f442778a`
- source changed after final gates: NO
- canonical main: `2245c9f75b07b063b6da5716a753d02c1fee5f95`
- PR #190: OPEN, DRAFT, MERGEABLE, unmerged
- modes: `off`, `shadow`, `compact-ea-canary`
- default: OFF; OFF versus canonical-main representative identity: 4/4 identical
- SHADOW changed outputs: 0
- canary gene: `COMPACT_INDEXED_MEMORY_ONLY`; scalar promotion: NO
- canary requests: 91 function decisions; applied: 37 functions; fallbacks: 54
- compact-EA applications: 91; safety rejections: 54; encoding rejections: 0
- structural delta: instructions -91, MOVs -91, loads/stores 0, stack ops 0, spills/reloads 0, frame bytes 0
- hard regressions/harm: 0
- T1: 7 selected, 7 passed, 0 failed, 0 skipped
- T2: 47 selected, 18 passed, 0 failed, 29 skipped
- T3 Linux x86-64: 75 comparisons, 25 OFF + 25 SHADOW + 25 CANARY, 0 failed
- holdout: PASS; LOFO: PASS; determinism: PASS
- P7/P8/P9: deferred read-only; timing and benchmarks: not run
- V2.2 four-policy matrix: not re-run because its policy path was unchanged; focused regression passed
- status: `V23_COMPACT_EA_CANARY_QUALIFIED_RESEARCH_ONLY`
- coverage: `INSUFFICIENT_FOR_TARGET`; next: `V2.4_COMPACT_EA_CANARY_GENERALIZATION_AND_SOAK`
- production policy changed: NO; PR Ready: NO; PR merged: NO
