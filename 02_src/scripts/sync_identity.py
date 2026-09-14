"""Copy the identity handoff's stylesheets into the inspector.

    python 02_src/scripts/sync_identity.py

The design system is delivered to 03_assets/identity/ as an archive and stays exactly as
delivered, so its own checks and specimens keep working. The inspector runs on a copy of
the three stylesheets, because nothing the system needs to run may live in 03_assets. A
test fails the build when the copy and the handoff differ, so there is one source of truth
and it is the handoff.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "03_assets" / "identity" / "css"
TARGET = ROOT / "02_src" / "adii" / "demo" / "web"
FILES = ("tokens.css", "base.css", "components.css")


def stale() -> list[str]:
    return [f for f in FILES
            if not (TARGET / f).exists() or (TARGET / f).read_bytes() != (SOURCE / f).read_bytes()]


def main() -> int:
    changed = stale()
    for name in changed:
        shutil.copyfile(SOURCE / name, TARGET / name)
        print(f"wrote {(TARGET / name).relative_to(ROOT)}")
    if not changed:
        print("already in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
