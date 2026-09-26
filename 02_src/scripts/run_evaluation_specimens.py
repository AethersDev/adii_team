#!/usr/bin/env python
"""Benchmark 3 models against ./adii_case_specimens_data/, via OpenRouter.

    python run_evaluation_specimens.py

This case data comes from `case_specimens.py`, a set of 10 incidents authored in the
same shape as adii_team's own `02_src/adii/examples/specimens.py` -- one Specimen per
incident, `IncidentContext` with exactly the four official fields, a `world` built as
plain SQL, and runs using only the two tools the tool layer always provides
(`get_schema`, `run_sql`). Every run in it was executed end to end through the real
ADII runtime (`adii.runtime.run.run_incident`) with zero failures, and every case's
claim was independently re-derived from its own data by `check_specimens.py` (not
taken on the author's word) -- all checks passed. See case_specimens.py's own
docstring for what each incident is built to measure.

Reads every case under adii_case_specimens_data/cases/ (incident.json + data/*.csv,
exported from case_specimens.py's SQL worlds via the real ReadOnlyDatabase), builds
each case's world through ADII's own tool layer (adii_team/02_src/adii/tools), and
drives a real tool-calling agent loop against each of 3 models, 3 runs per case per
model (10 cases x 3 runs x 3 models = 90 runs). Each run's final JSON decision block
is scored against adii_case_specimens_data/evaluation/ground_truth.jsonl. Raw output
goes to evaluation_specimens_raw_results.json; a comparative summary prints at the end.

Requires OPENAI_API_KEY (an OpenRouter key, sk-or-v1-...) in the environment or in
adii_team/.env.local -- read the same way adii_team's own runtime reads it.

What this still is not: an ADII-certified evaluation. The agent loop, the system
prompt and the scoring here are custom, written for this benchmark, not adii_team's
own runtime or evaluation authority -- only the tool layer and the case data are the
genuine article. Ground truth is case_specimens.py's own authored decision (the last
run's InvestigationDecision per specimen); it is evidence-grounded and independently
re-derivable, but it was not produced or reviewed by the adii_team project itself.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent  # the workspace beside the repo: case data, incidents and results stay out of it
CASE_DATA = ROOT / "adii_case_specimens_data"
CASES_DIR = CASE_DATA / "cases"
EVAL_DIR = CASE_DATA / "evaluation"
ADII_SRC = REPO / "02_src"

sys.path.insert(0, str(ADII_SRC))

from adii.tools import ReadOnlyDatabase  # noqa: E402
from adii.tools.executor import ToolExecutor  # noqa: E402
from adii.tools.sql_tools import DEFAULT_MAX_ROWS, GET_SCHEMA, RUN_SQL  # noqa: E402
from adii.tools.user_world import world_from_files  # noqa: E402
from adii.provider.credential import load_env_local  # noqa: E402

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = {
    "Model_A": "openai/gpt-4o-mini",
    "Model_B": "openai/gpt-4.1-mini",
    "Model_C": "anthropic/claude-haiku-4.5",
}

RUNS_PER_CASE = 3
MAX_TOOL_TURNS = 12
TEMPERATURE = 0
MAX_TOKENS = 1200
REQUEST_TIMEOUT_S = 90
RETRIES = 4
IN_FLIGHT_BACKOFF_S = 125  # OpenRouter's in_flight_budget_exhausted names its own wait via
                           # the response's Retry-After header (observed: 120s); this is that
                           # plus a small margin, not the short exponential backoff for 429/5xx

SYSTEM_PROMPT = """You are ADII (Autonomous Data Incident Investigator), an AI agent specialized in investigating data incidents, analyzing logs, inspecting system metrics, and auditing database behaviors.

### YOUR GOAL
Investigate the provided data incident using ONLY the available controlled tools, identify the root cause, and output a final structured decision.

### OPERATIONAL RULES
1. Tool-Based Investigation: Do NOT guess or make assumptions. Use the provided tools to inspect logs, query datasets, check configurations, and review system policies.
2. Strict Evidence Gathering: Every conclusion must be backed by explicit evidence retrieved via tool calls.
3. No Unsafe Actions: You do NOT execute fixes directly. You only investigate and propose/classify decisions.

### DECISION CATEGORIES
Your investigation MUST culminate in choosing exactly ONE of the following decisions:
- NO_REPAIR: Use when the reported anomaly is expected, non-erroneous, or aligns with system policies or scheduled events.
- REPAIR: Use when there is a clear, deterministic, and safe technical issue with a known fix that can be safely proposed.
- ESCALATE: Use when the issue involves critical security risks, irrecoverable data loss, financial/ledger discrepancy, or severe ambiguity requiring human intervention.

