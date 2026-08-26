"""Authoritative static-link entrypoint for final Stage1 self-emission.

The base qualifier owns the self-emit semantics and evidence format.  This thin
adapter replaces only its link function for the duration of the run so every
Stage2 candidate and smoke program uses the same deterministic freestanding
static recipe required by the later Landlock gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tools.qualify_stage1_final_self_emit as base
from tools.selfhost_static_link import assemble_link_static


def qualify(**kwargs: Any) -> dict[str, Any]:
    original = base._assemble_link
    base._assemble_link = assemble_link_static
    try:
        result = base.qualify(**kwargs)
        result["link_recipe"] = {
            "mode": "STATIC_FREESTANDING_FINAL_AUTHORITY",
            "flags": [
                "-static",
                "-nostdlib",
                "-no-pie",
                "-s",
                "-Wl,--build-id=none",
            ],
            "authoritative_runner": "tools/qualify_stage1_final_self_emit_static.py",
        }
        report = Path(kwargs["report"]).resolve()
        report.write_text(
            __import__("json").dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return result
    finally:
        base._assemble_link = original


def main(argv: list[str] | None = None) -> int:
    original_qualify = base.qualify
    original_link = base._assemble_link

    def patched_qualify(**kwargs: Any) -> dict[str, Any]:
        base._assemble_link = assemble_link_static
        try:
            result = original_qualify(**kwargs)
            result["link_recipe"] = {
                "mode": "STATIC_FREESTANDING_FINAL_AUTHORITY",
                "flags": [
                    "-static",
                    "-nostdlib",
                    "-no-pie",
                    "-s",
                    "-Wl,--build-id=none",
                ],
                "authoritative_runner": "tools/qualify_stage1_final_self_emit_static.py",
            }
            report = Path(kwargs["report"]).resolve()
            report.write_text(
                __import__("json").dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return result
        finally:
            base._assemble_link = original_link

    base.qualify = patched_qualify
    try:
        return base.main(argv)
    finally:
        base.qualify = original_qualify
        base._assemble_link = original_link


if __name__ == "__main__":
    raise SystemExit(main())
