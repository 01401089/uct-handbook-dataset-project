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
3. Credit-load and fee trends can be compared across handbook editions — and
   against what the **faculty rules** say each whole degree must total
   (the rules layer, `degree_rules.csv`).

**Current coverage: all six faculties (Commerce, EBE, Law, Health Sciences,
Science, Humanities) + Fees for 2021–2026** — six editions, 24,536
main-dataset rows across 1,066 register entries (specialisations and
majors). The credit re-think is visible in the data from both directions:
in the curriculum tables (e.g. BCom Actuarial Science year 1 drops from 185
to 180 credits at the 2024 edition) and in the printed degree rules
(BBusSc minimum 623→528 credits at 2025, EBE's 4-year minimum 576→560 at
2026, undergraduate LLB 660→637 at 2026). In Science and Humanities the
curriculum unit is the **major** (a BSc/BA/BSocSc student combines majors
under composition rules), so their credit anchors are degree-level rather
than per-year — see caveat 8 of the user manual.

## Quick start

```bash
pip install -r requirements.txt
python run_pipeline.py --years all
```

The batch runner discovers every year with a fees PDF plus a Commerce PDF in
`faculty-handbooks-undergraduate/`, then per year runs the fees extractor,
**every faculty extractor whose PDF is present** (com, ebe, law, fhs, sci,
hum), main-dataset assembly and validation; afterwards it builds the
**final-clean layer** for all loaded years (resolution rules + adjudication
registers → `main_dataset_final.csv` → final validation). Writers are
**merge-by-year and merge-by-faculty-within-year**: re-running one
extractor replaces exactly its own faculty's rows for that year and leaves
everything else byte-identical, so pipeline runs are reviewable as small
git diffs.

Individual steps can also be run per year:

```bash
python -m extractors.fees.extract --year 2025
python -m extractors.com.extract --year 2025   # likewise ebe/law/fhs/sci/hum
python build_main_dataset.py --year 2025
python validation/validate.py --year 2025
python build_final_dataset.py --year 2025
python validation/validate_final.py --year 2025
```

## Repository layout

```
uct-handbook-project/
├── faculty-handbooks-undergraduate/   # RAW input PDFs (immutable)
│   ├── YYYY-com-ug.pdf                #   faculty books: YYYY-<fac>-ug.pdf
│   └── YYYY-_fees.pdf                 #   fees books:    YYYY-_fees.pdf
├── run_pipeline.py                    # batch runner (all years / range / list)
├── build_main_dataset.py              # assembles the single source of truth
├── build_final_dataset.py             # final-clean layer (rules + registers)
├── common/                            # shared engine + utilities
│   ├── handbook_parser.py             #   faculty-configurable parsing engine
│   └── degree_rules.py                #   rules-layer extractor (degree minima)
├── extractors/                        # ONE config/extractor package PER faculty
│   ├── com/ ebe/ law/                 #   shared-engine configs (2021-2026)
│   ├── fhs/ sci/ hum/                 #   bespoke parsers (2021-2026)
│   └── fees/                          #   fees handbook (2021-2026)
├── resolutions/                       # per-faculty adjudication registers
├── data/
│   ├── interim/                       # per-page text dumps (gitignored)
│   └── processed/                     # output tables, all years side by side (committed)
├── validation/                        # validate.py + per-year exception reports
├── analysis/                          # trend analysis (next phase)
└── docs/
    ├── USER-MANUAL.md                 # manual for reviewers / deans
    ├── REPLICATION.md                 # detailed process log + hazard catalogue
    ├── FINAL-DATASET-METHOD.md        # final-layer rule taxonomy + register
    └── commerce-review-and-proposal.md  # original design document
```

## The datasets: as-printed and final-clean

The data comes in two layers. The **as-printed layer** records exactly what
the handbooks print, defects included, for audit and replication. The
**final-clean layer** resolves those defects through documented rules and a
reviewable adjudication register — *analysts should use the final tables*:

| Table | Grain | Purpose |
|---|---|---|
| **`main_dataset_final`** | specialisation × study-year × course-slot | **final-clean dataset for analysis** — as-printed columns + `final_included`, resolution class/ref, notes |
| **`ideal_student_summary_final`** | specialisation × study-year | final credits + cost with status, confidence, and written rationale |
| `main_dataset` | specialisation × study-year × course-slot | as-printed single source of truth incl. `ideal_student` flag |
| `ideal_student_summary` | specialisation × study-year | as-printed credits + cost vs stated/published values |
| `specialisations` | one row per plan/specialisation/major code per year | degree + specialisation register |
| `degree_rules` | one row per printed rule statement | the **rules layer**: degree minimum credits, durations, stream totals, composition rules — with rule ref, page and verbatim quote |
| `curriculum` / `curriculum_totals` | course-slots / stated totals | the curriculum tables as data |
| `courses` / `course_fees` / `programme_fees_published` | catalogue / fees | supporting joins |

Discrepancy resolution (rule order, evidence requirements, worked examples):
[docs/FINAL-DATASET-METHOD.md](docs/FINAL-DATASET-METHOD.md). Case-by-case
adjudications live in per-faculty registers
(`resolutions/<faculty>.csv`) with written rationale and PDF page evidence;
Commerce's ([resolutions/com.csv](resolutions/com.csv)) is the only seeded
one so far.

