# Commerce Handbook Review & Proposed Way Forward

*Based on inspection of `2025-com-ug.pdf` (303 pp) and `2025-_fees.pdf` (154 pp), August 2026.*

## 1. What the Commerce handbook contains

The 2025 Commerce undergraduate handbook is the most structured of the six
faculty books and is the right one to build first. Its anatomy:

| Section | Pages (approx.) | Data value |
|---|---|---|
| Front matter, term dates, codes & symbols | 1–14 | Course-code grammar, results symbols |
| Qualifications register | 15–18 | Degree names, abbreviations, SAQA IDs, minimum duration |
| Faculty rules (`FBA…`) | 24–37 | Degree requirements, progression rules |
| **Programmes of Study** | 38–133 | **Curriculum tables per plan code — the core dataset** |
| Departments (staff + course descriptions) | 134–291 | Course catalogue: credits, NQF level, prerequisites, assessment |
| Terminology & policies | 292–303 | Reference |

### 1.1 Programme curriculum tables

Each specialisation is introduced by a heading + plan code, then per-year tables:

```
Bachelor of Business Science specialising in FINANCE with ACCOUNTING
[CB004FTX04]
First Year Core Modules
Code        Course                       NQF Credits   NQF Level
ACC1006F    Financial Accounting              18            5
...
Total credits per year ............ 159
```

Observed structural features the parser must handle:

- **Year blocks**: "First/Second/Third/Fourth Year Core Modules".
- **Stated totals**: every year block ends with "Total credits per year … N" —
  an authoritative cross-check we should *compare against*, never sum from.
- **OR groups**: consecutive rows separated by an `OR` line
  (e.g. `MAM1031F` OR `MAM1004F`; `INF1002F/S` OR `CSC1015F`).
- **Elective placeholders** (elective-heavy programmes such as BCom Management
  Studies `CB001BUS06`): "One elective at 1st year level … 18 5",
  "Four electives at NQF level 6 … 72 6", "Any NQF level 7 electives …
  totalling a minimum of 120 credits". Pre-approved elective lists follow as
  plain lists, plus discipline-specific guidance for Honours eligibility.
- **Footnotes** carrying binding rules (e.g. 60% average in 3rd-year finance
  courses required for FTX4000-level entry; ACC3009W↔ACC3020W substitution).
- **Programme families**: the same specialisation appears up to three times —
  regular (`CB001`/`CB003`/`CB004`), Academic Development *augmented*
  (`CB023`/`CB026`) and *extended* (`CB011`/`CB015`/`CB018`/`CB020`) variants
  with different year structures. These are distinct plan codes and distinct
  rows in our dataset, related via a `variant` column.

### 1.2 Course descriptions

Department sections list courses in a highly regular template:

```
ACC1006F FINANCIAL ACCOUNTING
18 NQF credits at NQF level 5
Convener: J Kew
Course entry requirements: …
Course outline: …
Lecture times: …
DP requirements: …
Assessment: Coursework: 35% Exam: 65%
```

This yields a clean course catalogue including courses taught *to* Commerce by
other faculties (CML, CSC, MAM, PHI, POL, PSY, STA, EGS…), which the curriculum
tables reference.

### 1.3 The fees handbook joins on both keys

- **§12 "UCT Academic Courses"** (pp. 59–143): a flat university-wide table
  `COURSE_CODE  TITLE  FEE` (e.g. `ACC1006F FINANCIAL ACCOUNTING 10,440`).
  Joins to the course catalogue on `course_code`.
