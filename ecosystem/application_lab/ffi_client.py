"""Isolated Python ctypes caller for the qualified scalar-i64 FFI fixture."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="s3-ffi-ctypes-client")
    parser.add_argument("library")
    parser.add_argument("symbol")
    parser.add_argument("cases_json")
    parser.add_argument("missing_symbol")
    parser.add_argument("missing_library")
    args = parser.parse_args(argv)
    try:
        cases = json.loads(args.cases_json)
        if not isinstance(cases, list) or not cases:
            raise ValueError("cases must be a non-empty JSON list")
        library = ctypes.CDLL(args.library)
        function = getattr(library, args.symbol)
        function.argtypes = [ctypes.c_int64, ctypes.c_int64]
        function.restype = ctypes.c_int64
        results = []
        for case in cases:
            values = case["arguments"]
            actual = int(function(values[0], values[1]))
            results.append({"name": case["name"], "actual": actual})
        try:
            getattr(library, args.missing_symbol)
        except AttributeError:
            missing_symbol_rejected = True
        else:
            missing_symbol_rejected = False
        try:
            ctypes.CDLL(args.missing_library)
        except OSError:
            missing_library_rejected = True
        else:
            missing_library_rejected = False
        print(json.dumps({
            "results": results,
            "missing_symbol_rejected": missing_symbol_rejected,
            "missing_library_rejected": missing_library_rejected,
        }, sort_keys=True))
        return 0
    except (AttributeError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