### OUTPUT FORMAT
Your final response MUST end with a JSON block in the following exact format:
```json
{
  "investigation_summary": "<Brief summary of what was found across the tools used>",
  "root_cause": "<Clear explanation of the root cause>",
  "decision": "NO_REPAIR" | "REPAIR" | "ESCALATE",
  "proposed_fix": "<Exact fix detail if decision is REPAIR, null otherwise/script/query>",
  "evidence": ["<Key reference 1>", "<Key reference 2>"]
}
```"""


# ── credential ────────────────────────────────────────────────────────────────────────

def api_key() -> str:
    load_env_local(root=REPO)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(
            "OPENAI_API_KEY not set. Put an OpenRouter key (sk-or-v1-...) in "
            "adii_team/.env.local as OPENAI_API_KEY=... or export it in the shell.")
    return key


# ── case loading ─────────────────────────────────────────────────────────────────────

@dataclass
class Case:
    case_id: str
    incident_id: str
    alert: str
    as_of: str
    permitted_write_paths: list[str]
    build_script: str


def load_tools_manifest() -> list[dict[str, object]]:
    manifest = json.loads((CASES_DIR / "tools_manifest.json").read_text(encoding="utf-8"))
    return [{"type": "function", "function": t} for t in manifest["tools"]]


def load_cases() -> list[Case]:
    cases: list[Case] = []
    for folder in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        incident = json.loads((folder / "incident.json").read_text(encoding="utf-8"))
        files = []
        for csv_path in sorted((folder / "data").glob("*.csv")):
            files.append((csv_path.name, csv_path.read_text(encoding="utf-8")))
        build_script = world_from_files(files)
        cases.append(Case(
            case_id=incident["case_id"], incident_id=incident["incident_id"],
            alert=incident["alert"], as_of=incident["as_of"],
            permitted_write_paths=incident["permitted_write_paths"],
            build_script=build_script))
    return cases


def load_ground_truth() -> dict[str, dict[str, object]]:
    truth = {}
    with (EVAL_DIR / "ground_truth.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            truth[row["case_id"]] = row
    return truth


def build_tool_executor(case: Case) -> ToolExecutor:
    """A fresh, real ADII tool layer over this case's world: `get_schema` and `run_sql`,
    exactly as adii_team's own runtime builds them, so grounding is genuine, not mocked."""
    database = ReadOnlyDatabase.in_memory(case.build_script)
    executor = ToolExecutor(max_calls=(MAX_TOOL_TURNS + 2) * 4)  # a turn may carry several calls

    def get_schema(table: str | None = None) -> dict[str, object]:
        if table is None:
            return {"tables": [
                {"name": t, "columns": list(database.schema(t).columns)}
                for t in database.tables()]}
        schema = database.schema(table)
        return {"name": schema.name, "columns": list(schema.columns), "ddl": schema.ddl}

    def run_sql(query: str) -> dict[str, object]:
        result = database.query(query, max_rows=DEFAULT_MAX_ROWS)
        return {"columns": list(result.columns),
                "rows": [list(r) for r in result.rows], "truncated": result.truncated}

    executor.register(GET_SCHEMA, get_schema)
    executor.register(RUN_SQL, run_sql)
    return executor


# ── OpenRouter call ──────────────────────────────────────────────────────────────────

def call_openrouter(key: str, model: str, messages: list[dict[str, object]],
                    tools: list[dict[str, object]]) -> dict[str, object]:
    body = json.dumps({
        "model": model, "messages": messages, "tools": tools, "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://github.com/adii-benchmark",
                "X-Title": "ADII benchmark"})
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as failed:
            detail = failed.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {failed.code}: {detail[:500]}")
            in_flight = failed.code == 402 and "in_flight_budget_exhausted" in detail
            if attempt < RETRIES and (failed.code in (429, 500, 502, 503, 504) or in_flight):
                if in_flight:
                    # The response itself names the wait via Retry-After (observed: 120s) or
                    # its own metadata.headers.Retry-After when the outer header is stripped;
                    # trust it over a guess, with IN_FLIGHT_BACKOFF_S as the floor and fallback.
                    wait = IN_FLIGHT_BACKOFF_S
                    header_value = failed.headers.get("Retry-After") if failed.headers else None
                    if header_value is None:
                        try:
                            header_value = json.loads(detail)["error"]["metadata"]["headers"] \
                                .get("Retry-After")
                        except (ValueError, KeyError, TypeError):
                            header_value = None
                    if header_value is not None:
                        try:
                            wait = max(wait, float(header_value) + 5)
                        except ValueError:
                            pass
                else:
                    wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise last_error
        except (urllib.error.URLError, TimeoutError) as failed:
            last_error = failed
            if attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue
    raise last_error  # type: ignore[misc]


