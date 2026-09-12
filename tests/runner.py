"""Tiny test runner. No pytest: a framework is not worth a dependency here."""
import sys
import traceback


def run(module) -> int:
    tests = [(n, f) for n, f in vars(module).items()
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except Exception:
            failed.append(name)
            print(f"  ✗ {name}")
            print("      " + traceback.format_exc().strip().replace("\n", "\n      "))
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


def main(module) -> None:
    sys.exit(run(module))
