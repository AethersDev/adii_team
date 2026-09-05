"""Make scripts/check_env.py importable without turning scripts/ into a package."""
import importlib.util
import sys
import types
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_env", _root / "scripts" / "check_env.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
_shim = types.ModuleType("scripts_check_env_shim")
_shim.check_env = _module
sys.modules["scripts_check_env_shim"] = _shim
