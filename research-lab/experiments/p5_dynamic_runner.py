from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_source


EVENT_RE = re.compile(r"^\s*# P5_EVENT (?P<payload>\{.*\})$")


def run(source_path: Path, output_path: Path, optimization: str = "O1") -> None:
    source = source_path.read_text(encoding="utf-8")
    compilation = compile_source(source, optimization)
    try:
        emulator_result = Emulator().execute(compilation.assembly)
        emulator_error = None
    except Exception as error:
        emulator_result = None
        emulator_error = str(error)
    assembly = X8664Backend().generate(compilation.assembly)
    events = []
    for line in assembly.splitlines():
        match = EVENT_RE.match(line)
        if match:
            events.append(json.loads(match.group("payload")))
    events.sort(key=lambda event: int(event["event_id"]))
    if [event["event_id"] for event in events] != list(range(len(events))):
        raise AssertionError("temporary P5 event IDs are not a complete sequence")

    toolchain = NativeToolchain.detect()
    with tempfile.TemporaryDirectory(prefix="s3-p5-dynamic-") as temporary:
        root = Path(temporary)
        counter_path = root / "counters.bin"
        counter_file = counter_path.open("w+b")
        executable = toolchain.build(
            assembly,
            root / "program",
            keep_assembly=root / "program.s",
        )

        def _install_counter_fd() -> None:
            os.dup2(counter_file.fileno(), 3)

        try:
            completed = subprocess.run(
                [str(executable)],
                check=False,
                capture_output=True,
                timeout=30.0,
                pass_fds=(counter_file.fileno(),),
                preexec_fn=_install_counter_fd,
            )
        finally:
            counter_file.close()
        payload = counter_path.read_bytes()

    if completed.returncode != 0:
        raise RuntimeError(
            f"native workload failed with {completed.returncode}: "
            f"{completed.stderr.decode(errors='replace')}"
        )
    newline = completed.stdout.find(b"\n")
    if newline < 0:
        raise RuntimeError("native workload did not emit the normal result line")
    expected = len(events) * 8
    if len(payload) != expected:
        raise RuntimeError(
            f"counter payload length {len(payload)} does not equal {expected}"
        )
    values = struct.unpack(f"<{len(events)}Q", payload) if events else ()
    rows = []
    category_counts: Counter[str] = Counter()
    function_counts: Counter[str] = Counter()
    block_counts: Counter[str] = Counter()
    observer_counts: Counter[str] = Counter()
    for event, count in zip(events, values):
        weighted = count * int(event["weight"])
        if weighted:
            row = dict(event)
            row["executions"] = count
            row["weighted_executions"] = weighted
            rows.append(row)
            category_counts[str(event["category"])] += weighted
            function_counts[str(event["function"])] += weighted
            block_counts[f"{event['function']}::{event['block']}"] += weighted
            observer_counts[str(event["observer_class"])] += weighted
    result = {
        "source": str(source_path),
        "optimization": optimization,
        "return_line": completed.stdout[: newline + 1].decode("ascii"),
        "emulator_result": emulator_result,
        "emulator_error": emulator_error,
        "event_site_count": len(events),
        "dynamic_event_site_count": len(rows),
        "dynamic_weighted_total": sum(category_counts.values()),
        "category_counts": dict(sorted(category_counts.items())),
        "function_counts": dict(function_counts.most_common()),
        "block_counts": dict(block_counts.most_common()),
        "observer_counts": dict(observer_counts.most_common()),
        "top_sites": sorted(
            rows,
            key=lambda row: (-int(row["weighted_executions"]), int(row["event_id"])),
        )[:100],
        "all_nonzero_sites": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: p5_dynamic_runner.py SOURCE OUTPUT [O0|O1]")
    run(
        Path(sys.argv[1]).resolve(),
        Path(sys.argv[2]).resolve(),
        sys.argv[3] if len(sys.argv) == 4 else "O1",
    )
