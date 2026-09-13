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

To see a run before the runtime exists:

```bash
python -m adii.examples.walkthrough --archive
```

A label names one run forever. Archiving under a taken label is refused, never overwritten.
