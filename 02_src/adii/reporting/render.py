"""The report: one run, from its record, readable by a human.

It has to show a success, a rejected repair, a model failure, a bound and an infrastructure
failure with equal honesty, each labelled in its own terms (inherited D11). A report that
only reads well when the agent was right is not evidence, it is marketing. Every call is
paired with the result the model saw, in order, and a call the run ended on is shown as
unanswered — never "pending", which is the wrong word for a call that ended the run.
"""
from __future__ import annotations

from ..contracts import Disposition
from .record import RunRecord

_RULE = "-" * 78

# A run that ended without a decision, each way in its own terms. The classification is the
# loop's — or the runtime's, for a defect of ours — and the report repeats it, adding nothing.
ENDED = {
    "model_failure": ("MODEL FAILURE", "the model's failure, filed as the model's"),
    "bound_hit": ("BOUND HIT", "the loop stopped at a bound it set"),
    "infrastructure_failure": ("INFRASTRUCTURE FAILURE", "our defect, not the model's"),
}


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


def render_run(record: RunRecord) -> str:
    context, decision, trace = record.context, record.decision, record.trace
    out = [_RULE, f"ADII INVESTIGATION REPORT   {context.incident_id}", _RULE, "",
           "ALERT", _wrap(context.alert), "", f"  evaluated as of {context.as_of}", "",
           "EVIDENCE GATHERED"]

    answered = {e.payload["call_id"] for e in trace if e.kind == "tool_result"}
    for event in trace:
        payload = event.payload
        if event.kind == "tool_call":
            out.append(f"  -> {payload['name']}({_arguments(payload['arguments'])})")
            if payload["call_id"] not in answered:
                out.append("  <- (unanswered: the run ended here)")
        elif event.kind == "tool_result":
            marker = "   " if payload["status"] == "OK" else " ! "
            out.append(f"  <-{marker}[{payload['status']}] {_summary(payload['content'])}")
    if not any(event.kind == "tool_call" for event in trace):
        out.append("  (none — the investigator decided without looking)" if decision
                   else "  (none — the run ended before any call)")

    if decision is None:
        name, meaning = ENDED[record.termination]
        out += ["", f"RUN ENDED — {name}   ({meaning})", _wrap(record.detail), "",
                "DECISION", "  none — the run ended before the investigator committed", "",
                "INDEPENDENT VALIDATION", "  never reached — no decision was submitted"]
    else:
        out += ["", "DECISION", f"  {decision.disposition.value}", "",
                f"  root cause: {decision.root_cause_id or '(none named)'}",
                _wrap(decision.root_cause_summary)]
        if decision.disposition is Disposition.REPAIR:
            out += ["", "PROPOSED REPAIR", f"  repair_id: {decision.repair_id}"]
            for path, body in decision.patch.items():
                out.append(f"  --- {path}")
                out += [f"      {line}" for line in body.rstrip("\n").splitlines()]
            verdict = record.validation
            # three states the record distinguishes: accepted; rejected after checks; and
            # not checked at all — a placeholder verdict, which is not a finding
            state = ("ACCEPTED" if verdict.accepted else "REJECTED" if verdict.checks_run
                     else "UNCHECKED")
            out += ["", "INDEPENDENT VALIDATION",
                    f"  {state}   (decided by the validator, never by the agent)",
                    _wrap(verdict.report),
                    f"  checks: {', '.join(verdict.checks_run) or '(none recorded)'}"]
        else:
            out += ["", "INDEPENDENT VALIDATION", "  not applicable — no repair was proposed"]

    out += ["", "COST OF THIS RUN",
            f"  tool calls {record.tool_calls}   model turns {record.model_turns}"
            f"   ${record.api_cost_usd:.4f}   {record.latency_ms} ms", _RULE]
    return "\n".join(out) + "\n"


def _arguments(arguments: object) -> str:
    if not isinstance(arguments, dict) or not arguments:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in arguments.items())


def _summary(content: object) -> str:
    if not isinstance(content, dict):
        return str(content)
    if "error" in content:
        text = str(content["error"])
    elif "rows" in content:
        rows = content["rows"]
        text = f"{len(rows)} row(s), first: {rows[0] if rows else '-'}"
    elif "columns" in content:
        text = f"{content.get('table', '?')}: {', '.join(map(str, content['columns']))}"
    else:
        text = ", ".join(f"{k}={v}" for k, v in list(content.items())[:3])
    evidence = content.get("evidence_id")          # minted by the tool layer, when it did
    return f"{text}   {evidence}" if evidence else text
