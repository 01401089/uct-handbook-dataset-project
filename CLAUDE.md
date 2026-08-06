# CLAUDE.md

Guidance for working in this repository.

## What this project is

Extract structured data from UCT faculty handbooks (PDF) and the student fees
handbook into relational CSV tables, to analyse credit-load changes and their fee
implications across faculties and handbook years. UCT is re-thinking curriculum
credit loads; this dataset measures the change. **The 2025 books are the
baseline — the initial state before credit re-think editions arrive** (git tag
`baseline-2025`). More years will be added later, so **every output table
carries a `year` column** and existing years' rows must never change when a new
year is loaded.

## Pipeline

```
python run_pipeline.py --years all      # batch: fees -> com -> assemble -> validate
```

or per year / per step:

```
python -m extractors.fees.extract --year YYYY
python -m extractors.com.extract  --year YYYY
python build_main_dataset.py      --year YYYY
python validation/validate.py     --year YYYY
```

COM + fees are loaded for **2021-2026**. Writers are merge-by-year
(`common/csv_io.py`): re-running a year replaces only that year's rows —
after any parser change, verify prior years' rows are byte-identical (the
2025 baseline especially). `data/processed/main_dataset.csv` is the
**as-printed single source of truth**: one row per specialisation x
study-year x course-slot with degree, credit, course and fee columns and an
`ideal_student` boolean. `main_dataset_final.csv` /
`ideal_student_summary_final.csv` are the **final-clean layer** built by
`build_final_dataset.py` (step 5) and checked by
`validation/validate_final.py` (step 6) — see
`docs/FINAL-DATASET-METHOD.md` for the rule taxonomy (R0/R3/R1/R2/R4).

**Final-layer ground rule:** never "fix" a handbook print error in an
extractor or an as-printed output. Parse artifacts (PDF prints right, we
read wrong) go in extractor `overrides`; print errors/ambiguities get a row
in `resolutions/com.csv` with rationale + page evidence, applied only in the
final layer. The finaliser fails on stale register entries; detectors R1b/
R2b feed `validation/pending_adjudication_<year>.csv` — check that report
after onboarding any new year. A doubled row-sum (exactly 2x stated) means a
swallowed programme heading — see hazards H22-H24.

`docs/REPLICATION.md` is the authoritative process log: read it (especially
the hazard catalogue H1-H21, which includes per-edition layout drift — 2024
Title-Case/inline-code headings, 2026 per-degree headers and HEQSF wording)
before touching any parser or onboarding a new handbook year.
`docs/USER-MANUAL.md` is the reviewer/dean-facing manual — update it when
tables, rules, or coverage change.

## Ground rules

- **One extractor per faculty.** Faculties present curricula differently; do not
  try to share a parser across faculties. Shared, provably-general helpers
  (course-code regex, credit-line parsing, PDF text dump) go in `common/`;
  everything else lives in `extractors/<fac>/`.
- **Raw PDFs are immutable.** They live in `faculty-handbooks-undergraduate/`
  with the naming convention `YYYY-<fac>-ug.pdf` and `YYYY-_fees.pdf`. Never
  edit or move them; new handbook years are added alongside.
- **Interim vs processed.** Page-level text dumps and intermediate JSON go to
  `data/interim/` (gitignored). Final tables go to `data/processed/` as CSV and
  are committed, so diffs between pipeline runs are reviewable in git.
- **Every extracted row keeps provenance**: `year` (handbook edition) and
  `source_page` (PDF page number) columns, so any value can be traced back and
  hand-checked.
- **Extraction is deterministic and re-runnable.** No manual edits to
  `data/processed/` files; fix the extractor and re-run instead. Where a
  handbook contains a genuine typo that must be corrected, record the correction
  in a per-faculty `overrides` file inside the extractor package, applied at
  parse time, so corrections are explicit and reviewable.

## Domain knowledge (read before parsing anything)

