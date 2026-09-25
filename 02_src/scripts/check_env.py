"""One command that tells you whether this machine is ready to run ADII.

Runs on Windows, macOS, and Linux with no shell, no Make, and no assumptions about
which package manager anyone uses:  python 02_src/scripts/check_env.py
"""
from __future__ import annotations

import importlib.util
import platform
import sys

REQUIRED = (3, 12)


def _check(label: str, ok: bool, detail: str) -> bool:
    print(f"  [{'ok ' if ok else 'FAIL'}] {label:22s} {detail}")
    return ok


def main() -> int:
    print(f"ADII environment check — {platform.system()} {platform.machine()}\n")
    version = sys.version_info
    results = [
        _check("python", version[:2] == REQUIRED,
               f"{version.major}.{version.minor}.{version.micro} "
               f"(need {REQUIRED[0]}.{REQUIRED[1]}.x)"),
        _check("adii importable", importlib.util.find_spec("adii") is not None,
               "yes" if importlib.util.find_spec("adii") is not None
               else "installed?  pip install -r requirements.txt"),
        _check("pytest", importlib.util.find_spec("pytest") is not None, "test runner"),
        _check("ruff", importlib.util.find_spec("ruff") is not None, "linter"),
    ]
    print()
    if all(results):
        print("Ready. Next:  python -m adii.examples.walkthrough --step")
        return 0
    print("Not ready. Fix the FAIL lines above, then run this again.")
    print("Setup instructions are in README.md (Windows and macOS both covered).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
