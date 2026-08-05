# Provenance

**This is a vendored snapshot, not the living copy.** The canonical source is the
`speciq-prd-skill` repo, owned by Beverly Armstrong and Courtney Cleaver — see that
repo's `README.md` and `CONTRIBUTING.md` for how changes are made there (branch off
`dev`, PR, with a required backlog-update + version-history row + test-PRD run per
change).

Do not edit the files in this directory expecting changes to sync back — they won't.
If Fathom needs a behavior change in this skill, make it in the source repo through
their process, then re-vendor here.

- **Vendored from:** `speciq-prd-skill` (main branch)
- **Vendored on:** 2026-07-30 (matches that repo's most recent version-history entry
  as of this snapshot)
- **What's included:** the shipped skill payload only — `SKILL.md`, `generate-prd.js`,
  `prd-content.js`, `scorecard-config.js`, `scripts/`, `assets/`. Their `docs/`
  directory (backlog, roadmap, mockups, brand reference) is internal planning for
  that team and isn't part of the installable skill, so it isn't vendored here.

## To re-vendor a newer version

Pull the latest shipped payload from their repo, replace this directory's contents
(minus this file), and update the "Vendored on" date above to match their latest
version-history entry.
