"""scripts/check_env.py as a fixture, loaded from its file: scripts/ is not a package, and a
script that is run as `python 02_src/scripts/check_env.py` stays that."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_env.py"


@pytest.fixture(scope="session")
def check_env():
    spec = importlib.util.spec_from_file_location("check_env", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
