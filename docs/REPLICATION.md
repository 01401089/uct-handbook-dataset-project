# Replication Log — 2025 Baseline

This document records, in full detail, how the 2025 dataset was produced, so
the process can be repeated for future handbook years and audited later.

> **Baseline statement.** The 2025 handbooks represent the **initial state**
> of UCT's academic offerings **before** further credit-load re-think editions
> are introduced. The git tag `baseline-2025` marks the commit that produced
> this state. All later handbook years are loaded *alongside* (every table has
> a `year` column) and compared *against* this baseline.

---

## 1. Environment

- Windows 11, Python 3.12 (any 3.10+ should work)
- `pip install -r requirements.txt` (pdfplumber, pypdf, pandas, openpyxl)
- All commands run from the repository root.

## 2. Inputs

Raw PDFs live in `faculty-handbooks-undergraduate/` and are **immutable**:

| File | Content |
|---|---|
| `2025-com-ug.pdf` | Faculty of Commerce UG handbook (303 pp) |
| `2025-_fees.pdf` | Student Fees handbook (154 pp) |
| `2025-{ebe,fhs,hum,law,sci}-ug.pdf` | remaining faculties (extractors pending) |

Convention for future years: `YYYY-<fac>-ug.pdf`, `YYYY-_fees.pdf`. Drop the
files in, never rename or edit existing ones.

## 3. Pipeline (exact commands, in order)

```bash
python -m extractors.fees.extract --year 2025
python -m extractors.com.extract --year 2025
python build_main_dataset.py --year 2025
python validation/validate.py --year 2025
```

Each step is deterministic and re-runnable; interim page dumps go to
`data/interim/` (gitignored), outputs to `data/processed/` (committed), and
exception reports to `validation/` (committed). `--skip-dump` reuses an
existing page dump during development.

### Step 1 — fees extractor (`extractors/fees/extract.py`)

