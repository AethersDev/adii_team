"""One command, one incident, one archived run, one report.

    python -m adii.runtime --incident demo-learning-001 --provider scripted

`scripted` replays the investigator and the validator from the walkthrough's recorded run — no
model runs — and drives them through the real runtime over the real tool layer, against the
walkthrough world. The record that lands in the archive was
produced, not assembled, and its observations are what the tools actually returned.

    python -m adii.runtime --incident orders-missing-day --provider local \
        --endpoint http://127.0.0.1:11434/v1 --model llama3.1

`local` (SPIKE) drives A's real investigator loop with a model behind an OpenAI-compatible
endpoint on this machine — Ollama, LM Studio, mlx_lm.server — over the real tool layer,
against the walkthrough world or a development specimen's. Nothing is paid for; the receipt
is written all the same, before the investigator runs, on every path.

    OPENAI_API_KEY=... python -m adii.runtime --incident revenue-after-deploy --provider openai \
        --model gpt-4.1-mini --max-cost-usd 0.25

`openai` is the same loop against a paid endpoint. Every precondition is checked before
the label is claimed: the model has a nominal price in reporting/ledger.py, the cap is
above zero, the endpoint is https and carries no secret, the credential is in the
environment — and never in the command line, the receipt, the trace or the record. When
the environment lacks it, `<repo>/.env.local` (ignored by git; `.env.example` names it)
is read for that one name, so a rehearsal is one command; the environment is the contract,
the file the operator's convenience, and a value already set is never overwritten. The
receipt names the cap and who permitted the spend. The cap is hard: before each request the
provider reserves its worst case — every byte of the messages as a token at the input rate,
`max_tokens` at the output rate — and a request whose reserve would cross the cap is not
sent; the record's cost is the ledger's lower bound, proved usage at nominal prices, with
the unknown rows counted. The validator (M6) is not yet wired into the live path, so a live
REPAIR carries a verdict that says exactly that: not checked, therefore not accepted, and no
finding about the repair.

Six bounds, each its own resource, each named in the `bound_hit` it causes: `--max-turns`
(A's model turns), `--max-tool-calls` (the executor's), `--max-model-requests` (the
provider's; when omitted, as many as the turns) and `--max-wall-clock-seconds` (the
provider's: no request is sent past it, and a request in flight is cut at the deadline —
the local run never waits past it), `--max-cost-usd` and `--max-tokens` (paid only). All
six are in the receipt and the record.

Exit codes, one per way a run can end:
    0  a decision was archived          3  the loop ended the run without a decision; archived
    1  the label is taken               4  an infrastructure failure; archived, traceback on stderr
    2  usage: unknown incident, or a label the archive cannot hold
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath

from ..contracts import IncidentContext
from ..examples.canonical_world import INCIDENTS
from ..examples.specimens import SPECIMENS
from ..examples.walkthrough import FIXTURE, load
from ..provider import (
    PROTOCOL,
    REASONING_EFFORTS,
    TIMEOUT_S,
    endpoint_may_carry_a_credential,
    initial_messages,
    input_tokens_upper_bound,
    load_env_local,
)
from ..reporting import render_run, write_record
from ..reporting.ledger import BYTE_LEVEL_TOKENIZERS, PRICES, aggregate, reserve_for
from ..reporting.receipts import NAME as RECEIPT
from ..reporting.receipts import digest_of, write_receipt
from ..reporting.record import ARCHIVE, LABEL, reserve
from ..tools import (
    EVIDENCE_BUNDLES,
    ReadOnlyDatabase,
    ToolExecutor,
    build_sql_tools,
    canonical_json,
    change_history_observation,
    load_change_histories,
    load_declared_schemas,
    load_notice_sources,
    load_reconciliation_sources,
    load_transform_sources,
    open_walkthrough_world,
)
from ..tools.walkthrough_world import build_script
from .run import Recorder, run_incident
from .scripted import AlwaysEscalate, replay

# The three arms of the controls (inherited CONTROLS.md): what the full investigator adds is
# measured against the same model with no tools and against no model at all.
ARMS = ("full", "alert-only", "always-escalate")


def armed(arm: str, tools, max_tool_calls: int):
    """The tool surface an arm investigates with: the incident's own, or — alert-only — none,
    so every call is refused as an unknown tool and the model decides from the alert."""
    return ToolExecutor(max_calls=max_tool_calls) if arm == "alert-only" else tools

WALKTHROUGH_WORLD = build_script()


def readable_or_refused(context: IncidentContext, transform_sources: dict[str, str]) -> None:
    """The rule that keeps a repair from being written blind: every path the incident permits
    the investigator to change is one it can read through the evidence surface —
    `transforms/<name>.sql` is served by `get_transform("<name>")`. An incident that permits a
    path it cannot show is refused here, before any label, never handed to a model that would
    have to patch a file it has never seen (three paid runs asked for one and were refused)."""
    missing = [p for p in context.permitted_write_paths
               if PurePosixPath(p).stem not in transform_sources]
    if missing:
        raise ValueError(f"the incident permits writing {', '.join(missing)} but the evidence "
                         "surface cannot show it: a repair target the investigator cannot read "
                         "would be patched blind — add its transform source or drop the path")


def incident(incident_id: str, max_tool_calls: int | None = None):
    """The incident's context, a fresh tool layer over its world — `max_tool_calls` is the
    executor's budget — the world's digest, the walkthrough's recorded run if this is the
    walkthrough, and the receipt's digests of the evidence the tools will show. None when no
    such incident exists; ValueError when the incident permits a path it cannot show."""
    context, recorded = load()
    if incident_id == context.incident_id:
        sources = load_transform_sources(FIXTURE)
        readable_or_refused(context, sources)
        tools = build_sql_tools(open_walkthrough_world(), max_calls=max_tool_calls,
                                transform_sources=sources or None)
        evidence = {"transforms": digest_of(canonical_json(sources))} if sources else {}
        return context, tools, digest_of(WALKTHROUGH_WORLD), recorded, evidence
    for specimen in SPECIMENS:
        if specimen.context.incident_id == incident_id:
            readable_or_refused(specimen.context, specimen.transforms)
            tools = build_sql_tools(ReadOnlyDatabase.in_memory(specimen.world),
                                    max_calls=max_tool_calls,
                                    transform_sources=specimen.transforms or None)
            if specimen.extra_tool:
                tools.register(*specimen.extra_tool)
            evidence = ({"transforms": digest_of(canonical_json(specimen.transforms))}
                        if specimen.transforms else {})
            return specimen.context, tools, digest_of(specimen.world), None, evidence
    folder = INCIDENTS / incident_id          # a development package: the same loader as a
    if LABEL.fullmatch(incident_id) and folder.is_dir():      # brought incident's
        return incident_from_dir(folder, max_tool_calls)
    return None


INCIDENT_FILES = ("incident.json", "world.sql")
# optional: the alerted metric as a series, which the runtime reads once from the world
# before the investigation — for the record and the page, never for the model
ALERT_SERIES = "alert_series.json"
MAX_SERIES_ROWS = 400


def alerted_series(folder: Path | None) -> dict | None:
    """The package's alerted series, read from its world through the read-only database,
    or None when the package declares none. ValueError when the declaration is malformed or
    its query is refused."""
    if folder is None or not (folder / ALERT_SERIES).is_file():
        return None
    spec = json.loads((folder / ALERT_SERIES).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not all(isinstance(spec.get(k), str)
                                              for k in ("metric", "unit", "query")):
        raise ValueError(f"{ALERT_SERIES} must hold metric, unit and query as text")
    world = ReadOnlyDatabase.in_memory((folder / "world.sql").read_text(encoding="utf-8"))
    read = world.query(spec["query"], max_rows=MAX_SERIES_ROWS)
    return {"metric": spec["metric"], "unit": spec["unit"], "query": spec["query"],
            "columns": list(read.columns), "rows": [list(row) for row in read.rows]}


def incident_from_dir(folder: Path, max_tool_calls: int | None = None):
    """An incident the operator brought: `incident.json` (what the investigator is told —
    the fields of IncidentContext) over `world.sql` (the build script of its world, as a
    specimen declares one), and any of the evidence bundles the tool layer knows — each a
    map file beside a directory of exactly the files it names. The same tool layer over the
    same kind of world; nothing else knows the difference. Returns the context, the tools,
    the world's digest, None (no recorded run) and the receipt's digests of the evidence the
    tools will show, by the receipt's names. ValueError names what is missing or malformed."""
    if not folder.is_dir() or not all((folder / name).is_file() for name in INCIDENT_FILES):
        raise ValueError(f"{folder} must hold {' and '.join(INCIDENT_FILES)}")
    told = json.loads((folder / "incident.json").read_text(encoding="utf-8"))
    paths = told.get("permitted_write_paths", []) if isinstance(told, dict) else None
    if not isinstance(told, dict) or not isinstance(paths, list) \
            or not all(isinstance(told.get(k), str) for k in ("incident_id", "alert", "as_of")) \
            or not all(isinstance(p, str) for p in paths):
        raise ValueError("incident.json must hold incident_id, alert and as_of as text, and "
                         "permitted_write_paths as a list of text")
    context = IncidentContext(incident_id=told["incident_id"], alert=told["alert"],
                              as_of=told["as_of"], permitted_write_paths=tuple(paths))
    world = (folder / "world.sql").read_text(encoding="utf-8")
    database = ReadOnlyDatabase.in_memory(world)      # ValueError when SQLite refuses the script
    evidence: dict[str, str] = {}
    declared_schemas = load_declared_schemas(folder)
    if declared_schemas:
        evidence["declared_schema_source"] = digest_of(canonical_json({
            table: declaration.source for table, declaration in declared_schemas.items()}))
        evidence["declared_schema_observation"] = digest_of(canonical_json({
            table: declaration.observation for table, declaration in declared_schemas.items()}))
    transform_sources = load_transform_sources(folder)
    readable_or_refused(context, transform_sources)
    if transform_sources:
        evidence["transforms"] = digest_of(canonical_json(transform_sources))
    notice_sources = load_notice_sources(folder)
    if notice_sources:
        evidence["notices"] = digest_of(canonical_json(notice_sources))
    change_histories = load_change_histories(folder)
    if change_histories:
        [(history_id, history)] = change_histories.items()
        evidence["change_history_source"] = digest_of(history.source)
        evidence["change_history_observation"] = digest_of(canonical_json(
            change_history_observation(history_id, history)))
    reconciliation_sources = load_reconciliation_sources(folder)
    if reconciliation_sources:
        evidence["reconciliation_source"] = digest_of(canonical_json(reconciliation_sources))
    tools = build_sql_tools(
        database,
        max_calls=max_tool_calls,
        declared_schemas=declared_schemas or None,
        transform_sources=transform_sources or None,
        notice_sources=notice_sources or None,
        change_histories=change_histories or None,
        reconciliation_sources=reconciliation_sources or None,
    )
    return context, tools, digest_of(world), None, evidence


