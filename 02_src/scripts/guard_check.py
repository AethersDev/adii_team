"""The guard-removal pass — inherited X1, enforced at integration by D.

    python 02_src/scripts/guard_check.py            # every guard: neutralise, run pytest, restore
    python 02_src/scripts/guard_check.py --only D   # one track's guards
    python 02_src/scripts/guard_check.py --list

A guard is not demonstrated because a test passes. It is demonstrated when removing the
guard makes a test fail. So, for each registered guard, this script replaces the exact
snippet with a neutralised one, runs the suite, restores the file byte for byte, and
reports: KILLED (a test failed, the guard is demonstrated) or SURVIVED (nothing depended on
it). Survivors are listed by name, never summarised into a percentage. Controls are guards
known to be covered; a control that survives means the harness is broken and no result
from the pass means anything. A registered snippet that is not found is itself a failure,
because a guard that moved is a guard that may be gone.

Exit status: 0 when every guard is killed; 1 on any survivor, any surviving control, or any
snippet not found. The registry is the team's: A, B, C and D each own their rows, and a
guard they add to the code is not done until its row is here and killed.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "02_src" / "adii"


@dataclass(frozen=True)
class Guard:
    name: str
    track: str            # A, B, C or D — who owns the guard and its test
    file: str             # relative to 02_src/adii
    snippet: str          # exact text, present once
    neutralised: str      # what removes the guard and nothing else
    control: bool = False # known covered: surviving means the harness is broken


GUARDS = (
    # ── A: the loop ─────────────────────────────────────────────────────────────────
    Guard("A.evidence_gate", "A", "investigator/loop.py",
          "                and not state.observations\n",
          "                and False\n"),
    Guard("A.turn_budget", "A", "investigator/loop.py",
          "        if turns_taken >= max_turns:\n",
          "        if False:\n"),
    Guard("A.max_turns_validated", "A", "investigator/loop.py",
          "    if isinstance(max_turns, bool) or not isinstance(max_turns, int) "
          "or max_turns < 0:\n",
          "    if False:\n"),
    Guard("A.patch_maps_path_to_text", "A", "investigator/loop.py",
          "    if not all(isinstance(k, str) and isinstance(v, str) for k, v in patch.items()):\n",
          "    if False:\n"),
    # ── B: the tool layer ───────────────────────────────────────────────────────────
    Guard("B.unknown_tool_denied", "B", "tools/executor.py",
          "        if tool is None:\n            return self._result(call, \"DENIED\", {\n",
          "        if tool is None:\n            tool = next(iter(self._tools.values()))\n"
          "        if False:\n            return self._result(call, \"DENIED\", {\n"),
    Guard("B.call_budget", "B", "tools/executor.py",
          "        if self.max_calls is not None and self.calls_dispatched >= self.max_calls:\n",
          "        if False:\n"),
    Guard("B.arguments_validated", "B", "tools/executor.py",
          "        problems = validate_arguments(spec, call.arguments)\n",
          "        problems = []\n"),
    Guard("B.read_only_authoriser", "B", "tools/database.py",
          "        if action in ALLOWED_ACTIONS:\n",
          "        if True:\n"),
    Guard("B.forbidden_functions", "B", "tools/database.py",
          "            if action == sqlite3.SQLITE_FUNCTION "
          "and str(arg2).lower() in FORBIDDEN_FUNCTIONS:\n",
          "            if False:\n"),
    # ── contracts: shared, changed only by review ───────────────────────────────────
    Guard("contracts.repair_needs_patch", "contracts", "contracts/core.py",
          "            if not self.repair_id or not self.patch:\n",
          "            if False:\n", control=True),
    Guard("contracts.repair_run_needs_verdict", "contracts", "contracts/core.py",
          "        if self.decision.disposition is Disposition.REPAIR "
          "and self.validation is None:\n",
          "        if False:\n"),
    # ── D: the record, the archive, the runtime, the page ───────────────────────────
    Guard("D.strict_json_on_write", "D", "reporting/record.py",
          "        return json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) "
          "+ \"\\n\"\n",
          "        return json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=True) "
          "+ \"\\n\"\n",
          control=True),
    Guard("D.strict_json_on_read", "D", "reporting/record.py",
          "    doc = json.loads(text, parse_constant=_not_json)\n",
          "    doc = json.loads(text)\n"),
    Guard("D.unknown_schema_refused", "D", "reporting/record.py",
          "    if schema != SCHEMA:\n",
          "    if False:\n"),
    Guard("D.label_is_one_segment", "D", "reporting/record.py",
          "    if not LABEL.fullmatch(label):\n",
          "    if False:\n"),
    Guard("D.submitted_iff_decision", "D", "reporting/record.py",
          "        if (self.termination == \"submitted\") != (self.decision is not None):\n",
          "        if False:\n"),
    Guard("D.label_never_overwritten", "D", "reporting/record.py",
          "    if path.exists():\n        raise FileExistsError(",
          "    if False:\n        raise FileExistsError("),
    Guard("D.only_repair_reaches_validator", "D", "runtime/run.py",
          "        if decision.disposition is Disposition.REPAIR:\n",
          "        if True:\n"),
    Guard("D.receipt_needs_reason", "D", "reporting/receipts.py",
          "    if not reason.strip():\n",
          "    if False:\n"),
    Guard("D.api_label_checked_before_disk", "D", "demo/server.py",
          "            if not LABEL.fullmatch(label) or not (ARCHIVE / label).is_dir():\n",
          "            if not (ARCHIVE / label).is_dir():\n"),
    Guard("D.page_renders_text_never_markup", "D", "demo/web/app.js",
          "  n.append(...kids);\n",
          "  kids.forEach((k) => (typeof k === \"string\" "
          "? n.insertAdjacentHTML(\"beforeend\", k) : n.append(k)));\n"),
    Guard("D.server_starts_local_only", "D", "demo/__main__.py",
          "    if args.provider == \"local\" and not endpoint_is_local(args.endpoint):\n",
          "    if False:\n"),
    Guard("D.server_starts_paid_only_past_the_preconditions", "D", "demo/__main__.py",
          "        why = refused_paid(args.model, args.max_cost_usd, args.endpoint, "
          "args.served_as)\n",
          "        why = None\n"),
    Guard("D.paid_cap_is_finite", "D", "runtime/__main__.py",
          "    if not (math.isfinite(max_cost_usd) and max_cost_usd > 0):\n",
          "    if not max_cost_usd > 0:\n"),
    Guard("D.paid_wire_name_is_the_priced_name", "D", "runtime/__main__.py",
          "    if served_as not in (None, model):\n",
          "    if False:\n"),
    Guard("D.page_launch_needs_operator", "D", "demo/server.py",
          "        if not LAUNCH:\n",
          "        if False:\n"),
    Guard("D.page_launch_known_incident", "D", "demo/server.py",
          "        if not isinstance(incident, str) or incident not in "
          "{i[\"incident_id\"] for i in incidents()}:\n",
          "        if False:\n"),
    Guard("D.page_launch_one_at_a_time", "D", "demo/server.py",
          "        if any(row.get(\"running\") for row in index(ARCHIVE)) "
          "or not RUNNING.acquire(blocking=False):\n",
          "        if False:\n"),
    Guard("D.page_launch_one_at_a_time_in_process", "D", "demo/server.py",
          "        if any(row.get(\"running\") for row in index(ARCHIVE)) "
          "or not RUNNING.acquire(blocking=False):\n",
          "        if any(row.get(\"running\") for row in index(ARCHIVE)) "
          "or not RUNNING.acquire(blocking=True):\n"),
    Guard("D.post_body_declared_json", "D", "demo/server.py",
          "        if self.headers.get(\"Content-Type\", \"\").split(\";\")[0].strip() "
          "!= \"application/json\":\n",
          "        if False:\n"),
    Guard("D.feedback_useful_enumerated", "D", "demo/server.py",
          "    if useful not in FEEDBACK_LIMITS[\"useful\"]:\n",
          "    if False:\n"),
    Guard("D.feedback_bounded", "D", "demo/server.py",
          "    if len(expected) > FEEDBACK_LIMITS[\"expected\"] "
          "or len(by) > FEEDBACK_LIMITS[\"by\"]:\n",
          "    if False:\n"),
    Guard("D.feedback_needs_record", "D", "demo/server.py",
          "            if not LABEL.fullmatch(label) "
          "or not (ARCHIVE / label / \"record.json\").is_file():\n",
          "            if not LABEL.fullmatch(label) or not (ARCHIVE / label).is_dir():\n"),
    # ── the seam between the record and the evaluation authority ──────────────────
    Guard("D.reader_refuses_a_patch_that_is_not_text", "D", "reporting/record.py",
          "    if not isinstance(patch, dict) or not all(\n",
          "    if False and not all(\n"),
    # ── the paid path: nothing is spent without a record, a price, a cap ────────────
    Guard("D.paid_provider_needs_receipt", "D", "provider/openai_compatible.py",
          "        if paid and not (receipt is not None and receipt.is_file()):\n",
          "        if False:\n"),
    Guard("D.cost_cap_between_requests", "D", "provider/openai_compatible.py",
          "            if spent >= self._cap:            "
          "# checked between requests: the overshoot is one\n",
          "            if False:\n"),
    Guard("D.paid_model_must_have_a_price", "D", "runtime/__main__.py",
          "    if model not in PRICES:\n",
          "    if False:\n"),
    Guard("D.paid_endpoint_carries_no_secret", "D", "provider/openai_compatible.py",
          "    if parts.query or parts.username or parts.password:\n        return False\n",
          "    if False:\n        return False\n"),
    Guard("D.paid_needs_credential_before_label", "D", "runtime/__main__.py",
          "    if not os.environ.get(\"OPENAI_API_KEY\"):\n",
          "    if False:\n"),
    Guard("D.ledger_row_without_usage_is_unknown", "D", "reporting/ledger.py",
          "        if isinstance(tokens_in, int) and isinstance(tokens_out, int) \\\n"
          "                and not isinstance(tokens_in, bool) "
          "and not isinstance(tokens_out, bool):\n",
          "        if True:\n"
          "            tokens_in, tokens_out = tokens_in or 0, tokens_out or 0\n"),
    Guard("D.verify_lists_the_unattested", "D", "reporting/manifest.py",
          "    present = {p.relative_to(root).as_posix() for p in root.glob(\"*/*\") "
          "if p.is_file()}\n",
          "    present = {p.relative_to(root).as_posix() for p in artefacts(root)}\n"),
    Guard("C.score_needs_the_incidents_own_key", "C", "evaluation/__main__.py",
          "    if key[\"incident_id\"] != incident:\n",
          "    if False:\n"),
    Guard("C.score_refuses_an_unchecked_repair", "C", "evaluation/__main__.py",
          "    if unchecked and key[\"correct_disposition\"] == \"REPAIR\":\n",
          "    if False:\n"),
    Guard("C.report_never_overwritten", "C", "evaluation/__main__.py",
          "    if path.exists():\n        raise FileExistsError(f\"{path} exists",
          "    if False:\n        raise FileExistsError(f\"{path} exists"),
    Guard("C.partition_assigns_one_of_two_classes", "C", "evaluation/commitment.py",
          "        if assigned not in CLASSES:\n",
          "        if False:\n"),
    Guard("C.commitment_made_once", "C", "evaluation/commitment.py",
          "        if out.exists():\n",
          "        if False:\n"),
    # C's own guards (the key loaders, the scorer's refusals) join here from C's tests.
)

PYTEST = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


def run_suite() -> bool:
    """True when the suite passes. -x: one failing test is all a kill needs."""
    return subprocess.run(PYTEST, cwd=ROOT, capture_output=True).returncode == 0


def check(guard: Guard, suite: Callable[[], bool]) -> str:
    """Neutralise, run, restore. Returns KILLED, SURVIVED or NOT FOUND."""
    path = SRC / guard.file
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(guard.snippet) != 1:
        return "NOT FOUND"
    path.write_bytes(text.replace(guard.snippet, guard.neutralised).encode("utf-8"))
    try:
        passed = suite()
    finally:
        path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            raise RuntimeError(f"{guard.file} was not restored — fix the file before anything else")
    return "SURVIVED" if passed else "KILLED"


def main(argv: list[str] | None = None, suite: Callable[[], bool] = run_suite) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", metavar="TRACK",
                        help="run one track's guards: A, B, C, D, contracts")
    parser.add_argument("--list", action="store_true", help="list the registry and exit")
    args = parser.parse_args(argv)
    guards = [g for g in GUARDS if not args.only or g.track == args.only]
    if args.list:
        for g in guards:
            print(f"{g.name:<40} {g.file}{'   (control)' if g.control else ''}")
        return 0
    failures = []
    for guard in guards:
        outcome = check(guard, suite)
        flag = ""
        if outcome == "NOT FOUND":
            flag = "  ← the snippet moved or is gone"
            failures.append(guard.name)
        elif outcome == "SURVIVED":
            flag = "  ← CONTROL SURVIVED: the harness is broken" if guard.control \
                else "  ← no test depends on this guard"
            failures.append(guard.name)
        print(f"{outcome:<10} {guard.name}{flag}", flush=True)
    print(f"\n{len(guards) - len(failures)} of {len(guards)} guards demonstrated.")
    if failures:
        print("Not demonstrated: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