- **§11 "UCT Academic Fees"** (pp. 40–58): published *typical annual fees per
  programme-year* per faculty (e.g. "BCom specialising in Economics & Finance,
  1st Year R 78 090"). Labelled by name only — needs fuzzy matching to plan
  codes — but it is exactly the university's own "ideal student" costing, which
  makes it a powerful external validation of ours.

This gives a **validation triangle**:

```
curriculum (courses+credits)  ×  course_fees  →  computed annual cost
        ↓ compare                                     ↓ compare
"Total credits per year"                 published programme-year fee (§11)
```

## 2. Proposed data model

All tables carry `year` (handbook edition) and `source_page` (provenance).
CSV in `data/processed/`, one folder per year is *not* used — year is a column,
so multi-year trend queries are trivial.

**`programmes`** — one row per plan code
`year, faculty, plan_code, programme_code, dept_code, degree_abbrev, degree_name,
specialisation, variant (regular|augmented|extended), nqf_exit_level,
min_duration_years, saqa_id, source_page`

**`curriculum`** — one row per course-slot per plan-year
`year, faculty, plan_code, study_year (1–4), seq, course_code, course_title,
nqf_credits, nqf_level, requirement (core|option|elective_slot),
choice_group (id shared by OR alternatives; null otherwise),
elective_rule (verbatim text for elective slots), notes, source_page`

**`curriculum_totals`** — one row per plan-year
`year, plan_code, study_year, stated_total_credits, is_minimum (bool)`

**`courses`** — one row per course description
`year, faculty_book, dept, course_code, title, nqf_credits, nqf_level, convener,
entry_requirements, assessment, source_page`

**`course_fees`** — one row per fees-book course row
`year, course_code, fees_title, fee_zar, source_page`

**`programme_fees_published`** — one row per published programme-year fee
`year, faculty, programme_label (verbatim), study_year, fee_zar,
matched_plan_code (nullable, via fuzzy match), source_page`

**`ideal_student`** — derived, one row per plan-year
`year, plan_code, study_year, credits_core, credits_elective_assumed,
credits_total, stated_total_credits, credit_delta, fee_core,
fee_elective_estimated, fee_total, published_fee, fee_delta, flags`

## 3. The "ideal student" — deterministic selection rules

The handbook offers choices; the dataset must commit to one defensible,
reproducible selection per programme-year:

1. **Core courses**: all included.
2. **OR groups**: take the *first-listed* option (handbooks list the default
   path first). Alternates stay in `curriculum` under the same `choice_group`,
   so sensitivity analysis ("what if the student took the other branch?") is a
   query, not a re-extraction.
3. **Elective slots**: credit load comes from the placeholder itself ("Four
   electives at NQF level 6 … 72 credits"). Cost is estimated as the *median*
   §12 fee across the programme's pre-approved elective list for that slot
   (falling back to the median fee of same-level courses in the relevant
   departments). Rows using estimates are flagged `elective_fee_estimated`.
4. **Dual offerings** (`STA2020F/S`): resolve to the `F` code; verify the fee is
   identical across variants (it is, in sampled cases).
5. **Minimum-credit elective years** ("minimum of 120 credits at NQF 7"): the
   ideal student takes exactly the minimum; `is_minimum` is recorded.

**Validation, not assumption:** computed credits are compared to
`curriculum_totals.stated_total_credits`, and computed cost to
`programme_fees_published.fee_zar`. Every mismatch beyond tolerance lands in a
per-faculty exception report in `validation/` for human review — this is where
handbook typos and parser gaps surface.

## 4. Parsing hazards confirmed during review

| Hazard | Example | Mitigation |
|---|---|---|
| Plan-code typos in TOC | `CBO18BUS01` (O for 0), `CB25BUS09` (9 chars) | Trust body heading; normalise O↔0; enforce 10-char shape |
| Split words from PDF extraction | `C omputer Science 2001` | Whitespace-tolerant matching on course codes; join on code not title |
| Stray symbols in totals | `Total credits per year … +168` | Regex tolerant of leading `+`/punctuation |
| Composite codes | `STA2020F/S`, `CML1001F/1004S` | Explicit composite-code resolver |
| Zero-credit courses | `CSC2004Z Programming Assessment 0` | Allow credits = 0 |
| Fees near-duplicates | `ACC1011N … 600` vs `ACC1011S … 10,440` | Keep all rows in `course_fees`; costing joins on exact code; treat `N`-variants as exam-only (verify) |
| Published fees lack codes | "BCom in the field of Management Studies" | Fuzzy name match with manual override table |
| Number formats | `10,440` vs `R 91 190` | Two dedicated parsers |

## 5. Build roadmap

**Phase 1 — Fees extractor** (`extractors/fees/`). Simplest structure, highest
leverage: §12 course fees (flat table) and §11 published programme fees. Output:
`course_fees`, `programme_fees_published`.

**Phase 2 — Commerce extractor** (`extractors/com/`), in three passes:
1. *Segmentation*: locate section boundaries via the TOC + page headers
   ("PROGRAMMES OF STUDY", "DEPARTMENTS IN THE FACULTY OF COMMERCE").
2. *Programme parser*: split the Programmes section on plan-code headings;
   within each, split on year-block headings; parse course rows, OR groups,
   elective placeholders, totals lines. Output: `programmes`, `curriculum`,
   `curriculum_totals`.
3. *Course-catalogue parser*: split department sections on the
   `CODE TITLE` / `NN NQF credits at NQF level N` pattern. Output: `courses`.

**Phase 3 — Validation harness** (`validation/`): credit-total checks, fee
cross-checks, referential checks (every curriculum course code exists in
`courses` or `course_fees`), exception reports as CSV.

**Phase 4 — Ideal-student builder**: applies §3 rules, outputs `ideal_student`.

**Phase 5 — Remaining faculties**, in order of expected difficulty:
EBE and LAW (structured, Commerce-like tables), FHS (structured but
programme-heavy), then SCI and HUM. For SCI/HUM the unit of extraction shifts
from "curriculum table" to "major + degree-composition rules" (the faculty
rules section defines how many majors/credits at each level constitute the
degree); the ideal student there is a *constructed* curriculum: one or two
majors' required course sequences + the general-education/elective credits the
rules demand. Plan codes follow the `SB001`/`HB001` + dept-code pattern
(e.g. `HB001SOC01`).

**Phase 6 — Multi-year loading & trend analysis**: drop `2024-*`/`2026-*` PDFs
into the raw folder, re-run per year, and build `analysis/` queries comparing
credit load and computed cost per plan code across editions. Plan codes are
stable enough to serve as the longitudinal key; where codes change between
editions, a small `plan_code_map` table will record successions.

## 6. Open questions

1. **`N`-suffix fee rows** (~R600): assumed to be exam-only/completion variants,
   excluded from costing — needs confirmation with the fees office.
2. **Published fee tolerance**: published §11 figures are "typical" and may
   assume a specific elective basket; we need to agree what fee delta counts as
   a validation failure (proposal: 5%).
3. **GSB / Advanced Diplomas**: the Commerce book includes Advanced Diplomas
   (`CU…` codes). Include in scope? (Proposal: yes — same parser, they are
   cheap to capture.)
4. **Which faculties' EDU/extended variants matter for the credit-load
   analysis?** They change the per-year load materially (same total credits over
   more years). Currently captured as distinct plan codes with a `variant`
   column, which keeps both views available.