Section boundaries are found by full-line heading matches ("11. UCT ACADEMIC
FEES", "12. UCT ACADEMIC COURSES", "13. RESIDENCES") — full-line, because the
table of contents contains the same text with dotted leaders.

- **§12 course fees** → `course_fees.csv`. Row grammar
  `CODE TITLE 10,440`. 2025 yield: 4,496 rows, 4,495 distinct codes, zero
  conflicting fees; 483 exact reprint duplicates dropped; 1 line unparseable
  (see Hazards H13) and recovered via `extractors/fees/overrides.py`.
- **§11 published programme fees** → `programme_fees_published.csv`.
  The printed layout interleaves margin notes with fee rows, so a state
  machine applies these rules: subsection 11.1 (fee *ranges*) is skipped;
  a text buffer becomes a programme label only when a "1st Year" row arrives;
  buffered text before later-year rows is margin noise (kept as
  `margin_note`); stream sub-labels without a degree keyword inherit the last
  degree-bearing label; dotted single-line fees keep `study_year` empty; year
  rows arriving with an empty buffer directly after a dotted fee belong to
  that dotted programme (part-time PG blocks). 2025 yield: 525 rows.

### Step 2 — Commerce extractor (`extractors/com/extract.py`)

Pages are classified by their running-header line ("RULES FOR ADVANCED
DIPLOMAS" / "PROGRAMMES OF STUDY" → programme parsing; "DEPARTMENTS IN THE
FACULTY..." / "FACULTIES AND DEPARTMENTS..." → course catalogue).

**Programme blocks.** A specialisation starts at a `[PLANCODE]` line (or an
inline Advanced-Diploma heading). The 1–2 title lines above it are
reconstructed by walking back to a line starting "Bachelor of…"/"Advanced
Diploma…". Umbrella lines ("Bachelor of Commerce Augmented", "… Extended
Academic Development") set the `variant` for subsequent blocks. Plan codes are
normalised (O→0, zero-padding) — see Hazards H1.

**Curriculum tables.** Inside a block, "(First…Fifth) Year Core Modules"
headings open year tables; repeated headings for the same year get
`table_index` 2+ (kept, never ideal). Row grammar and structures handled:

| Structure | Example | Encoding in `curriculum.csv` |
|---|---|---|
| Core row | `ACC1006F Financial Accounting … 18 5` | `requirement=core` |
| OR pair (line or trailing "OR") | `INF1002F … OR / CSC1015F …` | shared `choice_group`, `choice_member` 1..k, `choice_pick_n=1` |
| AND bundle inside a choice | `CSC2001F AND CSC2002S OR …` | same `choice_member` for bundled rows |
| Named option blocks | `Mathematical Statistics Option:` vs `Applied Statistics Option:` | one group, member per block, pick 1 |
| Pick-n menu | `Plus 2 courses from:` + rows | member per row, `choice_pick_n=n` |
| 4th-year sub-blocks | `Core courses (…):` / `Elective Courses:` + "take two options" | core rows + menu with instructed pick |
| Elective slot with credits | `Four electives at NQF level 6 … 72 6` | `requirement=elective` |
| Elective slot, credits elsewhere | `PLUS one elective at 1st year level …` | credits blank → inferred in assembly |
| Open elective minimum | `Any NQF level 7 electives … minimum of 120 credits` | `is_minimum=True` |
| Stated total | `Total credits per year … 159` (also `+168`, `144+`, `>=126`, prose "The total credits for year 2 equals 186.") | `curriculum_totals.csv`; prose form never overwrites an inline total |

2025 yield: **73 specialisations** (33 BBusSc, 34 BCom, 3 AdvDip; 27 regular,
23 augmented, 23 extended), 2,323 curriculum rows, 268 stated totals.

**Course catalogue.** Entries recognised as `CODE TITLE` (≥60% uppercase
title) confirmed by an `NN NQF credits at NQF level N` line within 4 lines;
labelled fields (Convener / Course entry requirements / Course outline /
Lecture times / DP requirements / Assessment) accumulate until the next
entry. 2025 yield: 307 courses.

### Step 3 — assembly (`build_main_dataset.py`)

Produces **`main_dataset.csv`** — the single source of truth: one row per
specialisation × study-year × course-slot carrying degree, credit, course,
fee and provenance columns plus the **`ideal_student`** boolean.

Ideal-student rules (deterministic):
1. `core` rows → taken.
2. `option` rows → taken iff `choice_member <= choice_pick_n`.
3. `elective` slots → taken; blank credits inferred as
   `stated_year_total − sum(other ideal rows)` when exactly one blank slot
   exists (`credits_inferred=True`).
4. `alternative` rows and `table_index > 1` rows → never taken.
5. Fees: exact course-code match first; then suffix-variant fallback
   (`MAM1010`→`MAM1010F`, `BUS4050W`→`BUS4050H`), recorded in `fee_source`;
   elective slots get `median same-level fee × slot_credits/18`, flagged
   `estimated_median`.

Published-fee matching: labels are parsed to (degree, AD?, normalised
specialisation) with an alias table for renames ("Analytics" → "Statistics
and Data Sciences", "Finance (Non CA Option)" → "Finance, Investment and
Banking", …); postgraduate labels are excluded. Academic-Development fees are
published once per specialisation — the block's year-count decides which AD
variant it prices (5 year-rows → the 5-year extended BBusSc), method recorded
as `ad_duration`/`ad_shared`.

Also produces **`ideal_student_summary.csv`**: per specialisation-year
credits and cost vs the handbook's stated total and the published fee.

### Step 4 — validation (`validation/validate.py`)

Writes `credit_check_2025.csv`, `fee_check_2025.csv`, `missing_fees_2025.csv`.

**2025 baseline results:**

| Check | Result |
|---|---|
| Credit reconciliation | **217 OK** / 33 MISMATCH / 16 UNRESOLVED_SLOTS (of 266) |
| Fee reconciliation (5% tolerance) | **131 OK** / 49 MISMATCH (of 180 matched) |
| Ideal-student courses without a fee | **0** |
| Median fee delta vs published | **0.0%** |

The MISMATCH rows are *findings, not failures*: most are the handbook's own
arithmetic (totals that count both OR branches, exclude a listed row, or a
typo like the 382-for-182 stated total on CB025BUS09 year 1) or final-year
tables whose choice rule is printed nowhere (the CSC 4th-year menu). They are
preserved verbatim in the dataset and listed in the exception reports for the
analysis team; decisions to pin them are made in per-extractor `overrides`
files with written rationale, never by editing outputs.

## 4. Hazard catalogue (all confirmed in 2025 sources)

| # | Hazard | Example | Handling |
|---|---|---|---|
| H1 | Plan-code typos in TOC | `CBO18BUS01` (O for 0), `CB25BUS09` (9 chars) | trust body heading; normalise O→0, zero-pad |
| H2 | Split words from PDF extraction | `C omputer Science` | match on codes, not titles |
| H3 | Stray symbols in totals | `+168`, `144+`, `>=126` | tolerated; `+`/`>=` sets `is_minimum` |
| H4 | Composite course codes | `STA2020F/S`, `CML1001F/1004S`, `ECO1011FS` | resolve to first-listed variant |
| H5 | Suffixless codes | `MAM1010` | fee fallback tries F/S/W/H/Z variants |
| H6 | Credits glued to title/dots | `…Research** ……142 8`, `…Report60 8` | separator `[\s.…]*` before credits |
| H7 | Wrapped elective lines | "Plus ECO2008S and 1 NQF level 6 course …" / "… 18+ 7" | credits continuation line fills the slot |
| H8 | Zero-credit courses | `CSC2004Z Programming Assessment 0 6` | allowed |
| H9 | Prose totals as remnants | "The total credits for year 2 equals 186." after an unrelated table | fill-only, never overwrite |
| H10 | Handbook arithmetic quirks | total counts both OR branches (CB004INF01 y1) | surfaced in credit_check, not "fixed" |
| H11 | Stated-total misprint | CB025BUS09 y1 "Total … 382" | exception report; overrides if pinned |
| H12 | Un-labelled choice menus | CSC 4th-year module list | exception report; overrides |
| H13 | Character-interleaved fee rows | p.82 of fees book, two rows merged | de-interleaved via `extractors/fees/overrides.py` |
| H14 | Fees-book code variants | `ACC1011N` (R600 exam-only rows), `X` codes | kept in `course_fees`; costing joins exact codes |
| H15 | PG fee rows bleeding into UG labels | part-time year rows after dotted fees | dotted-label fallback; PG labels excluded from matching |
| H16 | AD fees published once for two variants | 5-year block vs 4-year augmented | duration-aware matching (`ad_duration`) |
| H17 | Specialisation renames between books | fees "Analytics" vs handbook "Statistics and Data Sciences" | alias table in `build_main_dataset.py` |

## 5. Adding a new handbook year (e.g. 2026)

1. Drop `2026-com-ug.pdf` and `2026-_fees.pdf` into
   `faculty-handbooks-undergraduate/`.
2. Run the four pipeline commands with `--year 2026`.
3. Review the console yields against this document's 2025 numbers — big drops
   mean the layout changed; check `validation/*_2026.csv` and the parser's
   "Layout facts" docstring before touching code.
4. New specialisation names or renames → extend `SPEC_ALIASES`;
   genuine print defects → add to the relevant `overrides` file **with the
   reason and source page**.
5. Commit the new processed CSVs (rows are additive — the `year` column keeps
   editions side by side; existing 2025 rows must not change) and tag
   `data-2026`.
6. Trend analysis then compares plan codes across years (`analysis/`).

## 6. Extending to the other faculties

One extractor package per faculty (`extractors/ebe/` etc.), same output
schemas, same pipeline position as `extractors/com/`. Recommended order:
EBE and LAW (Commerce-like curriculum tables), FHS, then SCI and HUM — for
those two the unit of extraction is the *major* (`SB…`/`HB…` plan codes) plus
the degree-composition rules from the faculty rules section, from which the
ideal student's curriculum is constructed rather than read off a table.
