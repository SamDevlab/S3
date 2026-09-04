"""External benchmark harness package.

This package is repository-only and intentionally outside the published S3
bootstrap package.
"""

from .campaign import aggregate_campaign, list_campaigns, load_campaign
from .comparison import compare_campaign
from .core import ExternalBenchmarkError, evaluate_scenario, load_scenario, list_scenarios
from .report import render_comparison_markdown

__all__ = ["ExternalBenchmarkError", "aggregate_campaign", "compare_campaign", "evaluate_scenario", "list_campaigns", "list_scenarios", "load_campaign", "load_scenario", "render_comparison_markdown"]
