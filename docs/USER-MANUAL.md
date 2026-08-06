# UCT Handbook Dataset — User Manual

*For reviewers, deans, and faculty planning teams.*
*Dataset version: Commerce + Fees, 2021–2026 editions (August 2026).*

---

## 1. Purpose

The University has been re-thinking curriculum credit loads, and some changes
are already in effect. To evaluate those changes, we need to answer, per
degree programme and per year of study, two questions:

1. **How many credits does a student actually carry, and how has that changed
   across handbook editions?**
2. **What does that credit load cost, and how has the cost moved with it?**

The published handbooks contain the answers, but as narrative PDF documents.
This project converts them into a single analysable dataset in which every
number can be traced back to the page of the handbook it came from.

## 2. What is covered

| Content | Editions | Status |
|---|---|---|
| Faculty of Commerce undergraduate handbook | 2021, 2022, 2023, 2024, 2025, 2026 | complete |
| Student Fees handbook (course fees + published programme fees) | 2021–2026 | complete |
| EBE, Health Sciences, Humanities, Law, Science handbooks | 2025 books on file | extraction pending |

The 2025 edition is treated as the **baseline** — the recorded state of the
curriculum against which the credit re-think editions are compared. Across the
six Commerce editions the dataset holds **14,282 curriculum records** covering
**71–75 specialisations per year** as offerings opened and closed, including
the Academic Development (augmented and extended) variants and the Advanced
Diplomas.

The dataset now comes in **two layers**:

- the **as-printed layer** — exactly what the handbooks print, including
  their own defects, preserved for audit;
- the **final-clean layer** (`main_dataset_final.csv`,
  `ideal_student_summary_final.csv`) — the same data with those defects
  resolved by documented, justified rules and case-by-case adjudications.

**Analysts should use the final-clean tables; auditors and replicators the
as-printed ones.** Section 6 describes both.

## 3. How the dataset was produced — and why it can be trusted

The conversion is fully programmatic. The same software reads each PDF,
recognises the handbook's structures (programme headings, curriculum tables,
course descriptions, fee tables), and writes the output tables. Four
integrity rules apply throughout:

1. **Source PDFs are never edited.** They are stored read-only in the
   repository, and every published edition is kept.
2. **Every record carries provenance.** Each row records the handbook year
   and the PDF page it came from, so any value can be checked against the
   original in seconds.
3. **No manual edits to outputs.** If the software misreads something, the
   software is fixed and re-run. Where the *handbook itself* contains a
   defect (a misprinted total, a missing rule), the correction is recorded in
   a documented "overrides" file stating the reason and the source page — or
   the defect is left in place and flagged, never silently changed.
4. **Everything is version-controlled.** The full history of the dataset and
   the software that built it is kept in git; re-running any year reproduces
   the same output, and re-processing one year cannot alter another year's
   records.

## 4. Key concepts

**Specialisation code (plan code).** The fundamental unit of the dataset,
e.g. `CB004FTX04` — Bachelor of Business Science specialising in Finance with
Accounting. The first five characters identify the programme family
(`CB004`), the last five the department/stream (`FTX04`). Commerce publishes
each specialisation in up to three **variants**:

- *regular* — the standard curriculum;
- *augmented* — Academic Development, same duration with additional support
  courses;
- *extended* — Academic Development, the curriculum spread over an extra year.

Each variant has its own specialisation code and is a separate row-set in the
dataset, so comparisons can be like-for-like.

**Course code.** E.g. `ACC1006F`: department (`ACC`), year-level digit
(`1`), course number (`006`), and period (`F` first semester, `S` second,
`W` whole year, `H` year-long half-course).

**NQF credits and levels.** Credits measure notional learning time (1 credit
= 10 notional hours; a standard semester course is 18 credits). Levels 5–8
grade the qualification ladder: level 7 is the exit of a 3-year bachelor's,
level 8 of a 4-year professional bachelor's.

## 5. The "ideal student"

Handbooks list more courses than any one student takes: they contain
either/or choices, option blocks, and elective slots. Credit load and cost
must therefore be computed from *a defensible selection*, not from everything
on offer. The dataset defines the **ideal student** by deterministic,
uniformly applied rules:

| Structure in the handbook | Rule |
|---|---|
| Core (compulsory) course | Taken. |
| "A **or** B" choices | The first-listed option is taken (handbooks list the default path first). The alternatives remain in the dataset, so "what if the student took B" is a filter, not a re-count. |
| "Choose *n* from the following" menus | The first *n* menu entries are taken; the menu and the pick-count are recorded. |
| Named option streams (e.g. Mathematical Statistics Option vs Applied Statistics Option) | The first-printed stream is taken. |
| Elective slots ("Four electives at NQF level 6 … 72 credits") | The slot is taken at its stated credits. If the handbook omits the slot's credits, they are inferred from the year's stated credit total and flagged as inferred. |
| "Minimum of *N* credits" years | The ideal student takes exactly the minimum. |

Every curriculum row carries an **`ideal_student`** true/false flag applying
these rules, so the ideal student is visible *inside* the main dataset rather
than in a separate calculation.

**Costing.** Each taken course is priced at its exact fee from the fees book
(course-code to course-code). Elective slots, which name no specific course,
are priced at the *median* fee of same-level courses in the departments that
specialisation draws on, scaled to the slot's credits — and always flagged as
estimates, with the estimated component reported separately in the summary
table.

## 6. The tables

All tables are CSV files in `data/processed/` and open directly in Excel.
Every table has a `year` column (handbook edition) — filter on it first.

### 6.1 `main_dataset.csv` — the single source of truth

One row per specialisation × year-of-study × course-slot. Key columns:

| Column | Meaning |
|---|---|
| `year` | handbook edition (2021–2026) |
| `plan_code`, `specialisation`, `degree_abbrev`, `variant` | which programme this row belongs to |
| `study_year` | year of study within the programme (1–5) |
| `course_code`, `course_title` | the course (blank code for elective slots) |
| `nqf_credits`, `nqf_level` | credit value and NQF level as printed |
| `requirement` | `core` / `option` (a choice) / `elective` (a slot) / `alternative` (listed but not counted) |
| `choice_group`, `choice_member`, `choice_pick_n` | which choice this row belongs to, its position, and how many are taken |
| `ideal_student` | **True if the ideal student takes this row** |
| `credits_inferred` | True where slot credits were derived from the year total |
| `fee_zar`, `fee_source` | the Rand fee and how it was resolved (`exact`, `variant:…`, `estimated_median`) |
| `source_page` | PDF page in that year's handbook |

### 6.2 `ideal_student_summary.csv` — one row per specialisation-year

The roll-up used for most review questions:

| Column | Meaning |
|---|---|
| `credits_ideal` | credits the ideal student carries that year |
| `credits_stated` / `credit_delta` | the handbook's own printed total, and the difference |
| `fee_ideal_zar` | computed cost of the ideal student's year |
| `fee_estimated_component_zar` | how much of that is elective-slot estimation |
| `fee_published_zar` / `fee_delta_pct` | UCT's published "typical" fee for that programme-year, and the percentage difference |
| `fee_match_method` | how the published fee was matched (see §8, caveat 4) |

### 6.3 Supporting tables

