# 01_data/runs — the run archive

Every run is archived here as one folder, however it ended:

```text
<label>/receipt.json   written and flushed before the first model request: the incident and
                       data by digest, the configuration, the reason the spend is permitted
<label>/trace.jsonl    every event, in order, as the runtime recorded it
<label>/record.json    the record: one strict, versioned document (adii.run_record/v3)
```

A label names one run forever; a taken label is refused, never overwritten. A run that
stopped without writing a record is listed by the page as exactly that.

```bash
python -m adii.demo                        # the page over this archive: http://127.0.0.1:8000
```

In this folder: the runs of the final evaluation packs (their receipts and reports are in
`01_data/packs/`), and the four `square-*` runs — one scripted proposal for each cell of the
admissibility square, judged by the real authorizer and validator
(`python 02_src/scripts/admissibility_square.py`; see `02_src/docs/architecture.md`).
