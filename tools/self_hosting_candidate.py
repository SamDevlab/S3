from __future__ import annotations


def main() -> int:
    print("S3 first self-hosting component candidate")
    print()
    print("selected: Assembly renderer subset")
    print("python reference: bootstrap/s3/assembly.py")
    print("initial fixtures:")
    print("  examples/first.s3")
    print("  examples/simple_call.s3")
    print("  examples/sign.s3")
    print("blocked by:")
    print("  strings")
    print("  arrays/vectors")
    print("  records/structs")
    print("  reusable helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
