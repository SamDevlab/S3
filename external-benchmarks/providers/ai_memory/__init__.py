"""Optional AI-MEMORY adapter for S3 external benchmarks."""

from .client import AiMemoryClient, AiMemoryConfig, AiMemoryProviderError
from .runner import (
    AiMemoryLaunch,
    build_managed_run_command,
    execute_managed_run,
    workstream_name_from_plan,
)

__all__ = [
    "AiMemoryClient",
    "AiMemoryConfig",
    "AiMemoryLaunch",
    "AiMemoryProviderError",
    "build_managed_run_command",
    "execute_managed_run",
    "workstream_name_from_plan",
]
