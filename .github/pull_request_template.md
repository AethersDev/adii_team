## What and why

<!-- One paragraph. What problem does this solve? -->

## Author-understanding gate

A PR is not mergeable until you can answer these **in your own words**. Not line-by-line
memorisation — operational understanding. A perfect generated implementation nobody can
debug is not done.

1. **What problem does this change solve?**
2. **What are its inputs and outputs?**
3. **What important failure modes does it have?**
4. **How did you test it?**
5. **What did a coding agent generate that you had to inspect or correct?**

## Checks

- [ ] CI green on Windows **and** macOS
- [ ] I can give a 2-minute walkthrough of this change on request
- [ ] If this touches `02_src/adii/contracts/`, a cross-boundary reviewer is assigned

## Reviewers

<!-- Domain reviewer for internals. If a contract file changed, add the reviewer whose
     boundary is affected: contracts are the one thing four people share. -->
