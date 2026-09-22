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
    "infrastructure_failure": ("INFRASTRUCTURE FAILURE",
                               "not the model's: the runtime's or the provider's"),
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


def _cost(record: RunRecord) -> str:
    """A paid run's cost is the ledger's lower bound, and says how many requests it could
    not price; a run with no paid provider spent nothing, and says that rather than $0."""
    if record.configuration.get("provider") != "openai":
        return (f"${record.api_cost_usd:.4f}" if record.api_cost_usd
                else "nothing spent (no paid provider)")
    unpriced = sum(1 for e in record.trace if e.kind == "model_requested") - sum(
        1 for e in record.trace if e.kind == "model_responded"
        and isinstance(e.payload.get("usage"), dict)
        and isinstance(e.payload["usage"].get("prompt_tokens"), int))
    bound = f"at least ${record.api_cost_usd:.4f}"
    return bound + (f" ({unpriced} request(s) without usage)" if unpriced else "")


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
        elif event.kind == "decision_rejected":
            out.append(f"  !! submission rejected ({payload.get('rejection_class', 'rejected')}): "
                       f"{payload.get('reason', '')}")
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
                _wrap(decision.root_cause_summary),
                # every cited id was minted by the tool layer in this run: the record refuses
                # any other. Cited is not warranted — that is the evaluation's question.
                f"  cites: {', '.join(decision.evidence_refs) or 'nothing'}"]
        if decision.disposition is Disposition.REPAIR:
            out += ["", "PROPOSED REPAIR", f"  repair_id: {decision.repair_id}"]
            for path, body in decision.patch.items():
                out.append(f"  --- {path}")
                out += [f"      {line}" for line in body.rstrip("\n").splitlines()]
            out += ["", "AUTHORIZATION", *_authorization(record)]
            verdict = record.validation
            # the contract's one derivation: accepted; rejected after checks; not checkable
            # (no world to rebuild, said in structure); or the legacy placeholder
            state = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED",
                     "NOT_CHECKABLE": "NOT CHECKABLE", "UNCHECKED": "UNCHECKED"}[verdict.state]
            out += ["", "INDEPENDENT VALIDATION",
                    f"  {state}   (decided by the validator, never by the agent)",
                    _wrap(verdict.report),
                    f"  checks: {', '.join(verdict.checks_run) or '(none recorded)'}",
                    "", "ADMISSION", *_admission(record)]
        else:
            out += ["", "INDEPENDENT VALIDATION", "  not applicable — no repair was proposed"]

    out += ["", "COST OF THIS RUN",
            f"  tool calls {record.tool_calls}   model turns {record.model_turns}"
            f"   {_cost(record)}   {record.latency_ms} ms", _RULE]
    return "\n".join(out) + "\n"


def _authorization(record: RunRecord) -> list[str]:
    """The runtime's fact about the targets, in its own terms: never a word about whether the
    patch works. A record from before the fact existed says so rather than implying one."""
    fact = record.authorization
    if fact is None:
        return ["  not recorded   (a record from before the runtime established this fact)"]
    if fact.authorized:
        return ["  AUTHORIZED   (the runtime's: every target is a path the incident permitted)",
                f"  checked: {', '.join(fact.checked_paths)}"]
    return [f"  DENIED   (the runtime's: {fact.reason_code}; a patch is authorized whole or "
            "not at all)",
            f"  checked: {', '.join(fact.checked_paths)}   denied: {', '.join(fact.denied_paths)}"]


def _admission(record: RunRecord) -> list[str]:
    """Derived from the two facts above by the record's own rule, stored nowhere; the reasons
    are the facts themselves. Nothing was executed in any case."""
    if record.admissible:
        return ["  admissible   (authorized and accepted; nothing was executed)"]
    fact, verdict = record.authorization, record.validation
    why = []
    if fact is None:
        why.append("no authorization fact was recorded")
    elif not fact.authorized:
        why.append(f"authorization denied: {fact.reason_code}")
    if verdict.state != "ACCEPT":
        why.append({"REJECT": "the repair was not accepted",
                    "NOT_CHECKABLE": "validation was not established",
                    "UNCHECKED": "no validator checked the repair"}[verdict.state])
    return [f"  not admissible   ({'; '.join(why)}; nothing was executed)"]


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
