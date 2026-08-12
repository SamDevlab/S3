from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(root: Path, output: Path) -> None:
    dynamic = {}
    paths = sorted((root / "dynamic").glob("*-dynamic-v3.json"))
    if not paths:
        paths = sorted((root / "dynamic").glob("*-dynamic.json"))
    for path in paths:
        name = path.stem.removesuffix("-dynamic-v3").removesuffix("-dynamic")
        dynamic[name] = load(path)
    static = {
        path.stem.removesuffix("-static"): load(path)
        for path in sorted((root / "static").glob("*-static.json"))
    }
    semantic = {
        path.stem.removesuffix("-init-semantics"): load(path)
        for path in sorted((root / "semantics").glob("*-init-semantics.json"))
    }
    summary = {}
    for name, report in dynamic.items():
        total = int(report["dynamic_weighted_total"])
        rows = sorted(
            report["all_nonzero_sites"],
            key=lambda row: (-int(row["weighted_executions"]), int(row["event_id"])),
        )
        shares = {}
        for percent in (1, 5, 10):
            count = max(1, math.ceil(int(report["event_site_count"]) * percent / 100))
            shares[f"top_{percent}_percent_site_share"] = (
                sum(int(row["weighted_executions"]) for row in rows[:count]) / total
                if total
                else None
            )
        summary[name] = {
            "event_site_count": report["event_site_count"],
            "dynamic_event_site_count": report["dynamic_event_site_count"],
            "dynamic_weighted_total": total,
            "category_counts": report["category_counts"],
            "observer_counts": report["observer_counts"],
            "hotness": shares,
            "top_20_sites_share": (
                sum(int(row["weighted_executions"]) for row in rows[:20]) / total
                if total
                else None
            ),
            "emulator_result": report.get("emulator_result"),
            "emulator_error": report.get("emulator_error"),
        }
    output.write_text(
        json.dumps({"dynamic": summary, "static": static, "semantic": semantic}, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: p5_report_analysis.py DATA_ROOT OUTPUT")
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
