"""Collect and summarize GitHub Actions run/job evidence for the CI audit."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path


REPOSITORY = "SamDevlab/S3"


def gh_json(endpoint: str) -> object:
    output = subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp", endpoint],
        text=True,
    )
    return json.loads(output)


def flatten_pages(pages: list[dict], key: str) -> list[dict]:
    result: list[dict] = []
    for page in pages:
        result.extend(page.get(key, []))
    return result


def duration_seconds(started: str | None, completed: str | None) -> float | None:
    if not started or not completed:
        return None
    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
    end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    return max(0.0, (end - start).total_seconds())


def fetch_jobs(run: dict) -> list[dict]:
    endpoint = (
        f"/repos/{REPOSITORY}/actions/runs/{run['id']}/jobs?per_page=100"
    )
    pages = gh_json(endpoint)
    jobs = flatten_pages(pages, "jobs")
    result = []
    for job in jobs:
        seconds = duration_seconds(job.get("started_at"), job.get("completed_at"))
        result.append(
            {
                "job_id": job["id"],
                "run_id": run["id"],
                "workflow": run["name"],
                "event": run["event"],
                "branch": run.get("head_branch"),
                "head_sha": run.get("head_sha"),
                "run_attempt": run.get("run_attempt"),
                "job_name": job["name"],
                "runner": job.get("runner_name") or job.get("runner_group_name"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "duration_seconds": seconds,
                "duration_minutes": None if seconds is None else seconds / 60.0,
                "conclusion": job.get("conclusion"),
                "status": job.get("status"),
            }
        )
    return result


def add_minutes(target: dict[str, float], key: str, jobs: list[dict]) -> None:
    target[key] = round(
        sum(
            float(job["duration_minutes"])
            for job in jobs
            if job["duration_minutes"] is not None
        ),
        6,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-08-01")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    endpoint = (
        f"/repos/{REPOSITORY}/actions/runs?per_page=100&created=%3E%3D{args.since}"
    )
    runs = flatten_pages(gh_json(endpoint), "workflow_runs")
    with ThreadPoolExecutor(max_workers=8) as executor:
        job_groups = list(executor.map(fetch_jobs, runs))
    jobs = [job for group in job_groups for job in group]

    total_minutes: dict[str, float] = {}
    add_minutes(total_minutes, "all", jobs)
    add_minutes(total_minutes, "successful", [j for j in jobs if j["conclusion"] == "success"])
    add_minutes(total_minutes, "failed", [j for j in jobs if j["conclusion"] == "failure"])
    add_minutes(total_minutes, "cancelled", [j for j in jobs if j["conclusion"] == "cancelled"])

    by_workflow: dict[str, list[dict]] = defaultdict(list)
    by_event: dict[str, list[dict]] = defaultdict(list)
    by_branch: dict[str, list[dict]] = defaultdict(list)
    by_job: dict[str, list[dict]] = defaultdict(list)
    for job in jobs:
        by_workflow[job["workflow"]].append(job)
        by_event[job["event"]].append(job)
        by_branch[job["branch"] or "<unknown>"].append(job)
        by_job[job["job_name"]].append(job)

    def totals(groups: dict[str, list[dict]]) -> dict[str, float]:
        output: dict[str, float] = {}
        for key, group in groups.items():
            output[key] = round(
                sum(
                    float(job["duration_minutes"])
                    for job in group
                    if job["duration_minutes"] is not None
                ),
                6,
            )
        return dict(sorted(output.items(), key=lambda item: (-item[1], item[0])))

    run_by_id = {run["id"]: run for run in runs}
    run_minutes = {
        run_id: round(
            sum(
                float(job["duration_minutes"])
                for job in jobs
                if job["run_id"] == run_id and job["duration_minutes"] is not None
            ),
            6,
        )
        for run_id in run_by_id
    }

    duplicate_pairs = []
    by_workflow_sha: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        by_workflow_sha[(run["name"], run.get("head_sha", ""))].append(run)
    for (workflow, sha), group in by_workflow_sha.items():
        pushes = [run for run in group if run["event"] == "push"]
        pull_requests = [run for run in group if run["event"] == "pull_request"]
        for push in pushes:
            for pull_request in pull_requests:
                duplicate_pairs.append(
                    {
                        "workflow": workflow,
                        "head_sha": sha,
                        "push_run_id": push["id"],
                        "pull_request_run_id": pull_request["id"],
                        "branch": push.get("head_branch"),
                        "push_minutes": run_minutes.get(push["id"], 0.0),
                        "pull_request_minutes": run_minutes.get(
                            pull_request["id"], 0.0
                        ),
                    }
                )

    superseded = []
    by_workflow_branch: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        by_workflow_branch[(run["name"], run.get("head_branch") or "")].append(run)
    for (workflow, branch), group in by_workflow_branch.items():
        ordered = sorted(group, key=lambda run: run["created_at"])
        for older, newer in zip(ordered, ordered[1:]):
            if older.get("head_sha") == newer.get("head_sha"):
                continue
            if older.get("updated_at", "") > newer.get("created_at", ""):
                superseded.append(
                    {
                        "workflow": workflow,
                        "branch": branch,
                        "older_run_id": older["id"],
                        "older_head_sha": older.get("head_sha"),
                        "newer_run_id": newer["id"],
                        "newer_head_sha": newer.get("head_sha"),
                        "older_minutes": run_minutes.get(older["id"], 0.0),
                        "older_conclusion": older.get("conclusion"),
                    }
                )

    event_run_counts = Counter(run["event"] for run in runs)
    workflow_run_counts = Counter(run["name"] for run in runs)
    output = {
        "repository": REPOSITORY,
        "since": args.since,
        "run_count": len(runs),
        "job_count": len(jobs),
        "runs": runs,
        "jobs": jobs,
        "run_minutes": total_minutes,
        "workflow_minutes": totals(by_workflow),
        "event_minutes": totals(by_event),
        "branch_minutes": totals(by_branch),
        "job_minutes": totals(by_job),
        "workflow_run_counts": dict(workflow_run_counts),
        "event_run_counts": dict(event_run_counts),
        "duplicate_push_pr_pairs": duplicate_pairs,
        "superseded_candidates": superseded,
        "duplicate_push_pr_minutes": round(
            sum(item["push_minutes"] for item in duplicate_pairs), 6
        ),
        "superseded_minutes": round(
            sum(item["older_minutes"] for item in superseded), 6
        ),
        "research_branch": "research/zettelkasten-lab-20260812",
        "research_branch_run_count": sum(
            run.get("head_branch") == "research/zettelkasten-lab-20260812"
            for run in runs
        ),
        "research_branch_minutes": round(
            sum(
                run_minutes.get(run["id"], 0.0)
                for run in runs
                if run.get("head_branch") == "research/zettelkasten-lab-20260812"
            ),
            6,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