### Plan / specialisation / major codes
`CB004FTX04` style. First 5 chars = **programme code** (`CB004`), last 5 =
**department/stream code** (`FTX04`). This 10-char code is the indivisible key
for a full degree programme:
- COM, EBE, LAW, FHS call it a *specialisation*.
- SCI and HUM call it a *major*; prefixes are typically `SB001`/`HB001` + dept
  code, e.g. `HB001SOC01` = major in Sociology (variations exist).
- Commerce programme-code families observed in 2025: regular (`CB001`, `CB003`,
  `CB004`, `CB019`, `CB025`), Academic Development augmented (`CB023`, `CB026`),
  Academic Development extended (`CB011`, `CB015`, `CB018`, `CB020`).

### Course codes
`ACC1006F` = dept `ACC` + level digit `1` + distinguisher `006` + period suffix.
Suffixes: `F` first semester, `S` second semester, `W` whole-year, `H` half-course
across the year, `Z` non-standard period, `P`/`U`/`L` summer/winter terms.
NQF levels: 5–7 = years 1–3 of a general bachelor's; 8 = professional
4-year degree / honours level.

### Handbook anatomy (Commerce 2025; others vary)
1. Front matter: contacts, term dates, explanation of codes/symbols.
2. Qualifications register: degree name, abbreviation, SAQA ID, minimum duration.
3. Faculty rules (rule codes like `FBA16`) — degree requirements live here.
4. **Programmes of Study**: per plan code, year-by-year curriculum tables with
   columns Code | Course | NQF Credits | NQF Level and a
   "Total credits per year … N" line (use it as a validation anchor, don't sum it).
5. **Departments**: staff lists + course descriptions in a regular format:
   `CODE TITLE` / `NN NQF credits at NQF level N` / Convener / Course entry
   requirements / Course outline / Lecture times / DP requirements / Assessment.
6. Terminology and policies.

### Fees handbook
- §11 "UCT Academic Fees": published **typical annual fee per programme-year**,
  labelled by degree/specialisation *name only* (no plan codes) → requires fuzzy
  name matching to `programmes`.
- §12 "UCT Academic Courses": flat table `COURSE_CODE TITLE FEE` for the whole
  university (UG + PG). Fees have comma thousands separators.

### The "ideal student"
Handbooks allow electives, so annual credit load must be computed from what a
student actually takes, not everything on offer. The deterministic rules (full
rationale in docs/commerce-review-and-proposal.md):
1. Take every core course.
2. In an OR/option group, take the first-listed option; record alternates.
3. For elective placeholders, use the placeholder's stated credits; cost them at
   the median course fee of the pre-approved elective list for that slot (flag
   as estimated).
4. For dual-offering codes (`STA2020F/S`), resolve to the `F` variant.
5. Validate: computed credits vs the stated "Total credits per year"; computed
   cost vs the published programme-year fee in fees §11. Mismatches go to a
   validation exception report, not silently absorbed.

## Known parsing hazards (2025 COM, confirmed by inspection)

- Plan-code typos in the TOC: `CBO18BUS01` (letter O for zero), `CB25BUS09`
  (missing digit). Trust the code printed at the programme body, normalise
  O↔0, and validate length 10.
- Intra-word spacing glitches from PDF text extraction: `C omputer Science`.
- Stray characters in totals lines: `Total credits per year … +168`.
- Composite codes in curriculum rows: `STA2020F/S`, `CML1001F/1004S`.
- Zero-credit courses exist (e.g. `CSC2004Z Programming Assessment`, 0 credits).
- Elective totals are sometimes minimums ("a minimum of 120 credits").
- Fees §12 contains near-duplicate rows per base course (`F`/`S`/`N`/`X`
  variants). `N`-suffixed rows (~R600) appear to be exam-only/completion
  variants — exclude from ideal-student costing (assumption to verify).
- Fees amounts formatted `10,440`; published programme fees formatted
  `R 91 190` (spaces) — parse both.

## Environment

Windows, Python 3.12. Install with `pip install -r requirements.txt`
(pdfplumber, pypdf, pandas, openpyxl). Run scripts from the repo root.
