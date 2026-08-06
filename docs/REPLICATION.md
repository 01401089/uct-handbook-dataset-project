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
python build_final_dataset.py --year 2025      # step 5: final-clean layer
python validation/validate_final.py --year 2025  # step 6: final-layer assertions
```

Steps 1–4 build and check the **as-printed layer** (exactly what the
handbooks print, defects preserved). Steps 5–6 build and check the
**final-clean layer** (`main_dataset_final.csv`,
`ideal_student_summary_final.csv`): discrepancies resolved by the ordered
rule set R0/R3/R1/R2/R4 with the curated register `resolutions/com.csv` —
full method and justification in
[FINAL-DATASET-METHOD.md](FINAL-DATASET-METHOD.md). The batch runner
executes steps 5–6 for **every loaded year** after the per-year loop
(cross-edition rules make the final layer a whole-dataset computation).

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
| H11 | Stated-total misprint | CB025BUS09 y1 "Total … 382" | adjudicated in `resolutions/com.csv` (COM-2025-008), resolved in the final layer |
| H12 | Un-labelled choice menus | CSC 4th-year module list | adjudicated in `resolutions/com.csv` (`accept_stated`), resolved in the final layer |
| H13 | Character-interleaved fee rows | p.82 of fees book, two rows merged | de-interleaved via `extractors/fees/overrides.py` |
| H14 | Fees-book code variants | `ACC1011N` (R600 exam-only rows), `X` codes | kept in `course_fees`; costing joins exact codes |
| H15 | PG fee rows bleeding into UG labels | part-time year rows after dotted fees | dotted-label fallback; PG labels excluded from matching |
| H16 | AD fees published once for two variants | 5-year block vs 4-year augmented | duration-aware matching (`ad_duration`) |
| H17 | Specialisation renames between books | fees "Analytics" vs handbook "Statistics and Data Sciences" | alias table in `build_main_dataset.py` |

## 5. Adding a new handbook year — batch processing

Drop `YYYY-com-ug.pdf` and `YYYY-_fees.pdf` into
`faculty-handbooks-undergraduate/`, then:

```bash
python run_pipeline.py --years all        # or --years 2027, or --years 2021-2027
```

The runner executes fees → com → assemble → validate per year and prints a
yield summary. Writers are **merge-by-year**: re-running a year replaces
exactly that year's rows in the processed CSVs and leaves every other year
byte-identical (verified for the 2025 baseline on every change). Then:

1. Compare the new year's yields to the table in §6 — a large drop means the
   layout changed; check the header families first (Hazards H18-H20).
2. New specialisation names/renames → extend `SPEC_ALIASES`; print defects →
   the relevant `overrides` file **with reason and source page**.
3. Commit the updated CSVs and validation reports; existing years' rows must
   show no diff.

## 6. Commerce yield reference (per-edition, as-printed layer)

Per-edition COM yields for regression comparison when parsers change:
73/74/75/75/73/71 specialisations and 2,434/2,468/2,491/2,318/2,323/2,248
curriculum rows for 2021→2026. Current cross-faculty status lives in §8.
The credit re-think is visible directly, e.g. CB019BUS01 (BCom Actuarial
Science) year 1: 185 credits (2021-2023) → 180 credits (2024-2026), with
computed ideal fees equal to the published fee to the rand in 2021-2025.

Layout drift encountered and handled across editions:

| # | Hazard | Edition | Handling |
|---|---|---|---|
| H18 | Title-Case running headers; catalogue section renamed "Departments offering courses to the Faculty of Commerce" | 2024 | case-insensitive page classification + extra header family |
| H19 | Plan codes printed inline at the end of the title line (Title Case and UPPERCASE) | 2024 | generalised inline-heading rule; case-insensitive degree parsing |
| H20 | Per-degree/per-department running headers ("BACHELOR OF COMMERCE AUGMENTED 15"), no "Programmes of Study" header | 2026 | degree/department header families; variant read from the page header |
| H21 | "NQF credits at HEQSF level N" wording | 2026 | credits-line accepts NQF and HEQSF |
| H22 | Trailing brackets on plan-code lines | `[CB003BUS01][SAQA ID:4411]` (2021/2022) | unified heading rule tolerates extra brackets |
| H23 | Wrapped heading tails | "…specialising in Quantitative ⏎ Finance [CB025BUS09]" (2024) | pre-bracket tail joined to buffered title lines |
| H24 | Markers/misprints inside the code bracket | `[CB011ECO03#]` (2022/2023), `[CB0015ECO03]` extra zero (2024) | bracket grammar tolerates `#`/`*`; extra-zero normalisation |
| H25 | Unseparated / comma-format published fees | `R 84690` (2023), `R 68,900` (2024) | sec-11 amount grammar accepts all three formats |
| H26 | Mixed year-heading nouns within one edition | EBE 2021: "Second Year Core **Modules**" inside a "Core Courses" book | EBE heading grammar accepts both nouns |
| H27 | Year headings with parenthetical suffixes | EBE: "First Year Core Courses (from 2020)", "… (EE)" | optional trailing parenthetical in the heading grammar |
| H28 | Pages with no running header (bare page number) | EBE 2023 in-faculty departments section (107 pages) | content-signature classification + sandwich fill for bare-number pages |
| H29 | Level-based totals with two wordings | LAW: "Total credits for Preliminary Level … 144" vs "… for first (Preliminary) year … 144"; stream grand totals must NOT match | faculty `total_line` override; grand totals excluded by pattern |
| H30 | Slot credits on a continuation line | LAW: "Two semester courses in a single language, …" + "…… 36 5" | `extra_elective_nocred` + credits-continuation merge |
| H31 | Section running header mislabelled by the book | LAW 2026 prints "COURSE OUTLINES (LLB)" over the rules-section pages | content reclassification (`content_reclassify`): programme signatures override the header |
| H32 | Multi-code programme blocks with shared curricula | FHS: "[MB014, MB020]", "[BSc Audiology MB011/MB019 & BSc Speech-Language Pathology MB010/MB018]" | bespoke FHS parser: primary code carries the curriculum, siblings noted; per-segment degree pairing |
| H33 | Trailing totals with slashed variant values | FHS: rows print BEFORE "Total NQF credits for year 2 … 162/168" | rows buffer until the next total/heading stamps their year; slash → credits + stated_total_max |
| H34 | Multi-line code brackets and programme-vs-plan code mixes | FHS 2021-2023: "[Programme code: MB003 or MB016 … Plan code: MB003AHS09." | closing bracket optional; 10-char plan codes take precedence over 5-char programme codes they subsume |

Failing to recognise a heading is the costliest hazard class: the previous
block silently **swallows** the next programme's tables (doubling its row
sums) — exactly what detector R2b in the final layer flags as
`check_extraction`. H22–H24, H26 and the EB015CON04 case were all found this
way; **an exactly-2× row-sum is the diagnostic signature**.

