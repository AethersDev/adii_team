# 01_data/runs — the run archive

Every run the runtime completes is archived here as `<label>/record.json`: one strict,
versioned document per run (`adii.run_record/v1`, defined in
`02_src/adii/reporting/record.py`). The inspector reads this directory and nothing else:

```bash
python -m adii.demo                        # http://127.0.0.1:8000
```

Payloads are ignored by git — they are machine-produced and can be large — but ignoring is
not preserving. A tracked manifest of what exists (path, size, digest) lands with the
preservation unit in `02_src/docs/plan_telemetry.md`; until then, a run you need to keep is
copied out by hand.

To produce a run:

```bash
python -m adii.runtime --incident demo-learning-001 --provider fake
```

`python -m adii.examples.walkthrough --archive` archives the same run assembled by hand
rather than produced by the runtime. The two agree on every status, the decision and the
verdict, and a test says they do; they are not byte-identical, because the runtime's record
carries what the real tool layer returned, evidence ids included.

A label names one run forever. Archiving under a taken label is refused, never overwritten.
