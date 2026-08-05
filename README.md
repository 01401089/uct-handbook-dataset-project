# UCT Handbook Dataset Project

Structured extraction of academic offerings and fees from University of Cape Town
faculty handbooks, to analyse changes in credit load and the associated fee
implications across faculties and across years.

## Objective

UCT has been undergoing a major re-think of curriculum credit loads, with some
changes already implemented. This repository converts the published faculty
handbooks (PDF) and the student fees handbook into relational tables so that:

1. Every degree programme's curriculum (courses, credits, NQF levels, per year of
   study) is captured as data.
2. An **"ideal student"** — a deterministic, documented selection of courses per
   programme-year, including a defensible treatment of electives — can be costed
   in credits and Rand.
3. When multiple years of handbooks are supplied, credit-load and fee trends can
   be compared across editions.

2025 handbooks are currently loaded; the pipeline is designed so additional years
are simply dropped into the raw folder and re-run.

## Repository layout

```
uct-handbook-project/
├── faculty-handbooks-undergraduate/   # RAW input PDFs (never edited)
│   ├── 2025-com-ug.pdf                #   convention: YYYY-<fac>-ug.pdf
│   └── 2025-_fees.pdf                 #   convention: YYYY-_fees.pdf
├── common/                            # shared parsing utilities (all faculties)
├── extractors/                        # ONE extractor package PER faculty
│   ├── com/   ├── ebe/   ├── fhs/
│   ├── hum/   ├── law/   ├── sci/
│   └── fees/                          # fees handbook extractor
├── data/
│   ├── interim/                       # per-page text dumps, intermediate JSON (gitignored)
│   └── processed/                     # final output tables (CSV, versioned in git)
├── validation/                        # cross-check scripts and exception reports
├── analysis/                          # trend analysis once >1 year is loaded
└── docs/                              # design notes and per-faculty review docs
```

Faculty codes: `com` Commerce, `ebe` Engineering & the Built Environment,
`fhs` Health Sciences, `hum` Humanities, `law` Law, `sci` Science.

**Why one extractor per faculty:** the faculties present curricula differently
(Commerce/EBE publish explicit per-year tables per specialisation; Humanities and
Science define majors plus composition rules). Extraction logic is therefore
faculty-specific by design; only genuinely shared code (course-code grammar,
credit-line parsing, PDF-to-text) lives in `common/`.

## The main dataset (single source of truth)

**`data/processed/main_dataset.csv`** — one row per specialisation ×
study-year × course-slot, joining degree, credit, course and fee information,
with an **`ideal_student`** boolean marking the rows a deterministic "ideal
student" takes (electives resolved by documented rules). Everything else is a
building block or a check against it. All tables carry a `year` column so
multiple handbook editions coexist side by side.

| Table | Grain | Purpose |
|---|---|---|
| `main_dataset` | specialisation × study-year × course-slot | **single source of truth** incl. `ideal_student` flag |
| `ideal_student_summary` | specialisation × study-year | computed credits + cost vs stated/published values |
| `specialisations` | one row per plan/specialisation code | degree + specialisation register (73 in COM 2025) |
| `curriculum` | one row per course-slot per spec-year | the curriculum tables as data |
| `curriculum_totals` | one row per spec-year | handbook-stated total credits (validation anchor) |
| `courses` | one row per course | catalogue: credits, NQF level, convener, requirements |
| `course_fees` | one row per course code | Rand fee from fees book §12 |
| `programme_fees_published` | one row per programme-year | published "typical" annual fee from fees book §11 |

Pipeline (run from the repo root, in order):

```bash
python -m extractors.fees.extract --year 2025
python -m extractors.com.extract --year 2025
python build_main_dataset.py --year 2025
python validation/validate.py --year 2025
```

See [docs/commerce-review-and-proposal.md](docs/commerce-review-and-proposal.md)
for the design and [docs/REPLICATION.md](docs/REPLICATION.md) for the detailed
process log, hazard catalogue, and how to add future handbook years.

## Baseline

The git tag **`baseline-2025`** marks the dataset built from the 2025
handbooks — the **initial state before further credit re-think editions are
introduced**. 2025 validation: 217/266 spec-years reconcile credits exactly
with the handbook's stated totals; median fee delta vs published programme
fees is 0.0%; every remaining discrepancy is listed in `validation/` with
provenance.

## Key identifiers

- **Plan / specialisation / major code** (e.g. `CB004FTX04`): the indivisible
  marker of a full degree programme. First 5 characters = programme code
  (`CB004`), last 5 = department/stream code (`FTX04`). In Science and
  Humanities these are majors with prefixes like `SB001`/`HB001` + department
  code (e.g. `HB001SOC01`).
- **Course code** (e.g. `ACC1006F`): 3-letter department + level digit + 3-digit
  distinguisher + period suffix (`F` first semester, `S` second semester,
  `W` whole year, `H` year-long half-course, `Z` non-standard, `P/U/L`
  summer/winter terms).

## Getting started

```bash
pip install -r requirements.txt
```

Current status:

- [x] Repo scaffold, Commerce handbook review, schema proposal
- [x] `extractors/fees` — course fee table + published programme fees
- [x] `extractors/com` — 73 specialisations, curricula, course catalogue
- [x] `build_main_dataset.py` — main dataset with `ideal_student` flag
- [x] `validation` — credit totals + fee cross-checks (tag `baseline-2025`)
- [ ] Remaining faculties: EBE, LAW, FHS, then SCI, HUM
- [ ] Multi-year loading and trend analysis