Variant assignment precedence (robust across all layouts): page-header hint
(2026) → known programme-code family map (`VARIANT_BY_PROGCODE`) → umbrella-
line tracking (2021-2025).

## 7. The shared engine and the EBE faculty (added 2026-08-06)

The COM parser was promoted to a faculty-configurable engine,
`common/handbook_parser.py`, once EBE proved to use the same publisher
template. Each faculty supplies a `FacultyConfig`
(`extractors/<fac>/extract.py`): plan-code grammar, degree parser, page
classification, heading grammar, variant resolution, department map, and
optional extras. The promotion was verified value-identical for all six COM
editions (curriculum and courses byte-equal; one deliberate improvement —
range-total support now captures a 2026 AdvDip total that previously sat in
notes).

**EBE config deltas** (stable across 2021-2026 — EBE shows no cross-edition
layout drift, unlike COM):

- Plan codes `EB###XXX##`; the **800-series are the 5-year Extended
  Curriculum Programmes** → variant `extended`.
- Year headings say "Core Courses" (with H26/H27 tolerances).
- Stated totals are often **ranges** ("108-156") because elective loads are
  ranges ("Approved elective courses … 0-48"): the minimum anchors the ideal
  student (`is_minimum=True`), the maximum is kept in `stated_total_max`.
- Every programme is followed by an "ELECTIVE COURSES" pool section →
  `requirement=alternative`.
- Specialisation sub-streams (Geomatics Geoinformatics: Computer Science vs
  EGS) share one plan code — the second block is DUPLICATE-flagged and its
  rows suppressed (first-listed stream is the ideal), as is the transferee
  access programme that reuses `EB001CHE01`/`EB002CIV01` (see DEV-TODO).
