"""Run the demo:  python -m adii.demo  [port]"""
from __future__ import annotations

import sys

from adii.demo.server import main

raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000))
