"""External benchmark harness package.

This package is repository-only and intentionally outside the published S3
bootstrap package.
"""

from .core import ExternalBenchmarkError, evaluate_scenario, load_scenario, list_scenarios

__all__ = [
    "ExternalBenchmarkError",
    "evaluate_scenario",
    "load_scenario",
    "list_scenarios",
]
