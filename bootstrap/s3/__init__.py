"""S3 bootstrap APIs, imported lazily to keep runtime-only paths isolated."""

from importlib import import_module


_EXPORTS = {
    "OptimizationLevel": (".optimizer", "OptimizationLevel"),
    "CompilationCache": (".pipeline", "CompilationCache"),
    "CompilationCacheInfo": (".pipeline", "CompilationCacheInfo"),
    "compile_source": (".pipeline", "compile_source"),
    "run_source": (".pipeline", "run_source"),
    "deserialize_ir": (".ir_serialization", "deserialize_ir"),
    "serialize_ir": (".ir_serialization", "serialize_ir"),
    "compile_program": (".whole_program", "compile_program"),
}

__all__ = [
    "OptimizationLevel",
    "CompilationCache",
    "CompilationCacheInfo",
    "compile_source",
    "deserialize_ir",
    "run_source",
    "serialize_ir",
]


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value