## Data quality at a glance (2021–2026, final layer)

Consistent / resolved / unresolved per faculty; Science and Humanities
major-years carry `no_anchor` (majors print no per-year totals — their
anchors are the degree-level rules):

| Year | COM | EBE | LAW | FHS | SCI | HUM |
|---|---|---|---|---|---|---|
| 2021 | 227 / 17 / 30 | 85 / 0 / 5 | 11 / 0 / 1 | 7 / 0 / 12 | 66 no-anchor | 89 no-anchor |
| 2022 | 240 / 11 / 24 | 86 / 0 / 4 | 11 / 0 / 1 | 8 / 0 / 11 | 66 no-anchor | 88 no-anchor |
| 2023 | 225 / 15 / 36 | 88 / 0 / 2 | 11 / 0 / 1 | 14 / 0 / 11 | 60 no-anchor | 88 no-anchor |
| 2024 | 203 / 13 / 55 | 86 / 0 / 4 | 10 / 0 / 2 | 14 / 0 / 11 | 63 no-anchor | 91 no-anchor |
| 2025 | 219 / 13 / 36 | 84 / 0 / 6 | 10 / 0 / 2 | 11 / 0 / 12 | 66 no-anchor | 91 no-anchor |
| 2026 | 202 / 11 / 48 | 80 / 0 / 10 | 7 / 0 / 0 | 10 / 0 / 13 | 66 no-anchor | 87 no-anchor |

Across 3,287 specialisation-years: **1,949 consistent, 80 resolved by
rules/adjudications, 337 unresolved** (flagged at low confidence, carried at
the computed value, enumerated with suggested actions in
`validation/pending_adjudication_<year>.csv`) and **921 `no_anchor`**
Science/Humanities major-years. Commerce's register has been provisionally
seeded; the EBE, LAW and FHS adjudication passes are pending (DEV-TODO.md)
— though the August 2026 engine refinements (hazards H37–H40) resolved most
of what those passes had queued: EBE went from 344/185
consistent/unresolved to 509/31, and LAW's legacy five-year stream turned
out to print totals in an unrecognised wording and now reconciles to its
printed 660-credit stream total (7 spec-years remain, where the 2024/2025
editions genuinely drop discontinued rows). FHS's unresolved rows are
dominated by the combined Audiology / Speech-Language block, whose
interleaved sub-tables need a dedicated splitter. The MBChB reconciles all
six years exactly, with years 1–3 fees matching published figures to the
rand. Computed fees reconcile at **median delta 0.0%** for COM, EBE and
FHS; LAW publishes one flat annual fee per stream (`flat_annual`) and
SCI/HUM one fee per degree covering every major (`degree_flat`), so their
per-year comparisons legitimately diverge. As-printed handbook defects are
preserved in the base layer and resolved — never silently corrected — in
the final layer. A third validation leg
(`validation/degree_check_<year>.csv`) reconciles each specialisation's
whole-degree credit sum against the rules layer.

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
  assumed). A Word copy for circulation sits alongside it, regenerated from
  the markdown by `docs/make_user_manual_docx.js`.
- **[docs/REPLICATION.md](docs/REPLICATION.md)** — the authoritative process
  log: pipeline details, per-edition layout contracts, the 40-entry hazard
  catalogue (H1–H40), the shared-engine / bespoke-parser architecture, and
  the procedure for onboarding new years and faculties.
- **[docs/FINAL-DATASET-METHOD.md](docs/FINAL-DATASET-METHOD.md)** — how the
  final-clean layer resolves discrepancies: the rule taxonomy
  (R0/R3/R1/R2/R4), the adjudication registers, worked examples.
- **[docs/commerce-review-and-proposal.md](docs/commerce-review-and-proposal.md)**
  — the original Commerce review and design document.

## Status

- [x] Repo scaffold, Commerce handbook review, schema proposal
- [x] `extractors/fees` + `extractors/com` — six editions each (2021–2026)
- [x] `build_main_dataset.py` — main dataset with `ideal_student` flag
- [x] `validation` — credit totals + fee cross-checks, per-year reports
- [x] Batch processing (`run_pipeline.py`) with merge-by-year writers
- [x] User manual for reviewers/deans
- [x] Final-clean layer: rules engine + adjudication register + final validation
- [x] EBE extractor (2021–2026) on the shared engine (`common/handbook_parser.py`)
- [x] LAW extractor (2021–2026): LLB streams incl. level-based totals and
      flat-annual published fees
- [x] FHS extractor (2021–2026): bespoke parser (multi-code blocks,
      trailing totals, six-year MBChB) reusing the shared grammar
- [x] SCI + HUM extractors (2021–2026): bespoke parsers with the **major**
      as the curriculum unit; `no_anchor` status; degree-flat fee matching
- [x] Rules layer: `degree_rules.csv` + whole-degree validation
      (`degree_check_<year>.csv`) across all six faculties
- [ ] Review of the 44 provisional COM adjudications; EBE + LAW + FHS
      adjudication passes (`DEV-TODO.md` documents the workflow)
- [ ] Composed-degree ideal student for SCI/HUM (majors + electives to the
      degree minimum, via the composition rules in `degree_rules.csv`)
- [ ] Trend analysis across editions (`analysis/`)

Git tags: `baseline-2025` (the pre-change initial state) and
`data-2021-2026` (the multi-year load).