def keep_incident(source: Path, folder: Path) -> None:
    """The operator's package copied into the run's folder byte for byte — the incident, the
    world and every evidence bundle present — as regular files only. The run is then loaded
    from this copy and never from `source` again, so what the model is shown, what the
    receipt binds and what the archive keeps are one read of one package."""
    def copy(path: Path, target: Path) -> None:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{path.name} must be a regular file")
        target.write_bytes(path.read_bytes())
    for name in INCIDENT_FILES:
        copy(source / name, folder / name)
    if (source / ALERT_SERIES).exists() or (source / ALERT_SERIES).is_symlink():
        copy(source / ALERT_SERIES, folder / ALERT_SERIES)
    for map_name, dir_name in EVIDENCE_BUNDLES:
        if (source / map_name).exists() or (source / map_name).is_symlink():
            copy(source / map_name, folder / map_name)
        source_dir = source / dir_name
        if source_dir.is_symlink() or (source_dir.exists() and not source_dir.is_dir()):
            raise ValueError(f"{dir_name} must be a directory")
        if source_dir.is_dir():
            (folder / dir_name).mkdir()
            for entry in sorted(source_dir.iterdir()):
                copy(entry, folder / dir_name / entry.name)


def release(folder: Path) -> None:
    """Give a claimed label back. Only before the run: no receipt was kept and no model was
    spoken to, so the folder holds nothing the archive must keep."""
    if (folder / "record.json").exists():
        raise ValueError(f"{folder} holds a record; a label with a record is never released")
    shutil.rmtree(folder)


