"""Markdown reporting for external benchmark comparisons."""

from __future__ import annotations

from typing import Any, Mapping


def _pct(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def _num(value: object) -> str:
    if value is None:
        return "n/a"
    return str(value)


def render_comparison_markdown(comparison: Mapping[str, Any]) -> str:
    lines = [
        f"# {comparison['campaign_id']} comparison",
        "",
        f"- Comparison schema: `{comparison['schema_version']}`",
        f"- Campaign version: `{comparison['campaign_version']}`",
        f"- Comparability: **{comparison['comparability']['status']}**",
        f"- Repetitions per provider: {comparison['comparability']['repetitions']}",
        "",
    ]
    reasons = comparison["comparability"].get("reasons", [])
    if reasons:
        lines.extend(["## Comparability blockers", ""])
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")

    lines.extend(
        [
            "## Provider outcomes",
            "",
            "| Provider | Campaign runs passed | Scenario pass rate | Critical oracle failures | Mean invariant recall |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for provider_id, metrics in comparison["providers"].items():
        lines.append(
            f"| `{provider_id}` | "
            f"{metrics['campaign_runs_passed']}/{metrics['campaign_runs_total']} | "
            f"{_pct(metrics['scenario_pass_rate'])} | "
            f"{_num(metrics['critical_oracle_failures'])} | "
            f"{_pct(metrics['mean_invariant_recall_rate'])} |"
        )

    lines.extend(["", "## Scenario detail", ""])
    scenario_ids = sorted(
        {
            scenario_id
            for provider in comparison["providers"].values()
            for scenario_id in provider["scenarios"]
        }
    )
    for scenario_id in scenario_ids:
        lines.extend(
            [
                f"### `{scenario_id}`",
                "",
                "| Provider | Passed | Pass rate | Critical oracle failures | Mean invariant recall |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for provider_id, metrics in comparison["providers"].items():
            row = metrics["scenarios"].get(scenario_id)
            if row is None:
                lines.append(f"| `{provider_id}` | n/a | n/a | n/a | n/a |")
                continue
            lines.append(
                f"| `{provider_id}` | {row['passed']}/{row['runs']} | "
                f"{_pct(row['pass_rate'])} | "
                f"{_num(row['critical_oracle_failures'])} | "
                f"{_pct(row['mean_invariant_recall_rate'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation rule",
            "",
            "This report is deliberately neutral. It does not select a winner.",
            "Correctness outcomes and recall are reported separately, and recall never overrides an oracle failure.",
            "If comparability is `NOT_COMPARABLE`, provider-to-provider capability claims must not be made from this report.",
            "",
        ]
    )
    return "\n".join(lines)
