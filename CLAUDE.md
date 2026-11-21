# Store Coach — hackathon project (Manyavar statement, VCH3, 21 Nov 2026)

**Read first, every session:** `planning/PLAN.md` (steps, status, output contract,
watch-outs) and `planning/KNOWLEDGE_LOG.md` (rules, data facts, findings, decisions).

## Session rules
- Do only the step the user names. Edit only that step's files (listed in PLAN.md).
- Check the time (`date +%H:%M`) at the start. **No commits or pushes after 4:45 pm; aim for the last push by 4:30 pm.**
- Never commit `*.zip`, `*.pdf`. `data/raw/*.csv` IS committed (D1, since Step 6 — the daily Action needs it). Never push branch `old-main`.
- Stage only your own files (`git add <paths>`), not `git add -A`. One commit per finished step: "Step N: …".
- Numbers come from code, never from guesses. If a number changes from KNOWLEDGE_LOG §3, say why.
- At the end of the step: set its row in the PLAN.md Status table, append to KNOWLEDGE_LOG §5 (clarifications), §4 (decisions) and §7 (step log).
- Clarifications the user gives that matter beyond this chat go into KNOWLEDGE_LOG §5.

## Data
- Raw CSVs: `data/raw/*.csv` (committed, D1). If missing, unzip `manyavar-vch3-data.zip` (`csv/*`) into `data/raw/`.
- Load with `storecoach.load.load()` — IDs stay text.
