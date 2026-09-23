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
    Guard("A.rejection_is_recorded_where_it_happens", "A", "investigator/loop.py",
          "        if sink is not None and durable:\n",
          "        if False:\n"),
    Guard("A.rejection_reason_returned_to_the_model", "A", "investigator/loop.py",
          '        kwargs = {"rejection": pending_rejection} if pending_rejection else {}\n',
          "        kwargs = {}\n"),
    Guard("A.patch_maps_path_to_text", "A", "investigator/loop.py",
          "    if not all(isinstance(k, str) and isinstance(v, str) for k, v in patch.items()):\n",
          "    if False:\n"),
    Guard("contracts.validation_state_space_is_closed", "contracts", "contracts/core.py",
          "        if self.reason_code is not None:\n"
          "            if self.reason_code not in REASON_CODES:\n",
          "        if False:\n"
          "            if self.reason_code not in REASON_CODES:\n"),
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
    Guard("B.transform_ids_are_logical", "B", "tools/transform_tools.py",
          "        if not isinstance(transform_id, str) or not "
          "LOGICAL_ID.fullmatch(transform_id):\n",
          "        if False:\n"),
    Guard("B.transform_source_is_complete", "B", "tools/transform_tools.py",
          "        if len(source) > max_chars:\n",
          "        if False:\n"),
    Guard("B.notice_ids_are_logical", "B", "tools/notice_tools.py",
          "        if not isinstance(notice_id, str) or not "
          "LOGICAL_ID.fullmatch(notice_id):\n",
          "        if False:\n"),
    Guard("B.notice_is_complete", "B", "tools/notice_tools.py",
          "        if len(content) > max_chars:\n",
          "        if False:\n"),
    Guard("B.change_history_is_complete", "B", "tools/change_history_tools.py",
          "    if len(changes) > max_records:\n",
          "    if False:\n"),
    Guard("B.change_history_tickets_are_unique", "B", "tools/change_history_tools.py",
          "        if ticket in seen_tickets:\n",
          "        if False:\n"),
    Guard("B.change_history_is_newest_first", "B", "tools/change_history_tools.py",
          "        if previous_date is not None and parsed_date > previous_date:\n",
          "        if False:\n"),
    Guard("B.reconciliation_source_is_bounded", "B", "tools/reconciliation_tools.py",
          "    if size > max_source_bytes:\n",
          "    if False:\n"),
    Guard("B.reconciliation_lines_are_bounded", "B", "tools/reconciliation_tools.py",
          "        if line_size > max_line_bytes:\n",
          "        if False:\n"),
    Guard("B.reconciliation_offset_is_nonnegative", "B", "tools/reconciliation_tools.py",
          "        if offset < 0:\n",
          "        if False:\n"),
    Guard("B.reconciliation_window_is_bounded", "B", "tools/reconciliation_tools.py",
          "        if limit <= 0 or limit > MAX_RECONCILIATION_LIMIT:\n",
          "        if False:\n"),
    Guard("B.declared_schema_tables_exist", "B", "tools/sql_tools.py",
          "        if unknown:\n",
          "        if False:\n"),
    # one closed bundle, the shape every evidence kind shares (tools/packages.py)
    Guard("B.bundle_json_keys_are_unique", "B", "tools/packages.py",
          "        if key in result:\n",
          "        if False:\n"),
    Guard("B.bundle_ids_are_logical", "B", "tools/packages.py",
          "        if not key or (keys is not None and not keys.fullmatch(key)):\n",
          "        if False:\n"),
    Guard("B.bundle_filenames_are_local", "B", "tools/packages.py",
          "        if not isinstance(filename, str) or not FILENAME.fullmatch(filename):\n",
          "        if False:\n"),
    Guard("B.bundle_holds_regular_files_only", "B", "tools/packages.py",
          "    if any(entry.is_symlink() or not entry.is_file() for entry in entries):\n",
          "    if False:\n"),
    Guard("B.bundle_is_closed", "B", "tools/packages.py",
          "    if present != declared:\n",
          "    if False:\n"),
    Guard("B.bundle_bytes_preserved", "B", "tools/packages.py",
          '    files = {name: (source_dir / name).read_bytes().decode("utf-8") '
          'for name in filenames}\n',
          '    files = {name: (source_dir / name).read_text(encoding="utf-8") '
          'for name in filenames}\n'),
    Guard("B.reconciliation_ids_are_logical", "B", "tools/reconciliation_tools.py",
          "    if not isinstance(reconciliation_id, str) or not "
          "LOGICAL_ID.fullmatch(reconciliation_id):\n",
          "    if False:\n"),
    Guard("B.reconciliation_lines_are_physical", "B", "tools/reconciliation_tools.py",
          "    lines = _LINE_END.split(source)\n",
          "    lines = source.splitlines()\n"),
    Guard("B.change_history_ids_are_logical", "B", "tools/change_history_tools.py",
          "    if not isinstance(history_id, str) or not LOGICAL_ID.fullmatch(history_id):\n",
          "    if False:\n"),
    Guard("B.change_history_date_is_calendar", "B", "tools/change_history_tools.py",
          "        if not _DATE.fullmatch(raw_date):\n",
          "        if False:\n"),
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
          "    if schema not in (SCHEMA, V2, V1):\n",
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
          '    node.append(typeof kid === "string" ? document.createTextNode(kid) : kid);\n',
          '    if (typeof kid === "string") node.insertAdjacentHTML("beforeend", kid);\n'
          "    else node.append(kid);\n"),
    Guard("D.server_starts_local_only", "D", "demo/__main__.py",
          "    if args.provider == \"local\" and not endpoint_is_local(args.endpoint):\n",
          "    if False:\n"),
    Guard("D.server_starts_paid_only_past_the_preconditions", "D", "demo/__main__.py",
          "        why = (refused_paid(args.model, args.max_cost_usd, args.endpoint, "
          "args.served_as,\n                            args.max_tokens)\n",
          "        why = (None\n"),
    Guard("D.paid_server_carries_no_alias", "D", "demo/__main__.py",
          "               or (args.served_as and ",
          "               or (False and "),
    Guard("D.paid_cap_is_finite", "D", "runtime/__main__.py",
          "    if not (math.isfinite(max_cost_usd) and max_cost_usd > 0):\n",
          "    if not max_cost_usd > 0:\n"),
    Guard("D.paid_wire_name_is_the_priced_name", "D", "runtime/__main__.py",
          "    if served_as not in (None, model):\n",
          "    if False:\n"),
    # decisions F1–F3: the page says what the record says — cited is cited, a fix stands only
    # with both authorities, and the drawing never costs the verdict it illustrates
    Guard("D.how_adii_knows_is_what_was_cited", "D", "demo/web/view.js",
          "  return refs.filter((ref) => byId[ref]).map((ref) => ({ ref, ...byId[ref] }));\n",
          "  return Object.keys(byId).map((ref) => ({ ref, ...byId[ref] }));\n"),
    Guard("D.a_fix_stands_only_with_both_authorities", "D", "demo/web/view.js",
          "  return Boolean(a && a.authorized && v && v.accepted);\n",
          "  return Boolean(v && v.accepted);\n"),
    Guard("C.the_series_never_costs_a_verdict", "C", "validation/validator.py",
          "            return ()           # and the verdict — already decided by the checks "
          "— stands\n",
          "            raise\n"),
    Guard("D.page_launch_needs_operator", "D", "demo/server.py",
          "        if not LAUNCH:\n",
          "        if False:\n"),
    Guard("D.page_launch_known_incident", "D", "demo/server.py",
          "                if not isinstance(incident, str) \\\n"
          "                        or incident not in {i[\"incident_id\"] for i in incidents()}:\n",
          "                if False:\n"),
    Guard("D.page_model_is_one_the_server_offers", "D", "demo/server.py",
          "    if model not in models():\n",
          "    if False:\n"),
    Guard("D.page_turns_within_the_ceiling", "D", "demo/server.py",
          "    if not (isinstance(turns, int) and not isinstance(turns, bool)\n"
          "            and 1 <= turns <= int(LAUNCH[\"max_turns\"])):\n",
          "    if False:\n"),
    # ── a visitor's own incident: what the page takes, bounded, and what the archive keeps ─
    Guard("D.brought_needs_a_description", "D", "demo/server.py",
          "    if not isinstance(description, str) or not description.strip():\n",
          "    if False:\n"),
    Guard("D.brought_files_are_bounded", "D", "demo/server.py",
          "    if not (isinstance(files, list) and 1 <= len(files) <= LIMITS[\"files\"] and all(\n",
          "    if not (isinstance(files, list) and all(\n"),
    Guard("D.body_is_bounded_before_it_is_read", "D", "demo/server.py",
          "        if length > limit:\n",
          "        if False:\n"),
    Guard("B.csv_row_matches_its_header", "D", "tools/user_world.py",
          "        if len(row) != len(header):\n",
          "        if False:\n"),
    Guard("B.csv_typing_never_alters_a_value", "D", "tools/user_world.py",
          "        return \"INTEGER\" if all(_INTEGER.fullmatch(v) and len(v.lstrip(\"-\")) <= 19\n"
          "                                and abs(int(v)) < 2 ** 63 for v in present) "
          "else \"TEXT\"\n",
          "        return \"INTEGER\" if all(_INTEGER.fullmatch(v) and len(v.lstrip(\"-\")) <= 19\n"
          "                                for v in present) else \"TEXT\"\n"),
    Guard("B.csv_real_is_exact_or_text", "D", "tools/user_world.py",
          "        return Decimal(value) == Decimal(repr(float(value)))\n",
          "        return True\n"),
    Guard("B.csv_rows_are_bounded", "D", "tools/user_world.py",
          "    if len(body) > LIMITS[\"rows\"]:\n",
          "    if False:\n"),
    Guard("D.incident_dir_holds_incident_and_world", "D", "runtime/__main__.py",
          "    if not folder.is_dir() or not all((folder / name).is_file() "
          "for name in INCIDENT_FILES):\n",
          "    if False:\n"),
    Guard("D.run_loads_the_archived_copy", "D", "runtime/__main__.py",
          "            context, tools, world_digest, _, evidence = "
          "incident_from_dir(folder, tool_cap)\n",
          "            pass\n"),
    Guard("D.label_released_when_the_package_fails", "D", "runtime/__main__.py",
          "        release(folder)      # nothing spent, no model spoken to\n",
          "        pass\n"),
    Guard("D.kept_package_is_regular_files", "D", "runtime/__main__.py",
          "        if path.is_symlink() or not path.is_file():\n",
          "        if False:\n"),
    Guard("D.evidence_bundles_are_attested", "D", "reporting/manifest.py",
          "    if len(parts) == 3 and parts[1] in SOURCE_DIRS:\n",
          "    if False:\n"),
    Guard("D.page_cap_is_paid_only", "D", "demo/server.py",
          "    elif \"max_cost_usd\" in body:\n",
          "    elif False:\n"),
    Guard("D.page_cap_within_the_ceiling", "D", "demo/server.py",
          "        if not (isinstance(cost, (int, float)) and not isinstance(cost, bool)\n"
          "                and 0 < cost <= ceiling):\n",
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
    # ── the run bounds: each hard, each its own resource, each named in its bound_hit ──
    Guard("D.cost_cap_admits_the_worst_case", "D", "provider/openai_compatible.py",
          "        if ledger.worst_case_usd + reserve > self._cap:\n",
          "        if False:\n"),
    Guard("D.cost_cap_admits_against_the_worst_case_not_the_lower_bound", "D",
          "provider/openai_compatible.py",
          "ledger.worst_case_usd + reserve > self._cap",
          "Decimal(repr(ledger.lower_bound_usd)) + reserve > self._cap"),
    Guard("D.cost_reserve_prices_the_whole_request", "D", "reporting/ledger.py",
          "    return input_tokens * price.input_per_token + max_tokens * price.output_per_token\n",
          "    return Decimal(0)\n"),
    Guard("D.unknown_usage_charged_at_its_reserve", "D", "reporting/ledger.py",
          "            worst += _reserve(request.payload)\n",
          "            worst += 0\n"),
    Guard("D.cost_arithmetic_is_exact", "D", "reporting/ledger.py",
          "    return Ledger(float(round(total, 6)), worst, proved, unknown)\n",
          "    return Ledger(float(round(total, 6)), round(worst, 6) if worst.is_finite() "
          "else worst, proved, unknown)\n"),
    Guard("D.reserve_breach_ends_the_run", "D", "provider/openai_compatible.py",
          "            if billed is not None and billed > reserve:\n",
          "            if False:\n"),
    Guard("D.request_in_flight_is_cut_at_the_deadline", "D", "provider/openai_compatible.py",
          "        if answer is None:                 # the deadline passed with the request "
          "in flight\n",
          "        if answer is None:                 # the deadline passed with the request "
          "in flight\n            answer = self._worker.ask({}, wait=None)\n"),
    Guard("D.no_redirect_is_followed", "D", "provider/worker.py",
          "    def redirect_request(self, req, fp, code, msg, headers, newurl):\n"
          "        return None\n",
          "    def redirect_request(self, req, fp, code, msg, headers, newurl):\n"
          "        return super().redirect_request(req, fp, code, msg, headers, newurl)\n"),
    Guard("D.body_that_is_not_json_is_the_endpoints_failure", "D",
          "provider/openai_compatible.py",
          "        if not isinstance(reply, dict):\n"
          "            raise ProviderFailure(\"malformed\", status=answer.get(\"status\"))\n",
          "        if not isinstance(reply, dict):\n"
          "            raise ValueError(\"malformed\")\n"),
    Guard("D.reply_without_the_apis_shape_is_the_endpoints_failure", "D",
          "provider/openai_compatible.py",
          "        if content is _NO_MESSAGE:          # the API's shape, not the model's answer, "
          "is missing\n"
          "            raise ProviderFailure(\"malformed\", status=answer.get(\"status\"))\n",
          "        if content is _NO_MESSAGE:          # the API's shape, not the model's answer, "
          "is missing\n"
          "            raise ValueError(\"malformed\")\n"),
    Guard("D.worker_spawn_failure_is_the_providers", "D", "provider/openai_compatible.py",
          "            except OSError as failed:       # no process to ask: ours, never the "
          "model's\n"
          "                raise ProviderFailure(\"worker\") from failed\n",
          "            except OSError as failed:       # no process to ask: ours, never the "
          "model's\n"
          "                raise\n"),
    Guard("D.pre_flight_proves_a_completion_not_a_listing", "D", "provider/__main__.py",
          "    answer = transact(request)\n",
          "    answer = {\"ok\": True, \"status\": 200, \"body\": "
          "'{\"usage\": {\"prompt_tokens\": 1, \"completion_tokens\": 1}}'}\n"),
    Guard("D.env_local_never_overwrites_the_environment", "D", "provider/credential.py",
          "    if os.environ.get(\"OPENAI_API_KEY\"):\n        return\n"
          "    path = (REPO if root is None else root) / ENV_LOCAL\n",
          "    if False:\n        return\n"
          "    path = (REPO if root is None else root) / ENV_LOCAL\n"),
    Guard("D.env_local_refuses_the_name_given_twice", "D", "provider/credential.py",
          "        if found is not None:               # two keys is no key: which one was "
          "meant?\n",
          "        if False:\n"),
    Guard("D.env_local_is_name_value_lines_only", "D", "provider/credential.py",
          "        if not equals or not name.isidentifier():\n",
          "        if False:\n"),
    Guard("D.max_tokens_refused_before_the_label", "D", "runtime/__main__.py",
          "    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) "
          "or max_tokens <= 0:\n",
          "    if False:\n"),
    Guard("D.paid_model_is_billed_byte_level", "D", "runtime/__main__.py",
          "    if PRICES[model].tokenizer not in BYTE_LEVEL_TOKENIZERS:\n",
          "    if False:\n"),
    Guard("D.first_request_must_be_affordable", "D", "runtime/__main__.py",
          "        if first > Decimal(repr(args.max_cost_usd)):\n",
          "        if False:\n"),
    Guard("D.wall_clock_is_finite_and_above_zero", "D", "runtime/__main__.py",
          "    if not (math.isfinite(max_wall_clock_seconds) and max_wall_clock_seconds > 0):\n",
          "    if False:\n"),
    Guard("D.tool_calls_bounded_for_a_brought_incident", "D", "runtime/__main__.py",
          "= incident_from_dir(folder, tool_cap)\n",
          "= incident_from_dir(folder)\n"),
    Guard("D.input_bound_counts_every_byte", "D", "provider/openai_compatible.py",
          '    return sum(len(m["content"].encode("utf-8")) + TOKENS_PER_MESSAGE '
          'for m in messages) \\\n',
          '    return sum(len(m["content"]) // 4 + TOKENS_PER_MESSAGE '
          'for m in messages) \\\n'),
    Guard("D.model_requests_are_bounded", "D", "provider/openai_compatible.py",
          "        if self._max_requests is not None and self._turn >= self._max_requests:\n",
          "        if False:\n"),
    Guard("D.no_request_past_the_deadline", "D", "provider/openai_compatible.py",
          "            if remaining <= 0:\n",
          "            if False:\n"),
    Guard("D.tool_calls_bounded_from_the_command_line", "D", "runtime/__main__.py",
          "    tool_cap = args.max_tool_calls\n",
          "    tool_cap = None\n"),
    Guard("D.bounds_are_above_zero", "D", "runtime/__main__.py",
          "    if any(v <= 0 for v in (max_turns, max_tool_calls, max_model_requests)):\n",
          "    if False:\n"),
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
          "    if isinstance(tokens_in, int) and isinstance(tokens_out, int) \\\n"
          "            and not isinstance(tokens_in, bool) "
          "and not isinstance(tokens_out, bool):\n",
          "    if True:\n"
          "        tokens_in, tokens_out = tokens_in or 0, tokens_out or 0\n"),
    Guard("D.verify_lists_the_unattested", "D", "reporting/manifest.py",
          "    present = {p.relative_to(root).as_posix() for p in files_of(root)}\n",
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
    Guard("C.exposure_identity", "C", "evaluation/exposure.py",
          '        if not isinstance(identity, str) or not identity.strip() '
          'or identity in candidates:\n',
          '        if False:\n'),
    Guard("C.exposure_membership", "C", "evaluation/exposure.py",
          '        if item["custom_id"] not in candidates:\n',
          '        if False:\n'),
    Guard("C.exposure_selection_binding", "C", "evaluation/exposure.py",
          '        if (doc["source_corpus_sha256"] != corpus_hash\n          '
          '      or not doc["evidence_class"].startswith("UNBLINDED_AI_ASSIS'
          'TED")):\n',
          '        if False:\n'),
    Guard("C.exposure_fixture_binding", "C", "evaluation/exposure.py",
          '    if doc["source"]["corpus_sha256"] != corpus_hash:\n',
          '    if False:\n'),
    Guard("C.exposure_model_receipt", "C", "evaluation/exposure.py",
          '        if doc.get("corpus_sha256") != corpus_hash or not all(\n  '
          '              isinstance(doc.get(k), str) and doc[k].strip()\n    '
          '               for k in ("custom_id", "model", "timestamp")):\n',
          '        if False:\n'),
    Guard("C.exposure_corpus_digest", "C", "evaluation/exposure.py",
          '    if hashlib.sha256(corpus).hexdigest() != args.expected_sha256:\n',
          '    if False:\n'),
    Guard("C.exposure_corpus_count", "C", "evaluation/exposure.py",
          '    if len(result["candidates"]) != args.expected_count:\n',
          '    if False:\n'),
    Guard("C.exposure_unknown_default", "C", "evaluation/exposure.py",
          '"KNOWN_EXPOSED" if refs else "UNKNOWN_EXPOSURE"',
          '"KNOWN_EXPOSED" if refs else "KNOWN_UNEXPOSED"'),
    Guard("C.exposure_write_once", "C", "evaluation/exposure.py",
          'args.out.open("x",',
          'args.out.open("w",'),
    Guard("D.repair_target_must_be_readable", "D", "runtime/__main__.py",
          "    missing = [p for p in context.permitted_write_paths\n",
          "    missing = [p for p in ()\n"),
    # ── C: validation — the patch is applied from frozen inputs or refused, never guessed ──
    # grounding is read from the archived trace: a refused call observes nothing
    Guard("C.decisive_is_read_from_the_trace", "C", "evaluation/grounding.py",
          '                if e.get("kind") == "tool_result"'
          ' and e["payload"].get("status") == "OK"}\n',
          '                if e.get("kind") == "tool_result"}\n'),
    Guard("C.grounding_key_bound_to_this_answer_key", "C", "evaluation/__main__.py",
          '        if grounding["answer_key_filename"] != key_path.name:\n',
          "        if False:\n"),
    # trace contract row 1: the record holds what the model was sent, each message once
    Guard("D.request_records_what_was_sent", "D", "provider/openai_compatible.py",
          "        self._recorded = len(self._messages)\n",
          "        pass\n"),
    # decision J: a case the deterministic path cannot settle is the judge's, or unresolved
    Guard("C.judge_unresolved_without_a_judge", "C", "evaluation/scoring.py",
          "    if judge is None:\n",
          "    if False:\n"),
    Guard("D.judge_named_by_prompt_digest", "D", "provider/judge.py",
          '            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),\n',
          '            "prompt_sha256": None,\n'),
    # the canonical world: a repair repairs something; a package id never leaves the packages
    Guard("C.a_repair_changes_the_world", "C", "validation/checks.py",
          "    if moved:\n",
          "    if True:\n"),
    Guard("D.incident_id_is_one_segment", "D", "runtime/__main__.py",
          "    if LABEL.fullmatch(incident_id) and folder.is_dir():      # brought incident's\n",
          "    if folder.is_dir():      # brought incident's\n"),
    # scale: every budget grows with the world it bounds, never a fixed number of instructions
    Guard("B.query_budget_scales_with_the_world", "B", "tools/database.py",
          '        limits.setdefault("max_progress_ticks", '
          'max(QUERY_TICKS_FLOOR, held // ROWS_PER_TICK))\n',
          '        limits.setdefault("max_progress_ticks", QUERY_TICKS_FLOOR)\n'),
    Guard("C.rebuild_budget_scales_with_the_world", "C", "validation/patching.py",
          "max_build_ticks=2 * world_ticks + MAX_BUILD_TICKS)",
          "max_build_ticks=MAX_BUILD_TICKS)"),
    # the controls: each arm is what it says, and a pack's spend is capped before it runs
    Guard("D.floor_arm_asks_no_model", "D", "runtime/__main__.py",
          '    if (args.provider == "none") != (args.arm == "always-escalate"):\n',
          "    if False:\n"),
    Guard("D.alert_only_sees_no_tool", "D", "runtime/__main__.py",
          '    return ToolExecutor(max_calls=max_tool_calls) if arm == "alert-only" else tools\n',
          "    return tools\n"),
    Guard("C.pack_worst_case_within_its_cap", "C", "evaluation/grid.py",
          "            if args.pack_cap_usd is None or worst > Decimal(str(args.pack_cap_usd)):\n",
          "            if False:\n"),
    Guard("D.judge_question_within_its_bound", "D", "provider/judge.py",
          "        if reserve > MAX_COST_USD:\n",
          "        if False:\n"),
    # the audit of 23 Sep: strict live trace, a versioned record shape, no unscored run hidden
    Guard("D.live_trace_is_strict_json", "D", "runtime/run.py",
          '"payload": payload}, allow_nan=False) + "\\n")',
          '"payload": payload}, default=str) + "\\n")'),
    Guard("D.v2_record_carries_authorization", "D", "reporting/record.py",
          '        a = doc.get("authorization") if v1 else doc["authorization"]\n',
          '        a = doc.get("authorization")\n'),
    Guard("C.unscored_run_is_named", "C", "evaluation/grid.py",
          '"category": scored["category"] if scored else "unscored" if record else "missing",',
          '"category": scored["category"] if scored else record.termination if record '
          'else "missing",'),
    # decision M2: a reasoning model is asked with its effort and never with a temperature
    Guard("D.effort_replaces_temperature", "D", "provider/openai_compatible.py",
          "        if self._effort is None:\n",
          "        if True:\n"),
    Guard("D.effort_is_paid_only", "D", "runtime/__main__.py",
          '    if args.reasoning_effort and args.provider != "openai":\n',
          "    if False:\n"),
    Guard("C.pack_effort_is_paid_only", "C", "evaluation/grid.py",
          '        if args.reasoning_effort and args.provider != "openai":\n',
          "        if False:\n"),
    # pilot-paid-v2: a refused tool call is in the runtime's history, and says why
    Guard("A.refused_call_is_in_the_history", "A", "investigator/loop.py",
          '                "arguments": call.arguments,\n'
          '            }, durable=not valid_envelope)\n',
          '                "arguments": call.arguments,\n            }, durable=False)\n'),
    Guard("A.call_then_text_is_named", "A", "investigator/loop.py",
          "                    why = TOOL_CALL_THEN_TEXT\n",
          "                    pass\n"),
    # decisions F1 and F2: the chart is the record's — the runtime's reading, the validator's
    Guard("D.alert_is_observed_before_the_investigation", "D", "runtime/run.py",
          "    if alert is not None:\n",
          "    if False:\n"),
    Guard("C.validator_reports_its_rebuilt_series", "C", "validation/validator.py",
          "                                rebuilt_series=self.alerted_series(context.incident_id, "
          "rebuilt))",
          "                                rebuilt_series=())"),
    # phase 4: a registered final pack runs only on the newest freeze, with its frozen terms
    Guard("C.registered_pack_runs_only_on_the_freeze", "C", "evaluation/grid.py",
          '            if freeze is None or moved or pack != freeze["packs"].get(args.pack):\n',
          "            if False:\n"),
    # a reply cut off at the completion bound is named as cut, never left to read as malformed
    Guard("D.cut_reply_is_named", "D", "provider/openai_compatible.py",
          '        self._cut = finish == "length"\n',
          "        self._cut = False\n"),
    Guard("C.failed_rebuild_is_reject_not_unchecked", "C", "validation/validator.py",
          '                                    checks_run=("rebuild",))\n',
          '                                    checks_run=())\n'),
    Guard("D.legacy_unchecked_is_never_a_verdict", "D", "runtime/run.py",
          '            if validation.state == "UNCHECKED":\n',
          "            if False:\n"),
    # trace contract row 3: a citation resolves to an observation the run minted, or it is refused
    Guard("contracts.a_decision_cites_each_observation_once", "contracts", "contracts/core.py",
          "        if len(set(self.evidence_refs)) != len(self.evidence_refs):\n",
          "        if False:\n"),
    Guard("A.citation_must_be_an_observation_the_model_received", "A", "investigator/loop.py",
          "            if unresolved:\n",
          "            if False:\n"),
    Guard("D.a_record_never_cites_what_its_trace_never_minted", "D", "reporting/record.py",
          "            if dangling:\n                raise ValueError(",
          "            if False:\n                raise ValueError("),
    # m7 row 4: the authorization fact, the runtime's, for every REPAIR, apart from validation
    Guard("contracts.authorization_state_space_is_closed", "contracts", "contracts/core.py",
          "        if self.authorized != (not self.denied_paths):\n",
          "        if False:\n"),
    Guard("D.authorization_is_established_for_every_repair", "D", "runtime/run.py",
          "            authorization = authorize(context, decision)\n",
          "            authorization = None\n"),
    Guard("D.one_denied_target_denies_the_patch_whole", "D", "runtime/run.py",
          "    denied = tuple(path for path in checked if path not in permitted)\n",
          "    denied = () if permitted & set(checked) else tuple(\n"
          "        path for path in checked if path not in permitted)\n"),
    Guard("D.validator_never_sees_permitted_paths", "D", "runtime/run.py",
          "            validation = validator.validate(replace(context, "
          "permitted_write_paths=()),\n"
          "                                            decision)\n",
          "            validation = validator.validate(context, decision)\n"),
    Guard("C.patch_names_the_permitted_transform", "C", "validation/patching.py",
          "    if not patch or set(patch) - patchable:\n",
          "    if False:\n"),
    Guard("C.patch_is_one_statement", "C", "validation/patching.py",
          '    if ";" in bare:\n',
          "    if False:\n"),
    Guard("C.unknown_world_raises_never_guesses", "C", "validation/validator.py",
          "        if not (_ID.fullmatch(context.incident_id) and path.is_file()):\n",
          "        if False:\n"),
    Guard("C.accept_only_when_every_check_passes", "C", "validation/validator.py",
          "        accepted = all(outcome.passed for outcome in outcomes)\n",
          "        accepted = True\n"),
    # decision V: the validator knows the invariant, never the answer
    Guard("C.oracle_shape_is_closed", "C", "validation/validator.py",
          '    if not isinstance(doc, dict) or set(doc) != {"schema", "incident_id", "pipeline",\n',
          '    if not isinstance(doc, dict) or set(doc) < {"schema", "incident_id", "pipeline",\n'),
    Guard("C.invariants_compare_rows", "C", "validation/checks.py",
          "    if got == want:\n",
          "    if len(got) == len(want):\n"),
    Guard("B.build_budget_bounds_a_candidate_transform", "B", "tools/database.py",
          "            return max_build_ticks is not None and ticks > max_build_ticks"
          "   # non-zero aborts\n",
          "            return False\n"),
    # C's own guards (the key loaders, the scorer's refusals) join here from C's tests.
)

# -B: a mutation run writes no bytecode. A neutralised file of the same size, restored within
# the same second, would otherwise leave a .pyc of the neutralised code that the next plain
# import trusts — the real suite then runs the guard-less code while the source shows the
# guard (found 20 Sep: open("x") → open("w") in exposure.py).
PYTEST = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


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
