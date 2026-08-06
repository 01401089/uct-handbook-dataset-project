# Extractors

One package per faculty (`com`, `ebe`, `fhs`, `hum`, `law`, `sci`) plus `fees`
for the student fees handbook. **All seven are built for 2021–2026.**

Faculty handbooks that follow the university's common publisher template
(**COM, EBE, LAW**) are parsed by the **shared engine**
`common/handbook_parser.py`; the faculty package then contains only a
`FacultyConfig` (plan-code grammar, degree parser, heading variants, page
classification, department map) plus any parse-time `overrides`. Faculties
whose books don't fit the template (**FHS, SCI, HUM**) have bespoke parsers
in their packages that reuse the shared grammar and the engine's catalogue
parser — see REPLICATION §7–§9. In SCI and HUM the curriculum unit is the
**major** (`SB001…`/`HB001…` plan codes), not the specialisation.

Each extractor package provides:

- `extract.py` — entry point (`python -m extractors.<fac>.extract --year Y`):
  a FacultyConfig + `run_extractor(...)` call, or a bespoke parser with the
  same outputs. Faculty extractors also run the rules-layer extractor
  (`common/degree_rules.py` → `degree_rules.csv`) after the main parse.
- `overrides.py` (or `.csv`) — explicit, reviewable corrections for parse
  artifacts (never hand-edit outputs; print errors go to `resolutions/`).
- Hazard notes belong in docs/REPLICATION.md.

Shared tables are written merge-by-year AND merge-by-faculty-within-year:
re-running one extractor replaces only its own faculty's rows for that year.