# ── the agent loop ───────────────────────────────────────────────────────────────────

@dataclass
class RunOutcome:
    case_id: str
    incident_id: str
    model_key: str
    model_id: str
    run_index: int
    turns: int
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    final_text: str | None = None
    decision_json: dict[str, object] | None = None
    error: str | None = None


def extract_decision(text: str) -> dict[str, object] | None:
    """The decision object at the end of the model's message: the last fenced ```json ...
    ``` block if there is one (models sometimes narrate before it, so the last fence wins);
    otherwise the last top-level {...} brace span in the text, since a model that follows
    the "end with a JSON block" instruction without fencing it still produces valid JSON,
    just unmarked. None if neither parses."""
    fence = "```json"
    idx = text.rfind(fence)
    body_start = idx + len(fence) if idx != -1 else None
    if body_start is None:
        idx = text.rfind("```")
        if idx != -1:
            body_start = idx + 3
    if body_start is not None:
        end = text.find("```", body_start)
        if end != -1:
            block = text[body_start:end].strip()
            try:
                parsed = json.loads(block)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
    # No fenced block parsed: fall back to the last balanced {...} span in the text.
    end_brace = text.rfind("}")
    while end_brace != -1:
        depth = 0
        for start_brace in range(end_brace, -1, -1):
            ch = text[start_brace]
            if ch == "}":
                depth += 1
            elif ch == "{":
                depth -= 1
                if depth == 0:
                    candidate = text[start_brace:end_brace + 1]
                    try:
                        parsed = json.loads(candidate)
                    except ValueError:
                        break
                    if isinstance(parsed, dict) and "decision" in parsed:
                        return parsed
                    break
        end_brace = text.rfind("}", 0, end_brace)
    return None


def run_one(key: str, case: Case, model_key: str, model_id: str, run_index: int,
           tools_schema: list[dict[str, object]]) -> RunOutcome:
    outcome = RunOutcome(case_id=case.case_id, incident_id=case.incident_id,
                         model_key=model_key, model_id=model_id, run_index=run_index, turns=0)
    executor = build_tool_executor(case)
    user_message = json.dumps({
        "incident_id": case.incident_id, "alert": case.alert, "as_of": case.as_of,
        "permitted_write_paths": case.permitted_write_paths}, indent=1)
    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for turn in range(1, MAX_TOOL_TURNS + 1):
        outcome.turns = turn
        try:
            reply = call_openrouter(key, model_id, messages, tools_schema)
        except Exception as failed:  # noqa: BLE001 - recorded, not re-raised, so the sweep continues
            outcome.error = f"provider error: {failed}"
            return outcome
        choices = reply.get("choices") or []
        if not choices:
            outcome.error = f"no choices in reply: {json.dumps(reply)[:500]}"
            return outcome
        message = choices[0].get("message") or {}
        messages.append({k: v for k, v in message.items() if k in ("role", "content", "tool_calls")})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            text = message.get("content") or ""
            outcome.final_text = text
            outcome.decision_json = extract_decision(text)
            return outcome

        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name", "")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            from adii.contracts import ToolCall  # local import: keeps module import order tidy
            result = executor.execute(ToolCall(call_id=call.get("id", name), name=name,
                                               arguments=arguments))
            outcome.tool_calls.append({"name": name, "arguments": arguments,
                                       "status": result.status, "content": result.content})
            messages.append({
                "role": "tool", "tool_call_id": call.get("id", name),
                "content": json.dumps({"status": result.status, "content": result.content})})

    outcome.error = f"reached MAX_TOOL_TURNS ({MAX_TOOL_TURNS}) without a final decision"
    return outcome


# ── scoring ──────────────────────────────────────────────────────────────────────────

def score(outcome: RunOutcome, expected: dict[str, object]) -> dict[str, object]:
    got_disposition = None
    if outcome.decision_json:
        raw = outcome.decision_json.get("decision")
        if isinstance(raw, str):
            got_disposition = raw.strip().upper()
    correct = got_disposition == expected["disposition"]
    return {
        "expected_disposition": expected["disposition"],
        "got_disposition": got_disposition,
        "correct": correct,
        "had_decision_json": outcome.decision_json is not None,
        "error": outcome.error,
    }


