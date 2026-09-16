# 01_data/runs — the run archive

Every run the runtime starts is archived here as `<label>/record.json`, however it ends —
a submission, a run the loop ended, or a failure of ours: one strict, versioned document per
run (`adii.run_record/v1`, defined in `02_src/adii/reporting/record.py`). A label reserved
by a run that never finished is listed by the inspector as exactly that. The inspector reads
this directory and nothing else:

```bash
python -m adii.demo                        # http://127.0.0.1:8000
```

Payloads are ignored by git — they are machine-produced and can be large — but ignoring is
not preserving. Three mechanisms, kept apart:

```bash
python -m adii.reporting.manifest                   # attest: MANIFEST.json — path, size, digest, retention
python -m adii.reporting.manifest --verify          # hold the archive to its manifest, from the manifest alone
python -m adii.reporting.manifest --preserve DEST   # manifest first, then the copy, then the copy verified
```

`MANIFEST.json` is tracked; commit it when the runs it lists are worth attesting — the
first paid run, say. The original is never deleted on the strength of an unverified copy.

Every run folder also holds `receipt.json`, written and flushed after the label was
reserved and before the investigator ran: the incident and world by digest, the
configuration, the source revision, and the reason the spend is permitted; and
`trace.jsonl`, every event as the runtime recorded it. A folder that has written nothing
for three minutes and has no record is a run that did not finish, and the inspector says
so. A person may leave `feedback.jsonl` beside a finished run, from the inspector.

What is kept, by name: `receipt.json`, `trace.jsonl` and `record.json` are **evidence** —
what the run left of itself; `feedback.jsonl` is an **annotation** — what someone said
about it afterwards. The manifest attests and preservation copies all four, each in its
class; a file under any other name in a run folder is listed by verification, not archived.

To produce a run:

```bash
python -m adii.runtime --incident demo-learning-001 --provider scripted
```

`python -m adii.examples.walkthrough --archive` archives the same run assembled by hand
rather than produced by the runtime. The two agree on every status, the decision and the
verdict, and a test says they do; they are not byte-identical, because the runtime's record
carries what the real tool layer returned, evidence ids included.

A label names one run forever. Archiving under a taken label is refused, never overwritten.