def artefacts(context, world_digest: str,
              evidence: dict[str, str] | None = None) -> dict[str, str]:
    """What the run is about to expose to a model, by digest: the incident as handed over,
    the world behind the tools, the protocol the model is told, and each evidence bundle the
    tools will show, by the receipt's names. The evaluation authority's frozen identifiers
    join these when a run is scored."""
    handed = json.dumps({"incident_id": context.incident_id, "alert": context.alert,
                         "as_of": context.as_of,
                         "permitted_write_paths": list(context.permitted_write_paths)},
                        sort_keys=True)
    return {"incident": digest_of(handed), "world": world_digest,
            "protocol": digest_of(PROTOCOL), **(evidence or {})}


def configure(args, tool_names) -> tuple[dict[str, object], str, dict[str, object]]:
    """The configuration the receipt and the record carry, the reason the receipt states, and
    what a paid provider needs — from arguments every refusal has already passed."""
    tools = list(tool_names)
    if args.provider == "none":
        return ({"provider": "none", "model": None, "arm": args.arm, "tools": tools},
                "a control arm, always-escalate: no model, no tools, nothing is spent", {})
    if args.provider == "scripted":
        return ({"provider": "scripted", "model": None, "tools": tools,
                 "max_tool_calls": args.max_tool_calls},
                "scripted replay of a recorded run: no model, nothing is spent", {})
    bounds = {"arm": args.arm, "max_turns": args.max_turns,
              "max_tool_calls": args.max_tool_calls,
              "max_model_requests": args.max_model_requests,
              "max_wall_clock_seconds": args.max_wall_clock_seconds, "timeout_s": TIMEOUT_S}
    if args.provider == "local":
        return ({"provider": "local", "model": args.model, "endpoint": args.endpoint,
                 "served_as": args.served_as, **bounds, "tools": tools,
                 "execution_mode": "live", "cost_basis": "local endpoint, no price"},
                f"a local model, {args.model}, at {args.endpoint}: no nominal price, "
                f"nothing is spent; requested from {args.requested_from}", {})
    price = PRICES[args.model]
    configuration = {"provider": "openai", "model": args.model, "endpoint": args.endpoint,
                     **bounds, "max_tokens": args.max_tokens,
                     "max_cost_usd": args.max_cost_usd,
                     **({"temperature": 0} if args.reasoning_effort is None
                        else {"reasoning_effort": args.reasoning_effort}),
                     "credential": "OPENAI_API_KEY (environment)",
                     "price_table": price.table, "tools": tools,
                     "execution_mode": "live",
                     "cost_basis": (f"lower bound: provider-reported usage at nominal "
                                    f"{args.model} prices, {price.table}"),
                     "cap_basis": ("hard by admission: a request is sent only if the exact "
                                   "worst case spent so far plus its own reserve — every byte "
                                   "of the messages as a token at the input rate, max_tokens at "
                                   "the output rate, sent as max_completion_tokens — stays "
                                   "within max_cost_usd; premise: the "
                                   f"endpoint honours max_tokens and bills by "
                                   f"{price.tokenizer}, a byte-level BPE; a bill above its "
                                   "reserve ends the run as the provider's failure")}
    reason = (f"a paid provider, {args.model} at {args.endpoint}: up to "
              f"${args.max_cost_usd:.2f} at nominal prices ({price.table}), a hard cap — no "
              f"request is sent whose worst case would cross it; requested from "
              f"{args.requested_from}; permitted by the operator running this process")
    paid = {"credential": os.environ["OPENAI_API_KEY"], "max_tokens": args.max_tokens,
            "price": price, "max_cost_usd": args.max_cost_usd,
            "reasoning_effort": args.reasoning_effort}
    return configuration, reason, paid