# ── main sweep ───────────────────────────────────────────────────────────────────────

def main() -> int:
    key = api_key()
    tools_schema = load_tools_manifest()
    cases = load_cases()
    ground_truth = load_ground_truth()

    total_runs = len(MODELS) * len(cases) * RUNS_PER_CASE
    print(f"Loaded {len(cases)} cases. Models: {', '.join(f'{k}={v}' for k, v in MODELS.items())}")
    print(f"Total runs: {total_runs} ({len(MODELS)} models x {len(cases)} cases x "
          f"{RUNS_PER_CASE} runs)\n")

    raw_results: list[dict[str, object]] = []
    done = 0
    for model_key, model_id in MODELS.items():
        for case in cases:
            expected = ground_truth[case.case_id]
            for run_index in range(1, RUNS_PER_CASE + 1):
                done += 1
                print(f"[{done}/{total_runs}] {model_key} ({model_id}) "
                      f"{case.case_id} run {run_index}...", end=" ", flush=True)
                outcome = run_one(key, case, model_key, model_id, run_index, tools_schema)
                verdict = score(outcome, expected)
                print("OK" if verdict["correct"] else
                      ("ERR" if outcome.error else "MISS"),
                      f"(got={verdict['got_disposition']}, "
                      f"expected={verdict['expected_disposition']})")
                raw_results.append({
                    "case_id": outcome.case_id, "incident_id": outcome.incident_id,
                    "model_key": outcome.model_key, "model_id": outcome.model_id,
                    "run_index": outcome.run_index, "turns": outcome.turns,
                    "tool_calls": outcome.tool_calls, "final_text": outcome.final_text,
                    "decision_json": outcome.decision_json, "error": outcome.error,
                    "score": verdict,
                })

    out_path = ROOT / "evaluation_specimens_raw_results.json"
    out_path.write_text(json.dumps(raw_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRaw results written to {out_path}")

    print_report(raw_results, ground_truth)
    return 0


# ── reporting ────────────────────────────────────────────────────────────────────────

def print_report(raw_results: list[dict[str, object]],
                 ground_truth: dict[str, dict[str, object]]) -> None:
    categories = ("NO_REPAIR", "REPAIR", "ESCALATE")

    print("\n" + "=" * 78)
    print("COMPARATIVE SUMMARY")
    print("=" * 78)

    header = f"{'Model':<12}{'Overall %':<12}" + "".join(f"{c + ' %':<14}" for c in categories) \
        + f"{'Consistent %':<14}"
    print(header)
    print("-" * len(header))

    for model_key in MODELS:
        rows = [r for r in raw_results if r["model_key"] == model_key]
        n = len(rows)
        correct = sum(1 for r in rows if r["score"]["correct"])
        overall = 100 * correct / n if n else 0.0

        cat_pct = {}
        for cat in categories:
            cat_rows = [r for r in rows if r["score"]["expected_disposition"] == cat]
            cat_correct = sum(1 for r in cat_rows if r["score"]["correct"])
            cat_pct[cat] = 100 * cat_correct / len(cat_rows) if cat_rows else float("nan")

        by_case: dict[str, list[bool]] = {}
        for r in rows:
            by_case.setdefault(r["case_id"], []).append(r["score"]["correct"])
        consistent_cases = sum(1 for outcomes in by_case.values() if all(outcomes))
        consistent_pct = 100 * consistent_cases / len(by_case) if by_case else 0.0

        line = f"{model_key:<12}{overall:<12.1f}"
        line += "".join(f"{cat_pct[c]:<14.1f}" if cat_pct[c] == cat_pct[c] else f"{'n/a':<14}"
                        for c in categories)
        line += f"{consistent_pct:<14.1f}"
        print(line)

    print("\n" + "-" * 78)
    print("FAILURE / DIVERGENCE ANALYSIS")
    print("-" * 78)
    case_ids = sorted(ground_truth.keys())
    for case_id in case_ids:
        expected = ground_truth[case_id]["disposition"]
        line_parts = [f"{case_id:<45} expected={expected:<10}"]
        diverged = False
        for model_key in MODELS:
            rows = [r for r in raw_results if r["model_key"] == model_key
                    and r["case_id"] == case_id]
            got = [r["score"]["got_disposition"] or "NONE" for r in rows]
            if not all(g == expected for g in got):
                diverged = True
            line_parts.append(f"{model_key}={','.join(got)}")
        if diverged:
            print("  " + "  ".join(line_parts))
    print()


if __name__ == "__main__":
    raise SystemExit(main())
