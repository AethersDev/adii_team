"""Run the inspector:  python -m adii.demo [port] [--endpoint URL --model ID [--served-as NAME]
[--max-turns N]]. Without --model the page is read-only; with it, runs may be started from
the page against that local model."""
from __future__ import annotations

import argparse

from adii.demo.server import main
from adii.provider import endpoint_is_local

parser = argparse.ArgumentParser(prog="python -m adii.demo", description=__doc__)
parser.add_argument("port", nargs="?", type=int, default=8000)
parser.add_argument("--endpoint", default="http://127.0.0.1:11434/v1",
                    help="a local OpenAI-compatible base URL (default: Ollama's)")
parser.add_argument("--model", help="allow runs from the page, against this model")
parser.add_argument("--served-as", metavar="NAME",
                    help="the name the endpoint wants in requests when it differs from --model")
parser.add_argument("--max-turns", type=int, default=12)
args = parser.parse_args()
launch = None
if args.model:
    if not endpoint_is_local(args.endpoint):
        raise SystemExit(f"{args.endpoint} is not a local endpoint; the page never reaches a "
                         "paid provider")
    launch = {"endpoint": args.endpoint, "model": args.model, "served_as": args.served_as,
              "max_turns": args.max_turns}
raise SystemExit(main(args.port, launch))