def refused_bounds(max_turns: int, max_tool_calls: int, max_model_requests: int,
                   max_wall_clock_seconds: float) -> str | None:
    """Why the run's bounds are not bounds, or None: each must be above zero, the wall
    clock finite. A bound of zero or less would look like one and bind nothing."""
    if any(v <= 0 for v in (max_turns, max_tool_calls, max_model_requests)):
        return ("--max-turns, --max-tool-calls and --max-model-requests must each be a whole "
                "number above zero")
    if not (math.isfinite(max_wall_clock_seconds) and max_wall_clock_seconds > 0):
        return "--max-wall-clock-seconds must be a finite number of seconds above zero"
    return None


def refused_paid(model: str | None, max_cost_usd: float, endpoint: str,
                 served_as: str | None, max_tokens: int) -> str | None:
    """Why a paid run may not start, or None. Every precondition of spending, checked
    before anything irreversible — a label claimed, a port bound (inherited D6, D7): a priced
    model, billed by a tokenizer the input bound is conservative for, that is the model on
    the wire; a finite cap; a completion bound above zero, since every reserve prices it in
    full; an endpoint that carries no secret; and the credential in the environment. The
    demo server asks the same question when it starts, so the page never learns it."""
    if model not in PRICES:
        return (f"--provider openai needs --model with a nominal price in reporting/ledger.py; "
                f"priced: {', '.join(sorted(PRICES))}")
    if PRICES[model].tokenizer not in BYTE_LEVEL_TOKENIZERS:
        return (f"--model {model} bills by {PRICES[model].tokenizer}, which is not known to be "
                "byte-level: the cap's input bound counts bytes and would not be a bound")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        return "--max-tokens must be a whole number above zero: every reserve prices it in full"
    if served_as not in (None, model):
        return (f"--served-as {served_as!r}: a paid run is billed by the name on the wire and "
                f"priced by --model; they must be the same — --served-as is for local endpoints")
    if not (math.isfinite(max_cost_usd) and max_cost_usd > 0):
        return "--max-cost-usd must be a finite amount above zero: a paid run needs a cap"
    if not endpoint_may_carry_a_credential(endpoint):
        return (f"--endpoint {endpoint!r}: a paid endpoint is https (unless on this machine) and "
                "carries no query string or credentials — the key comes from OPENAI_API_KEY")
    if not os.environ.get("OPENAI_API_KEY"):
        return ("OPENAI_API_KEY is not set; a paid run takes its credential from the "
                "environment and nowhere else")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.runtime", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--incident", help="the incident id to investigate")
    what.add_argument("--incident-dir", metavar="DIR",
                      help="a folder holding incident.json and world.sql — an operator's own "
                           "incident over their own data; both are kept beside the record")
    parser.add_argument("--arm", default="full", choices=list(ARMS),
                        help="full: the investigator with the tool surface; alert-only: the same "
                             "model and protocol with no tool, so it decides from the alert; "
                             "always-escalate: no model, ESCALATE every time (--provider none)")
    parser.add_argument("--provider", required=True,
                        choices=["scripted", "local", "openai", "none"],
                        help="scripted: a scripted investigator and validator over the real "
                             "tool layer — no model, no cost. local: A's loop with a model "
                             "behind a local OpenAI-compatible endpoint (SPIKE). openai: the "
                             "same loop against a paid endpoint, credential from OPENAI_API_KEY")
    parser.add_argument("--endpoint", default=None,
                        help="the OpenAI-compatible base URL (default: Ollama's for local, "
                             "https://api.openai.com/v1 for openai)")
    parser.add_argument("--model", help="the model's identity, as the record keeps it")
    parser.add_argument("--max-cost-usd", type=float, default=0.25,
                        help="openai only: the hard spend cap — a request whose worst case "
                             "would cross it is not sent (default 0.25)")
    parser.add_argument("--max-tokens", type=int, default=512,
                        help="openai only: the completion bound per request (default 512); "
                             "priced in full in every request's reserve")
    parser.add_argument("--reasoning-effort", choices=REASONING_EFFORTS,
                        help="openai only, a reasoning model: sent as given in place of "
                             "temperature; its reasoning tokens count inside --max-tokens")
    parser.add_argument("--served-as", metavar="NAME",
                        help="local only: the name the endpoint wants in requests when it differs "
                             "from --model (mlx-lm's server: default_model)")
    parser.add_argument("--max-turns", type=int, default=12,
                        help="the investigator's model-turn bound (default 12)")
    parser.add_argument("--max-tool-calls", type=int, default=30,
                        help="the executor's budget: tool calls past it are DENIED, and the "
                             "investigator may still decide (default 30)")
    parser.add_argument("--max-model-requests", type=int, default=None,
                        help="the provider's request bound, a resource of its own beside "
                             "--max-turns (default: as many as --max-turns; a lower value is "
                             "a stricter bound, respected)")
    parser.add_argument("--max-wall-clock-seconds", type=float, default=600.0,
                        help="the run's deadline from the investigator's first request: no "
                             "request is sent past it, and one in flight is cut at it "
                             "(default 600)")
    parser.add_argument("--label", help="archive label (default: <incident>-<UTC time>); "
                                        "a label names one run forever")
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="archive root (default: 01_data/runs)")
    parser.add_argument("--requested-from", default="the command line", metavar="TEXT",
                        help="where this run was asked for, as the receipt's reason records it; "
                             "the demo server names the page and the ceilings it checked")
    parser.add_argument("--no-report", action="store_true",
                        help="archive only; do not print the report")
    args = parser.parse_args(argv)

    if args.max_model_requests is None:   # omitted: one request per turn; given: as given
        args.max_model_requests = args.max_turns
    why = refused_bounds(args.max_turns, args.max_tool_calls, args.max_model_requests,
                         args.max_wall_clock_seconds)
    if why:
        print(why)
        return 2
    tool_cap = args.max_tool_calls
    if args.incident_dir:
        source = Path(args.incident_dir)
        try:                                        # refused before any label is claimed
            found = incident_from_dir(source, tool_cap)
        except (ValueError, json.JSONDecodeError) as bad:       # not an incident folder
            print(f"not an incident: {bad}")
            return 2
    else:
        try:
            found = incident(args.incident, tool_cap)
        except ValueError as bad:                       # a path it permits but cannot show
            print(f"not an incident: {bad}")
            return 2
        if found is None:
            known = [load()[0].incident_id, *(s.context.incident_id for s in SPECIMENS),
                     *sorted(p.name for p in INCIDENTS.glob("*") if p.is_dir())]
            print(f"no such incident {args.incident!r}; known: {', '.join(known)}")
            return 2
    context, tools, world_digest, recorded, evidence = found
    if (args.provider == "none") != (args.arm == "always-escalate"):
        print("--arm always-escalate runs with --provider none, and --provider none only with it: "
              "the floor of the controls asks no model")
        return 2
    tools = armed(args.arm, tools, tool_cap)
    if args.endpoint is None:
        args.endpoint = ("https://api.openai.com/v1" if args.provider == "openai"
                         else "http://127.0.0.1:11434/v1")
    if args.provider == "scripted" and recorded is None:
        print(f"the scripted provider replays the walkthrough only; "
              f"{context.incident_id!r} has no recorded run — use --provider local, or "
              "python -m adii.examples.specimens")
        return 2
    if args.provider == "local" and not args.model:
        print("--provider local needs --model <id the endpoint serves>")
        return 2
    if args.reasoning_effort and args.provider != "openai":
        print("--reasoning-effort is a paid reasoning model's setting: --provider openai only")
        return 2
    if args.provider == "openai":
        try:
            load_env_local()
        except ValueError as bad:                   # a file that is not NAME=value lines
            print(bad)
            return 2
        why = refused_paid(args.model, args.max_cost_usd, args.endpoint, args.served_as,
                           args.max_tokens)
        if why:
            print(why)
            return 2
        # The first request's reserve is known now — the protocol, the incident, the tools —
        # and a cap it alone would cross is refused here, not as a run of zero requests.
        first_input = input_tokens_upper_bound(initial_messages(context, tools.advertised()))
        first = reserve_for(first_input, PRICES[args.model], args.max_tokens)
        if first > Decimal(repr(args.max_cost_usd)):
            print(f"--max-cost-usd {args.max_cost_usd}: the first request alone reserves "
                  f"${first:f} (at most {first_input} input tokens, {args.max_tokens} output) "
                  "and would not be sent; raise the cap or lower --max-tokens")
            return 2
    label = args.label or f"{context.incident_id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    archive = Path(args.archive)
    try:                          # every precondition that needs no I/O has passed: claim the label
        folder = reserve(archive, label)
    except ValueError as bad:                # the label is not one the archive can hold
        print(f"not archived: {bad}")
        return 2
    except FileExistsError as taken:
        print(f"not archived: {taken}")
        return 1
    try:
        if args.incident_dir:
            # The operator's package is copied into the run's folder first and the run is
            # loaded from that copy: the model's view, the receipt and the archive are one
            # read of one package, whatever happens to the operator's folder from here on.
            keep_incident(source, folder)
            context, tools, world_digest, _, evidence = incident_from_dir(folder, tool_cap)
            tools = armed(args.arm, tools, tool_cap)
        alert = alerted_series(folder if args.incident_dir else
                               INCIDENTS / args.incident if LABEL.fullmatch(args.incident)
                               else None)
        configuration, reason, paid = configure(args, tools.names)
        # The receipt, before anything is spent: written and flushed, kept on every path.
        write_receipt(folder, label=label, artefacts=artefacts(context, world_digest, evidence),
                      configuration=configuration, reason=reason)
        # Every event lands in trace.jsonl the moment it happens: the live view of the run,
        # and what a killed run leaves behind. The record written at the end is the authority.
        recorder = Recorder(sink=folder / "trace.jsonl")
    except (ValueError, json.JSONDecodeError, OSError) as bad:
        release(folder)      # nothing spent, no model spoken to
        print(f"not archived: {bad}")
        return 2
    if paid:
        paid["receipt"] = folder / RECEIPT     # the provider refuses to exist without it
    if args.provider == "none":
        investigator, validator = AlwaysEscalate(), None     # it never proposes a repair
    elif args.provider == "scripted":
        investigator, _, validator = replay(recorded)
    else:
        from .live import LoopInvestigator, ValidatorOnLivePath  # the spike
        investigator = LoopInvestigator(endpoint=args.endpoint, model=args.model,
                                        max_turns=args.max_turns, recorder=recorder,
                                        served_as=args.served_as,
                                        max_model_requests=args.max_model_requests,
                                        max_wall_clock_s=args.max_wall_clock_seconds, **paid)
        validator = ValidatorOnLivePath()

    record = run_incident(label, context, investigator, tools, validator,
                          configuration=configuration, recorder=recorder, alert=alert)
    if paid:
        # The cost is the ledger's lower bound over the trace — proved usage at nominal
        # prices; a request without usage is counted, not priced, and the renderers say so.
        ledger = aggregate(record.trace, paid["price"])
        record = replace(record, api_cost_usd=ledger.lower_bound_usd)
    print(f"archived {write_record(record, archive)}")
    if not args.no_report:
        print(render_run(record))
    if record.termination == "submitted":
        return 0
    print(f"the run ended without a decision — {record.termination}: {record.detail}")
    return 4 if record.termination == "infrastructure_failure" else 3


if __name__ == "__main__":
    raise SystemExit(main())
