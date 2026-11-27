# Notes for Claude sessions

## Checklist sync (do this at the start of every session)

The Checklist tab of the Sheet "SDS Resources by Section (Sections 4-8)"
(https://claude.ai/artifact/YU3qDgtuqh4mMq5BxX3wHd) is the master copy of the checklist.
`checklist/coverage.csv` is generated from it and must never be edited by hand.

At the start of each session, and whenever the user says they have edited the Sheet:

1. Read the tab's size with the Claude Docs connector (`readSheets`) to find the last filled row N.
2. Read `Checklist!B1:B{N}` and `Checklist!F1:G{N}` (`readCells`), at the same revision.
3. Run `python3 -I tools/sync_checklist.py --from-transcript`. It writes `checklist/sheet_export.json` and
   rewrites `checklist/coverage.csv`; if it stops on a row it cannot read, tell the user which row to fix in
   the Sheet rather than guessing.
4. Run `python3 -I tools/check_coverage.py`. A mismatch means the Sheet's Status column and the engines
   disagree: report it to the user; do not change the Sheet to make it pass.
5. If either file changed, commit both. CI (`sync_checklist.py --check`, then `check_coverage.py`) checks them.

Write to the Checklist tab only with the user's approval of the rows, as before.
