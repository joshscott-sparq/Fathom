# Skills

Standalone Claude Skills that pair well with Fathom without being part of it —
loosely coupled, not merged. A skill in here isn't imported by any Fathom code; it's
a tool you drop into a Claude session/Project to do something Fathom itself doesn't
do, usually upstream of Fathom's own pipeline (Fathom's job starts once a PRD and
client context already exist).

## Convention

Each skill lives in its own subdirectory: `skills/<skill-name>/`, laid out exactly as
an installable Claude Skill package (a `SKILL.md` plus whatever code/assets it needs).
That means any skill in here can be zipped up and dropped into Claude Skills settings
or a Project directly.

Each skill's directory should carry a short `PROVENANCE.md` noting:
- where it's actually maintained (its own repo, if it has one)
- whether this is a vendored snapshot or the living copy
- when it was last synced, if vendored

## Adding a skill

1. `mkdir skills/<skill-name>` and drop in the skill payload (not the maintaining
   team's own internal planning docs, backlog, or roadmap — just what would ship in
   the installable skill).
2. Add a `PROVENANCE.md` per the convention above.
3. Add a line to the table below.

## What's here

| Skill | What it does | Source of truth |
|---|---|---|
| [`spec-iq`](spec-iq/) | Generates a formatted, pre-filled PRD `.docx` from source material (meeting notes, transcripts) or a live interview, with gap/conflict flagging and a readiness scorecard. Useful as a front door into Fathom: a well-structured PRD (Fathom already ingests `.docx`) extracts more cleanly than raw notes. | Vendored snapshot — maintained in its own repo; see `spec-iq/PROVENANCE.md`. |