`specialisations` (the register, per year), `curriculum` and
`curriculum_totals` (the raw curriculum tables and their printed totals),
`courses` (course catalogue: convener, entry requirements, assessment),
`course_fees` (every course's fee), `programme_fees_published` (the fees
book's typical annual fees as printed).

### 6.4 `main_dataset_final.csv` — the final-clean dataset

Every row of `main_dataset.csv` with its original columns untouched, plus:

| Column | Meaning |
|---|---|
| `final_included` | True if the row counts in the final ideal-student selection (differs from `ideal_student` only where an adjudication changed a choice) |
| `resolution_class` | `none` / `R1a` (arithmetic rule) / `R2a` (cross-edition rule) / `R3` (adjudication) |
| `resolution_ref` | the rule or register entry (e.g. `COM-2025-008`) that applied |
| `final_note` | explanation where the row's inclusion changed |

### 6.5 `ideal_student_summary_final.csv` — the final roll-up

The summary table analysts should use. Adds to §6.2's columns:

| Column | Meaning |
|---|---|
| `final_credits` | the resolved credit load for the year |
| `credits_stated_corrected` | filled where a misprinted total was corrected by adjudication |
| `final_credit_status` | `consistent` / `resolved_computed` / `resolved_manual` / `unresolved` |
| `final_fee_zar` / `final_fee_status` | resolved cost; `reconciled` / `published_divergent` / `no_published` |
| `confidence` | `high` (arithmetic or adjudicated) / `medium` (cross-edition) / `low` (default policy) |
| `resolution_rationale` | the written justification, in full sentences |

How discrepancies are resolved — the rule order, the evidence each rule
demands, and worked examples — is documented in
[FINAL-DATASET-METHOD.md](FINAL-DATASET-METHOD.md). In short: printed
arithmetic identities and corroborated cross-edition evidence resolve
automatically; genuine ambiguities are adjudicated case-by-case in a
reviewable register (`resolutions/com.csv`) with rationale and page
evidence; everything else is flagged `unresolved` at `low` confidence rather
than silently guessed.

## 7. How the data is validated

Each specialisation-year is checked from two independent directions — a
validation triangle:

```
   curriculum (courses + credits)  ×  course fees   →  computed year cost
        ↕ compared with                                  ↕ compared with
   the handbook's printed                       the fees book's published
   "Total credits per year"                     typical fee for that year
```

Results for the current load, after the final-clean layer:

| Year | Spec-years | Consistent as printed | Resolved by rule/adjudication | Unresolved (flagged) |
|---|---|---|---|---|
| 2021 | 274 | 227 | 17 | 30 |
| 2022 | 275 | 240 | 11 | 24 |
| 2023 | 276 | 225 | 15 | 36 |
| 2024 | 271 | 203 | 13 | 55 |
| 2025 | 268 | 219 | 13 | 36 |
| 2026 | 261 | 201 | 11 | 49 |

86% of all specialisation-years are fully resolved at high or medium
confidence; the unresolved remainder (mostly small ±6–24 credit gaps) carry
the computed value at low confidence and are individually listed, with
suggested actions, in `validation/pending_adjudication_<year>.csv`.

Where computed fees can be compared with published fees, the **median
difference is 0.0%** — for most programmes the computation reproduces UCT's
own published figure to the rand.

**A "mismatch" is a finding, not an error.** Every one is listed, with page
references, in the `validation/` reports (`credit_check_<year>.csv`,
`fee_check_<year>.csv`). On inspection, most mismatches are defects or
ambiguities in the handbooks themselves, which the dataset deliberately
preserves and surfaces rather than papering over. Real examples:

- a printed year total of **382** credits where the table sums to 182 (2025,
  CB025BUS09 year 1 — a misprint);
- year totals that **count both branches of an either/or choice** (2025,
  CB001INF01 year 1: rows sum to 150 taking one branch, 168 taking both; the
  printed total is 168);
- final-year course menus whose **selection rule is printed nowhere** (the
  Computer Science stream's 4th-year module list);
- a stated total **excluding a course that is listed** in the same table
  (CB011ACC08 year 2).

These lists are themselves a useful review product: they show where the
published handbooks would benefit from editorial correction.

## 8. Caveats and limitations

1. **Elective costs are estimates.** Slots naming no course are priced at a
   credit-scaled median (§5). The estimated component is always reported
   separately (`fee_estimated_component_zar`), so it can be excluded from any
   analysis that requires exact figures.
2. **The ideal student is a convention.** "First-listed option" is a
   documented, consistent convention — not a claim about actual student
   behaviour. Because alternatives are retained, sensitivity checks are
   straightforward.
3. **Handbook defects are preserved.** Where the handbook's own numbers
   disagree, the dataset records what is printed and flags the disagreement
   (§7). Corrections are only applied through the documented overrides
   process (§10).
4. **Published-fee matching is by name.** The fees book labels programmes by
   name, not by specialisation code, and names drift between books
   ("Analytics" vs "Statistics and Data Sciences"). Matching is rule-based
   with a curated alias list; the method used is recorded per row
   (`fee_match_method`), and unmatched labels are reported. Academic
   Development fees are published once per specialisation — they are assigned
   to the variant whose duration matches the published block, and flagged
   where ambiguity remains.
5. **Older editions are noisier.** The 2021–2023 fee sections reconcile at a
   somewhat lower rate than 2024–2026; their mismatch lists are
   correspondingly longer.
6. **Zero-credit and cross-listed courses exist** (e.g. a 0-credit
   programming assessment) and are represented as printed.
7. **Coverage is Commerce-first.** Conclusions about other faculties must
   wait for their extractors; their handbook structures differ (Science and
   Humanities in particular define majors plus composition rules rather than
   per-specialisation tables).

## 9. Worked examples

**"How did the credit load of BCom Actuarial Science change?"**
Open `ideal_student_summary.csv`, filter `plan_code = CB019BUS01`,
`study_year = 1`:

| Edition | Ideal credits | Stated total | Computed fee | Published fee |
|---|---|---|---|---|
| 2021 | 185 | 185 | R85,250 | R85,250 |
| 2022 | 185 | 185 | R88,910 | R88,910 |
| 2023 | 185 | 185 | R93,850 | R93,850 |
| 2024 | 180 | 180 | R98,140 | R98,140 |
| 2025 | 180 | 180 | R103,890 | R103,890 |
| 2026 | 180 | 180 | R110,160 | R110,580 |

The credit re-think is visible at the 2024 edition (−5 credits), and the
computed cost matches the published fee to the rand in 2021–2025 (−0.4% in
2026).

**"What exactly does that student take in 2024?"**
Open `main_dataset.csv`, filter `year = 2024`, `plan_code = CB019BUS01`,
`study_year = 1`, `ideal_student = True` — the course list, each course's
credits and fee, and the page each row came from.

**"Which programmes' handbook entries need editorial attention?"**
Open `validation/credit_check_<year>.csv` and filter `status = MISMATCH`.

## 10. Raising corrections

If a reviewer finds a value that misrepresents the handbook:

1. Check the row's `source_page` against the PDF in
   `faculty-handbooks-undergraduate/`.
2. **If the software misread the page** (the PDF prints the right value), the
   parser or its overrides file is fixed and the year re-run — other years
   are provably unaffected.
3. **If the handbook itself is wrong or ambiguous**, the decision is entered
   in the adjudication register (`resolutions/com.csv`) with its rationale
   and page evidence, and the final layer re-run. The as-printed record is
   never altered; the final tables carry the resolution with its register
   reference, so every correction is visible, attributable, and reversible.

Forty-four provisional adjudications (marked *"provisional (Claude), pending
review"*) currently await confirmation — reviewing them is the most valuable
contribution a reader of this manual can make. They are listed in
`resolutions/com.csv` with their reasoning spelled out.

## 11. Glossary

| Term | Meaning |
|---|---|
| **Specialisation / plan code** | 10-character code identifying a full degree programme (§4) |
| **Variant** | regular / augmented / extended presentation of a specialisation |
| **NQF credit** | 10 notional learning hours; 18 = standard semester course |
| **NQF level** | qualification-ladder level (5–8 for undergraduate work) |
| **Ideal student** | the deterministic course selection defined in §5 |
| **Stated total** | the "Total credits per year" figure printed in the handbook |
| **Published fee** | the "typical annual fee" printed in the fees book |
| **Elective slot** | a curriculum line reserving credits without naming a course |
| **Provenance** | the `year` + `source_page` columns tracing a row to its PDF page |
| **Overrides** | documented, reviewable corrections applied at build time |

## 12. File inventory

| Location | Contents |
|---|---|
| `faculty-handbooks-undergraduate/` | source PDFs, read-only |
| `data/processed/main_dataset_final.csv` | **the final-clean dataset — use this for analysis** (§6.4) |
| `data/processed/ideal_student_summary_final.csv` | final per specialisation-year roll-up (§6.5) |
| `data/processed/main_dataset.csv` | as-printed dataset (§6.1) — audit/replication |
| `data/processed/ideal_student_summary.csv` | as-printed roll-up (§6.2) |
| `data/processed/*.csv` | supporting tables (§6.3) |
| `resolutions/com.csv` | the adjudication register with rationales (§10) |
| `validation/*.csv` | exception reports, resolution logs, pending adjudications (§7) |
| `docs/FINAL-DATASET-METHOD.md` | how the final layer resolves discrepancies |
| `docs/REPLICATION.md` | technical process log and hazard catalogue |
| `docs/commerce-review-and-proposal.md` | original design document |
