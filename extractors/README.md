# Extractors

One package per faculty (`com`, `ebe`, `fhs`, `hum`, `law`, `sci`) plus `fees`
for the student fees handbook.

Faculty handbooks that follow the university's common publisher template
(COM, EBE — likely LAW/FHS too) are parsed by the **shared engine**
`common/handbook_parser.py`; the faculty package then contains only a
`FacultyConfig` (plan-code grammar, degree parser, heading variants, page
classification, department map) plus any parse-time `overrides`. Faculties
whose books don't fit the template (expected: SCI, HUM) write their own
parser in their package instead.

Each extractor package provides:

- `extract.py` — entry point (`python -m extractors.<fac>.extract --year Y`):
  a FacultyConfig + `run_extractor(...)` call, or a bespoke parser with the
  same outputs.
- `overrides.py` (or `.csv`) — explicit, reviewable corrections for parse
  artifacts (never hand-edit outputs; print errors go to `resolutions/`).
- Hazard notes belong in docs/REPLICATION.md.

Status: `fees`, `com`, `ebe` built (2021-2026); `law`/`fhs` next, then
`sci`/`hum`.
