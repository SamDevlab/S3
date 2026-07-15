from __future__ import annotations


def main() -> int:
    print("S3 structured data capability inventory")
    print()
    print("current:")
    print("  records: not supported as source-level data")
    print("  structs: not supported as source-level data")
    print("  enums: not supported as source-level data")
    print("  sum types: not supported")
    print("  variants: not supported")
    print("  pattern matching: ternary match only, no general patterns")
    print("  tuples: not supported as source-level values")
    print("  named fields: not supported as source-level values")
    print("  arrays: supported with limitations")
    print("  strings: reserved, no runtime support")
    print()
    print("required for Assembly renderer subset:")
    print("  records for program/function/block/instruction/source shape")
    print("  enums or safe tags for opcodes, types, and operand kinds")
    print("  arrays for ordered collections")
    print("  strings for names and output text")
    print("  formatting helpers for deterministic text")
    print()
    print("temporary alternatives:")
    print("  parallel arrays")
    print("  numeric tags")
    print("  flattened scalar groups")
    print("  host-provided data during bootstrap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
