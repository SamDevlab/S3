"""Internal deterministic IR pass sequencing."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .ir import IRFunction, IRModule


class IRPass(Protocol):
    name: str

    def run_function(self, function: IRFunction) -> IRFunction:
        ...


@dataclass(frozen=True, slots=True)
class FunctionPass:
    name: str
    transform: Callable[[IRFunction], IRFunction]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("pass name must be non-empty")

    def run_function(self, function: IRFunction) -> IRFunction:
        return self.transform(function)

    def run(self, module: IRModule) -> IRModule:
        return IRModule(
            tuple(self.run_function(function) for function in module.functions)
        )


@dataclass(frozen=True, slots=True)
class PassManager:
    passes: tuple[IRPass, ...] = ()

    def __init__(self, passes: Iterable[IRPass] = ()) -> None:
        items = tuple(passes)
        names: set[str] = set()
        duplicates: set[str] = set()
        for item in items:
            if not item.name:
                raise ValueError("pass name must be non-empty")
            if item.name in names:
                duplicates.add(item.name)
            names.add(item.name)
        if duplicates:
            rendered = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate pass name(s): {rendered}")
        object.__setattr__(self, "passes", items)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(pass_.name for pass_ in self.passes)

    def run(self, module: IRModule) -> IRModule:
        if not self.passes:
            return module
        return IRModule(
            tuple(self._run_function(function) for function in module.functions)
        )

    def _run_function(self, function: IRFunction) -> IRFunction:
        result = function
        for pass_ in self.passes:
            result = pass_.run_function(result)
        return result
