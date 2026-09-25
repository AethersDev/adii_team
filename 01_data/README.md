# 01_data — what the system reads

Everything here is readable by anyone with this folder, and the system runs from it.

```text
incidents/     the incident packages: each one's alert, data (world.sql), transforms and
               evidence documents — never its answer
packs/         each final evaluation pack's receipt, written before it ran, and its report
runs/          the archive: one folder per run — receipt, trace, record
demo/csv/      sample data to bring to the page as CSV files
walkthrough/   the teaching incident, its recorded run, and the same incident ended every
               other way
```

No answer key is here. Answer keys, scoring and the validator's invariants belong to the
evaluation authority, in `02_src/adii/evaluation/` and `02_src/adii/validation/`, which the
investigator cannot import; `02_src/tests/integration/test_answer_keys_stay_out.py` fails
the build if evaluation-shaped data appears anywhere else. An investigator that could read
the answer would not be investigating anything.
