# UCT Handbook Dataset Project

Structured extraction of academic offerings and fees from University of Cape
Town handbooks, to analyse changes in credit load and the associated fee
implications across faculties and across years.

## Objective

UCT has been undergoing a major re-think of curriculum credit loads, with some
changes already implemented. This repository converts the published faculty
handbooks (PDF) and the student fees handbooks into relational tables so that:

1. Every degree programme's curriculum (courses, credits, NQF levels, per year
   of study) is captured as data, with page-level provenance.
2. An **"ideal student"** — a deterministic, documented selection of courses
   per specialisation-year, including a defensible treatment of electives —
   can be costed in credits and Rand.
3. Credit-load and fee trends can be compared across handbook editions.

**Current coverage: Commerce + Fees for 2021–2026** (six editions,
14,282 main-dataset rows). The credit re-think is already visible in the
data — e.g. BCom Actuarial Science year 1 drops from 185 to 180 credits at
the 2024 edition. Other faculties (EBE, FHS, HUM, LAW, SCI) have 2025 books
loaded and extractors pending.

## Quick start

```bash
pip install -r requirements.txt
python run_pipeline.py --years all
```

The batch runner discovers every year with both a Commerce and a fees PDF in
`faculty-handbooks-undergraduate/`, and runs the full pipeline per year
(fees extractor → Commerce extractor → main-dataset assembly → validation).
Writers are **merge-by-year**: re-running a year replaces exactly that year's
rows and leaves every other year byte-identical, so pipeline runs are
reviewable as single-year git diffs.

Individual steps can also be run per year:

```bash
python -m extractors.fees.extract --year 2025
python -m extractors.com.extract --year 2025
python build_main_dataset.py --year 2025
python validation/validate.py --year 2025
```

## Repository layout

```
uct-handbook-project/
├── faculty-handbooks-undergraduate/   # RAW input PDFs (immutable)
│   ├── YYYY-com-ug.pdf                #   faculty books: YYYY-<fac>-ug.pdf
│   └── YYYY-_fees.pdf                 #   fees books:    YYYY-_fees.pdf
├── run_pipeline.py                    # batch runner (all years / range / list)
├── build_main_dataset.py              # assembles the single source of truth
├── common/                            # shared utilities (PDF text, grammar, CSV io)
├── extractors/                        # ONE extractor package PER faculty
│   ├── com/                           #   built (2021-2026)
│   ├── fees/                          #   built (2021-2026)
│   └── ebe/ fhs/ hum/ law/ sci/       #   pending
├── data/
│   ├── interim/                       # per-page text dumps (gitignored)
│   └── processed/                     # output tables, all years side by side (committed)
├── validation/                        # validate.py + per-year exception reports
├── analysis/                          # trend analysis (next phase)
└── docs/
    ├── USER-MANUAL.md                 # manual for reviewers / deans
    ├── REPLICATION.md                 # detailed process log + hazard catalogue
    └── commerce-review-and-proposal.md  # original design document
```

## The main dataset (single source of truth)

**`data/processed/main_dataset.csv`** — one row per specialisation ×
study-year × course-slot, joining degree, credit, course and fee information,
with an **`ideal_student`** boolean marking the rows a deterministic "ideal
student" takes. Everything else is a building block or a check against it.
All tables carry a `year` column so editions sit side by side.

| Table | Grain | Purpose |
|---|---|---|
| `main_dataset` | specialisation × study-year × course-slot | **single source of truth** incl. `ideal_student` flag |
| `ideal_student_summary` | specialisation × study-year | computed credits + cost vs stated/published values |
| `specialisations` | one row per plan/specialisation code per year | degree + specialisation register |
| `curriculum` | one row per course-slot per spec-year | the curriculum tables as data |
| `curriculum_totals` | one row per spec-year | handbook-stated total credits (validation anchor) |
| `courses` | one row per course per year | catalogue: credits, NQF level, convener, requirements |
| `course_fees` | one row per course code per year | Rand fee from the fees book |
| `programme_fees_published` | one row per programme-year | published "typical" annual fee |

## Data quality at a glance (2021–2026)

| Year | Specialisations | Curriculum rows | Credit check OK | Published-fee coverage |
|---|---|---|---|---|
| 2021 | 71 | 2,434 | 218/269 | 164/269 |
| 2022 | 69 | 2,468 | 216/261 | 160/261 |
| 2023 | 71 | 2,491 | 209/265 | 158/265 |
| 2024 | 72 | 2,318 | 181/255 | 178/255 |
| 2025 | 73 | 2,323 | 217/266 | 180/266 |
| 2026 | 70 | 2,248 | 199/258 | 172/258 |

Every discrepancy is itemised with page provenance in `validation/`; most
"mismatches" are the handbooks' own arithmetic quirks, preserved rather than
silently corrected (see the user manual's caveats section).

## Key identifiers

- **Plan / specialisation / major code** (e.g. `CB004FTX04`): the indivisible
  marker of a full degree programme. First 5 characters = programme code
  (`CB004`), last 5 = department/stream code (`FTX04`). In Science and
  Humanities these are majors with prefixes like `SB001`/`HB001` + department
  code (e.g. `HB001SOC01`).
- **Course code** (e.g. `ACC1006F`): 3-letter department + level digit +
  3-digit distinguisher + period suffix (`F` first semester, `S` second,
  `W` whole year, `H` year-long half-course, `Z` non-standard, `P/U/L`
  summer/winter terms).

## Documentation

- **[docs/USER-MANUAL.md](docs/USER-MANUAL.md)** — for reviewers and deans:
  what the dataset contains, how to read it, the ideal-student definition,
  validation results, caveats, and how to query it (no technical background
  assumed). A Word copy for circulation sits alongside it.
- **[docs/REPLICATION.md](docs/REPLICATION.md)** — the authoritative process
  log: pipeline details, per-edition layout contracts, the 21-entry hazard
  catalogue, and the procedure for onboarding new years and faculties.
- **[docs/commerce-review-and-proposal.md](docs/commerce-review-and-proposal.md)**
  — the original Commerce review and design document.

## Status

- [x] Repo scaffold, Commerce handbook review, schema proposal
- [x] `extractors/fees` + `extractors/com` — six editions each (2021–2026)
- [x] `build_main_dataset.py` — main dataset with `ideal_student` flag
- [x] `validation` — credit totals + fee cross-checks, per-year reports
- [x] Batch processing (`run_pipeline.py`) with merge-by-year writers
- [x] User manual for reviewers/deans
- [ ] Remaining faculties: EBE, LAW, FHS, then SCI, HUM
- [ ] Trend analysis across editions (`analysis/`)

Git tags: `baseline-2025` (the pre-change initial state) and
`data-2021-2026` (the multi-year load).