- Published-fee labels ("BSc Eng (Chemical)") are matched by an EBE-specific
  label parser; ECP variants are not published separately — duration
  matching assigns each block to the right variant.

Tables shared by several faculties are written **merge-by-faculty-within-
year** (`write_year_rows(..., keep=...)`): an extractor re-run replaces only
its own faculty's rows.

**LAW config deltas** (stable across 2021-2026 except H31 in 2026):

- Undergraduate content is the "RULES FOR LLB DEGREE STREAMS" section: three
  streams with 5-character programme codes and no department suffix —
  `[LP001]` graduate LLB, `[LB002]` four-year undergraduate LLB, `[LB003]`
  legacy five-year stream (no new intake after 2019 → variant `extended`;
  absent from 2026; prints no credit totals, so its spec-years are flagged
  unresolved by design).
- Year headings: "First Year YEAR 1 (PRELIMINARY LEVEL)" (LB003 uses
  COM-style "Core Modules"); totals are per level with two wordings (H29).
- Cross-faculty requirement lines ("AND two semester courses in another
  faculty … 36 5") are captured as elective slots via the LAW
  `extra_elective` grammar; wrapped descriptions merge with their
  continuation line (H30).
- The many bracketed postgraduate codes (LM…/LG002…) sit in postgraduate
  sections excluded by page classification.
- Published fees (fees book §11.6) are **flat annual amounts per stream**
  ("Undergraduate LLB … R 76 810") — applied to every study year with match
  method `flat_annual`; per-year divergence from the flat figure is expected
  and is not a data defect.

**FHS (bespoke parser, `extractors/fhs/extract.py`).** FHS does not fit the
block engine: programme blocks are bracket lines carrying one or more MB
codes with shared curricula (H32), totals trail their tables with several
wordings and slashed variant values (H33), the MBChB runs SIX years with
rule-prefixed headings ("FBA3.8 Sixth Year"), and 2022-2023 use per-degree
running headers while 2021-2023 print multi-line brackets (H34). The parser
reuses the shared grammar (course rows, OR handling) and the engine's
catalogue parser/classifier. Conventions: primary code carries the
curriculum; second code of a pair is the intervention/extended variant;
known residual — the combined Audiology/Speech-Language block interleaves
both degrees' sub-tables before shared totals and needs a dedicated
splitter (its spec-years are flagged unresolved; see DEV-TODO.md).

## 8. Multi-year status (COM + EBE + LAW + FHS, final layer 2026-08-06)

Consistent / resolved / unresolved per faculty:

| Year | COM | EBE | LAW | FHS |
|---|---|---|---|---|
| 2021 | 227 / 17 / 30 | 62 / 1 / 27 | 7 / 0 / 5 | 7 / 0 / 12 |
| 2022 | 240 / 11 / 24 | 57 / 0 / 33 | 7 / 0 / 5 | 8 / 0 / 11 |
| 2023 | 225 / 15 / 36 | 59 / 0 / 31 | 7 / 0 / 5 | 14 / 0 / 11 |
| 2024 | 203 / 13 / 55 | 57 / 0 / 33 | 7 / 0 / 5 | 14 / 0 / 11 |
| 2025 | 219 / 13 / 36 | 55 / 0 / 32 | 7 / 0 / 5 | 11 / 0 / 12 |
| 2026 | 202 / 11 / 48 | 54 / 0 / 29 | 7 / 0 / 0 | 10 / 0 / 13 |

Main dataset: **20,438 rows** (COM 14,282 + EBE 4,536 + LAW 433 + FHS
1,187); 696 specialisation register entries; 2,356 specialisation-years
(1,766 consistent, 81 resolved, 509 unresolved pending adjudication — the
EBE/LAW/FHS registers are empty until their review passes, see DEV-TODO.md).
Median computed-vs-published fee delta is 0.0% for COM, EBE and FHS (the
MBChB's years 1-3 match to the rand); LAW's flat-annual published fees make
per-year deltas structurally divergent (LP001 year 1 matches to the rand).

## 9. Extending to the remaining faculties

SCI and HUM remain — the unit of extraction there is the *major*
(`SB…`/`HB…` plan codes) plus the degree-composition rules from the faculty
rules section, from which the ideal student's curriculum is constructed
rather than read off a table; expect bespoke parsers in the FHS mould
(reusing the shared grammar and catalogue parser).
