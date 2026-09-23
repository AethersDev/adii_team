"""Copy the identity handoff's logo into the front door.

    python 02_src/scripts/sync_identity.py

The design system is delivered to 03_assets/identity/ as an archive and stays exactly as
delivered. The front door (final plan, decision W) draws its own page but not its own mark:
the logo is the handoff's, unchanged, served from a copy, because nothing the system needs
to run may live in 03_assets. A test fails the build when the copy and the handoff differ,
so there is one source of truth and it is the handoff.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "03_assets" / "identity" / "assets" / "logo"
TARGET = ROOT / "02_src" / "adii" / "demo" / "web" / "logo"
FILES = ("adii-lockup-horizontal.svg", "adii-symbol.svg", "favicon.svg")


def stale() -> list[str]:
    return [f for f in FILES
            if not (TARGET / f).exists() or (TARGET / f).read_bytes() != (SOURCE / f).read_bytes()]


def main() -> int:
    changed = stale()
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in changed:
        shutil.copyfile(SOURCE / name, TARGET / name)
        print(f"wrote {(TARGET / name).relative_to(ROOT)}")
    if not changed:
        print("already in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
