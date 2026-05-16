"""Minimal test runner (no pytest dependency).

Usage: python -m tests.run
Discovers test_* functions in tests/test_*.py modules, runs them,
and exits non-zero on any failure.
"""

import importlib
import pkgutil
import traceback

import tests


def main():
    passed = failed = 0
    for mod_info in pkgutil.iter_modules(tests.__path__):
        if not mod_info.name.startswith("test_"):
            continue
        mod = importlib.import_module(f"tests.{mod_info.name}")
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(mod, name)()
                print(f"PASS {mod_info.name}.{name}")
                passed += 1
            except Exception:
                print(f"FAIL {mod_info.name}.{name}")
                traceback.print_exc()
                failed += 1
    print(f"--- {passed}/{passed + failed} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
