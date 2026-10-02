# Contributing

Before proposing a change, run the checks the project holds itself to:

```bash
python -m ruff check 02_src
python -m pytest
python -m adii.evaluation.lock --check
```

[02_src/docs/architecture.md](../02_src/docs/architecture.md) describes the system and its
boundaries, which `02_src/tests/architecture/` enforces. The evaluated system is frozen: a
change to a frozen file fails `test_the_freeze.py` until a new freeze is taken, and that is
the authors' decision. The tagged states the paper cites (`freeze-*`, `paper-v1`) never change.

## Contributions from outside the team

The code is licensed under AGPL-3.0-only, and its authors may also license it on other
terms. To keep both possible, an outside contribution can be merged only after its author
has signed a contributor agreement that lets the authors relicense it. That agreement is
not published yet, so please open an issue to discuss a change before writing a pull
request; a pull request without a signed agreement cannot be merged.
