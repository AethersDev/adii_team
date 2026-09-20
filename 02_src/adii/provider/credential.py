"""Where the credential comes from, for every entrypoint that spends: the environment, and
when the environment lacks it, the operator's `.env.local` at the repository root."""
from __future__ import annotations

import os
from pathlib import Path

from ..reporting.record import REPO

ENV_LOCAL = ".env.local"


def load_env_local(root: Path | None = None) -> None:
    """The operator's convenience, never the provider's contract: when OPENAI_API_KEY is not
    in the environment and `.env.local` at `root` (the repository, unless a test says
    otherwise) is a file, that one name is read from it into the environment. Bare
    `NAME=value` lines, blank lines and `#` comments; any other line is refused by number —
    a value is never printed — and a quoted value is refused rather than guessed at.
    Nothing else in the file is read, and a value already in the environment is never
    overwritten, so the shell's word always stands."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    path = (REPO if root is None else root) / ENV_LOCAL
    if not path.is_file():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, equals, value = (part.strip() for part in line.partition("="))
        if not equals or not name.isidentifier():
            raise ValueError(f"{ENV_LOCAL} line {number}: expected NAME=value")
        if name != "OPENAI_API_KEY":
            continue
        if value[:1] in ("'", '"'):
            raise ValueError(f"{ENV_LOCAL} line {number}: OPENAI_API_KEY must be the bare "
                             "value, unquoted")
        if value:
            os.environ["OPENAI_API_KEY"] = value
        return
