        frontend = ingest_source_frontend(context)
        if not frontend.success:
            return context._failure_result(test_artifact_input=False)

        context.phases.begin(PhaseKind.SEMANTIC)
        context.phases.fail(
            "S3E_SEMANTIC_PHASE_UNAVAILABLE",
            "generic source frontend and declaration types are resolved; "
            "expression/declaration semantic analysis is not implemented",
        )
        return context._failure_result(test_artifact_input=False)

    return context.compose(prepared_artifacts)


__all__ = [
    "BlockId", "CallTarget", "CompositionError", "DeclarationId", "DiagnosticArena", "DiagnosticId", "DiagnosticRecord",
    "ExportRecord", "ExportSpec", "FieldSpec", "FunctionId", "FunctionRecord", "FunctionSpec", "FunctionSignature",
    "IdRange", "ImportRecord", "ImportSpec", "InstructionId", "ModuleId", "ModuleRecord", "ModuleSpec", "NominalTypeId",
    "NominalTypeRecord", "NominalTypeSpec", "NodeId", "ParameterRecord", "ParameterSpec", "PhaseKind", "PhaseOrchestrator", "PhaseRecord",
    "PhaseStatus", "PreparedProgramArtifacts", "ProgramId", "ProgramRegistry", "ProgramRegistryCheckpoint", "RegistrationError",
    "ScopeId", "SemanticDeclaration", "SemanticSeed", "SemanticState", "SemanticStateError", "StorageId", "TypeArena",
    "TypeArenaCheckpoint", "TypeArenaError", "TypeId", "TypeInfo", "TypeKind", "TypeSpec", "ValueId", "WholeProgramCompileResult",
    "WholeProgramContext", "compile_program",
]