"""Run the inspector:  python -m adii.demo [port] [--model ID [--provider local|openai]
[--endpoint URL] [--served-as NAME] [--max-turns N] [--max-tool-calls N]
[--max-model-requests N] [--max-wall-clock-seconds S] [--max-cost-usd USD] [--max-tokens N]
[--reasoning-effort LEVEL]].
Without --model the page is read-only. With it, runs may be started from the page: against
a local model by default, costing nothing; against a paid one when the operator says
`--provider openai` and starts this process with OPENAI_API_KEY in its environment — or in
the repository's ignored `.env.local`, read for that one name when the environment lacks it.
Every precondition of spending is checked here, before a port is bound, and stops the
process; the page never learns of credentials.
The flags are each run's default and the ceiling a request from the page may not pass; every
bound the runtime has is set here, so a run from the page runs under exactly the bounds a
run from the command line would, and /api/launch reports each of them."""
from __future__ import annotations

import argparse

from adii.demo.server import main
from adii.provider import REASONING_EFFORTS, endpoint_is_local, load_env_local
from adii.runtime.__main__ import refused_bounds, refused_paid

parser = argparse.ArgumentParser(prog="python -m adii.demo", description=__doc__)
parser.add_argument("port", nargs="?", type=int, default=8000)
parser.add_argument("--provider", choices=["local", "openai"], default="local",
                    help="local: an OpenAI-compatible endpoint on this machine, nothing spent; "
                         "openai: the paid path, capped per run")
parser.add_argument("--endpoint", default=None,
                    help="the base URL (default: Ollama's for local, api.openai.com for openai)")
parser.add_argument("--model", help="allow runs from the page; this model by default — on the "
                                     "paid path a visitor may pick any priced one")
parser.add_argument("--served-as", metavar="NAME",
                    help="the name the endpoint wants in requests when it differs from --model")
parser.add_argument("--max-turns", type=int, default=12)
parser.add_argument("--max-tool-calls", type=int, default=30)
parser.add_argument("--max-model-requests", type=int, default=None,
                    help="default: as many as --max-turns")
parser.add_argument("--max-wall-clock-seconds", type=float, default=600.0)
parser.add_argument("--max-cost-usd", type=float, default=0.25,
                    help="openai: the hard cap one run may not pass, at nominal prices")
parser.add_argument("--max-tokens", type=int, default=512,
                    help="openai: the most tokens one response may carry")
parser.add_argument("--reasoning-effort", choices=REASONING_EFFORTS,
                    help="openai, a reasoning model: sent in place of temperature on every run; "
                         "the page may then ask for this model only")
args = parser.parse_args()
if args.reasoning_effort and args.provider != "openai":
    raise SystemExit("--reasoning-effort is a paid reasoning model's setting: --provider openai")
launch = None
if args.model:
    if args.max_model_requests is None:
        args.max_model_requests = args.max_turns
    why = refused_bounds(args.max_turns, args.max_tool_calls, args.max_model_requests,
                         args.max_wall_clock_seconds)
    if why:
        raise SystemExit(why)
    if args.endpoint is None:
        args.endpoint = ("https://api.openai.com/v1" if args.provider == "openai"
                         else "http://127.0.0.1:11434/v1")
    if args.provider == "local" and not endpoint_is_local(args.endpoint):
        raise SystemExit(f"{args.endpoint} is not a local endpoint; a local model costs "
                         "nothing because it is on this machine — for a paid one, say "
                         "--provider openai")
    if args.provider == "openai":
        try:
            load_env_local()            # the operator's .env.local, when the shell has no key
        except ValueError as why:
            raise SystemExit(str(why)) from None
        # the page may ask for any priced model, so no wire alias can stand for "the" model
        why = (refused_paid(args.model, args.max_cost_usd, args.endpoint, args.served_as,
                            args.max_tokens)
               or (args.served_as and "--served-as is for local endpoints: on the paid path "
                                      "the name on the wire is the priced name, whichever the "
                                      "page asks for"))
        if why:
            raise SystemExit(f"{why}\nThe page can start paid runs only when this process was "
                             "started with the credential in its environment; start it "
                             "through the credential wrapper.")
    # The runtime's own flags, as the operator gave them: what the server forwards to every
    # run, and what /api/launch reports. The credential is not among them; the cap and the
    # response bound exist only where something is spent.
    launch = {"provider": args.provider, "endpoint": args.endpoint, "model": args.model,
              "served_as": args.served_as, "max_turns": args.max_turns,
              "max_tool_calls": args.max_tool_calls,
              "max_model_requests": args.max_model_requests,
              "max_wall_clock_seconds": args.max_wall_clock_seconds}
    if args.provider == "openai":
        launch.update(max_cost_usd=args.max_cost_usd, max_tokens=args.max_tokens)
        if args.reasoning_effort:
            launch["reasoning_effort"] = args.reasoning_effort
raise SystemExit(main(args.port, launch))
