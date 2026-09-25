# Evaluation fixtures — development authority only

**Nothing in this directory may be used to claim unseen performance.** Every file here is
team-visible development material: keys for incidents whose worlds are public in this
repository, and drill keys for the scorer's own tests. Unseen keys never enter this
repository; blind incidents are held by a custodian.

| file | incident | authored by | frozen | role |
|---|---|---|---|---|
| `demo-learning-001.answer.json` (+ `.sha256`) | the walkthrough, `01_data/walkthrough/` | C, 12 Sep; frozen 15 Sep | yes | development key for the one world the validator rebuilds; recovered 21 Sep from commit `ef9c951` — a public teaching fixture's authority, reclassified as a development fixture |
| `demo-learning-002-mismatch-drill.answer.json` | the same world, hypothetical decisions | C, 12 Sep | no | drills the scorer's routing to the judge; a fixture, never scored against a run |
| `revenue-after-deploy.answer.json` (+ `.sha256`) | the specimen `revenue-after-deploy` | the runtime's author, 16 Sep | yes | a smoke of the scoring path, not an independent key — the file says so |
| `synthetic-escalate-001.answer.json`, `synthetic-no-repair-001.answer.json` | none | C | no | scorer fixtures |

Not restored from history, on purpose: `demo-learning-001.grounding.json`. Its required
calls — `get_schema` on `stg_orders`, `run_sql` mentioning `amount_cents` — are not made by
the walkthrough's own trace, so it fails its own evidentiary premise; it stays in history
until the evaluation authority re-authors it against the trace.

The location rule is a test: `test_answer_keys_stay_out` fails the build on key-shaped JSON
anywhere but under `02_src/adii/evaluation/`.
