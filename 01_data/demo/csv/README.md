# 01_data/demo/csv — the data to bring

Every development specimen's world, as CSV files: one folder per incident, one file per
table, and the alert in `alert.txt`. This is what to attach under **Your data** on the
page, with the alert typed under **What looks wrong?** — the product path, rehearsed on a
world whose answer is known. Any other CSV works the same way; these are the ones ADII was
built and tested on.

Generated, not authored: the source of truth is `02_src/adii/examples/specimens.py`, and
`python -m adii.examples.specimens --csv 01_data/demo/csv` rewrites this folder from it. A
test holds the two together, and another reads every file back through the tool layer's
world builder (`02_src/adii/tools/user_world.py`) and finds the same tables and rows.
These carry no evaluation claim: a run over them is a development run, like a run on the
specimen itself.
