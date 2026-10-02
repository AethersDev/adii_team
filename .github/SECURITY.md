# Security

ADII is research code: a reference implementation that runs locally. It is not a hosted
service and has no production deployment.

## Reporting a problem

Report security problems privately, through the repository's **Security** tab →
**Report a vulnerability**. Please do not open a public issue for them.

Most relevant here: anything that lets the investigator reach data outside the tool layer,
write outside its permitted paths, read an answer key, or carry an API key into a run record.

## What gets fixed

Fixes go to `main`. The tagged states the paper cites (`freeze-*`, `paper-v1`) are frozen
evidence and are never changed; a fix to one of them is a new tag.

This is a small research team without a security response service. We will acknowledge a
report as soon as we can.
