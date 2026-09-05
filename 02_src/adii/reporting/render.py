"""The telemetry layer's first build: turn a run into something a human can read.

The report has to be able to show a success, a false repair, a correct abstention, and a
rejected repair with equal honesty. A reporting layer that only looks good when the agent
was right is not evidence, it is marketing.
"""
from __future__ import annotations

from ..contracts import Disposition, IncidentContext, InvestigationRun

_RULE = "-" * 78


def _wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(indent + line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(indent + line)
    return "\n".join(lines)


def render_run(context: IncidentContext, run: InvestigationRun) -> str:
    decision = run.decision
    out = [_RULE, f"ADII INVESTIGATION REPORT   {context.incident_id}", _RULE, "",
           "ALERT", _wrap(context.alert), "", f"  evaluated as of {context.as_of}", "",
           "EVIDENCE GATHERED"]

    for event in run.trace:
        if event.kind == "tool_call":
            payload = event.payload
            out.append(f"  -> {payload['name']}({_arguments(payload['arguments'])})")
        elif event.kind == "tool_result":
            payload = event.payload
            marker = "   " if payload["status"] == "OK" else " ! "
            out.append(f"  <-{marker}[{payload['status']}] {_summary(payload['content'])}")
    if not any(event.kind == "tool_call" for event in run.trace):
        out.append("  (none — the investigator decided without looking)")

    out += ["", "DECISION", f"  {decision.disposition.value}", "",
            f"  root cause: {decision.root_cause_id or '(none named)'}",
            _wrap(decision.root_cause_summary)]

    if decision.disposition is Disposition.REPAIR:
        out += ["", "PROPOSED REPAIR", f"  repair_id: {decision.repair_id}"]
        for path, body in decision.patch.items():
            out.append(f"  --- {path}")
            out += [f"      {line}" for line in body.rstrip("\n").splitlines()]
        verdict = run.validation
        out += ["", "INDEPENDENT VALIDATION",
                f"  {'ACCEPTED' if verdict.accepted else 'REJECTED'}"
                "   (decided by the validator, never by the agent)",
                _wrap(verdict.report),
                f"  checks: {', '.join(verdict.checks_run) or '(none recorded)'}"]
    else:
        out += ["", "INDEPENDENT VALIDATION", "  not applicable — no repair was proposed"]

    out += ["", "COST OF THIS RUN",
            f"  tool calls {run.tool_calls}   model turns {run.model_turns}"
            f"   ${run.api_cost_usd:.4f}   {run.latency_ms} ms", _RULE]
    return "\n".join(out) + "\n"


def _arguments(arguments: object) -> str:
    if not isinstance(arguments, dict) or not arguments:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in arguments.items())


def _summary(content: object) -> str:
    if not isinstance(content, dict):
        return str(content)
    if "error" in content:
        return str(content["error"])
    if "rows" in content:
        rows = content["rows"]
        return f"{len(rows)} row(s), first: {rows[0] if rows else '-'}"
    if "columns" in content:
        return f"{content.get('table', '?')}: {', '.join(map(str, content['columns']))}"
    return ", ".join(f"{k}={v}" for k, v in list(content.items())[:3])
