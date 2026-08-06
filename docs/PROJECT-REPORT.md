# The UCT Handbook Dataset — End-to-End Project Report

*A standalone account of the project: what was built, how the handbooks
were reverse-engineered into a relational database, what was found —
faculty by faculty — to be accurate, inconsistent, or wrong, how the
final justified dataset was produced, and where the project goes next.*

*State as of August 2026: all six faculties + fees, 2021–2026 editions.*

---

## 1. Executive summary

The University of Cape Town is re-thinking curriculum credit loads. This
project converts the published evidence of that re-think — six years of
faculty handbooks and student-fees handbooks (42 PDFs, 2021–2026) — into a
relational dataset in which **every number can be traced to the page it
was printed on**, and in which credit loads and their Rand cost can be
compared across editions, faculties, and degree programmes.

The dataset now covers **all six faculties** (Commerce, Engineering & the
Built Environment, Law, Health Sciences, Science, Humanities): 24,536
curriculum records across 1,066 programme register entries, a 9,821-entry
course catalogue, 26,298 course-fee rows, 3,197 published programme fees,
and — critically — a **387-row rules layer** extracted from the
faculty-rules sections, recording what each degree must total in credits.

Headline findings:

- **The credit re-think is real, measurable, and written into the books
  in two different ways.** In Commerce the *rules* moved first: the
  BBusSc minimum fell from 623 to 528 credits at the 2025 edition while
  the printed curricula (still 544–675 credits in 2026) have not yet
  shrunk to the new floor. In Engineering the *departments* moved first:
  Chemical Engineering's printed curriculum falls 544 → 496 → 468 credits
  across the 2024→2026 editions, with cohort-split wording ("560 if
  registered from 2025, else 576") appearing a year before the faculty
  rule itself dropped from 576 to 560 in 2026. Law's four-year LLB total
  fell 660 → 637 at 2026.
- **The handbooks are mostly accurate — and their defects are
  identifiable, classifiable, and worth reporting back.** Of 2,366
  specialisation-years with a printed credit total to check against, 86%
  reconcile exactly or are resolved by documented rules. The remainder
  divides into misprints (a "382" where the table sums to 182), totals
  that count both branches of an either/or choice, choice menus whose
  selection rule was never printed, and curricula that no longer sum to
  their own faculty's stated minimum — including three 2026 BCom
  specialisations printed *below* the BCom's own 440-credit floor.
- **Computed cost reproduces UCT's own published fees.** Summing each
  taken course's fee reproduces the published "typical annual fee" at a
  median absolute difference of 0.0% in Commerce, ~0.5% in EBE and ~1.8%
  in Health Sciences (the MBChB's pre-clinical years match to the rand).
  Where the difference is large it is structural and labelled: Law
  publishes one flat fee per stream, Science/Humanities one per degree.
- **Nothing was silently corrected.** The as-printed layer records the
  books verbatim, defects included; a separate final-clean layer resolves
  defects through an ordered rule set and a reviewable adjudication
  register, each resolution carrying its class, evidence, confidence and
  written rationale.

The recommended next step (§10) is a DuckDB-based exploration layer with
a dean-facing visual interface over exactly these tables.

## 2. The question and the source material

Three questions drive the design:

1. How many credits does a student actually carry in each year of study,
   and how has that changed across handbook editions?
2. What does that credit load cost, and how has cost moved with it?
3. What do the faculty rules say the **whole degree** must total — and
   when did that requirement change?

The sources are the university's own publications, stored immutably in
`faculty-handbooks-undergraduate/` under the convention
`YYYY-<faculty>-ug.pdf` and `YYYY-_fees.pdf`: six editions (2021–2026) of
six faculty undergraduate handbooks plus six fees handbooks. The 2025
edition is tagged as the **baseline** (`baseline-2025`) — the recorded
state against which credit re-think editions are compared, noting that
the rules layer shows some changes landing at or before that baseline.

Each faculty handbook contains, in a publisher's template that most
faculties share: front matter, a qualifications register, a
**faculty-rules section** (rule codes like `FBA16` — degree requirements
live here), **programmes of study** (per plan code, year-by-year
curriculum tables with a printed "Total credits per year" line), and
**department sections** (course descriptions with credits, conveners,
entry requirements). The fees handbook prints published "typical annual
fees" per programme-year (§11, labelled by name only) and a
university-wide course-fee table (§12).

## 3. Reverse-engineering the books into a relational database

The handbooks are narrative documents; the project's core act is
recovering the relational structure they encode implicitly. Three design
decisions made this reliable:

**One shared engine, per-faculty configuration.** Commerce's parser was
promoted into a faculty-configurable engine
(`common/handbook_parser.py`) once EBE proved to use the same publisher
template; Law joined it. Each of these faculties is expressed as a
`FacultyConfig` — plan-code grammar, degree parser, heading variants,
page classification — never as a fork of the engine. Health Sciences,
Science and Humanities genuinely do not fit the template (multi-code
programme blocks; majors printed inside department sections) and have
bespoke parsers that still reuse the shared row grammar and catalogue
parser. Parsing was hardened against a catalogue of **40 documented
hazards** (H1–H40 in `docs/REPLICATION.md`) discovered by inspection —
from plan-code typos (`CBO18BUS01`, letter O for zero) to per-edition
layout drift (2024's Title-Case headers, 2026's per-degree running
headers) to the costliest failure class: an unrecognised heading silently
merges two programmes, and an exactly-2× row sum is its diagnostic
signature.

**Two layers, one provenance rule.** The **as-printed layer** records
exactly what the books print, defects included; the **final-clean layer**
(§6) resolves defects by documented rules. Every row in every table
carries `year` (edition) and `source_page` (PDF page), so any value is
checkable against the original in seconds. Extraction is deterministic
and re-runnable; outputs are never hand-edited; writers merge by year and
by faculty within year, so re-running one extractor cannot disturb any
other faculty's or year's rows — pipeline runs review as small git diffs.

**The relational model.** The indivisible key is the 10-character **plan
code** (`CB004FTX04`: programme family + department/stream), which
Commerce, EBE, Law and Health Sciences use for *specialisations* and
Science/Humanities for *majors*. Around it:

| Table | Grain / role |
|---|---|
| `specialisations` | register: one row per plan code per edition (degree, name, variant) |
| `curriculum` | one row per course-slot in a printed year table (core / option / elective / alternative, choice-group encoding) |
| `curriculum_totals` | the printed "Total credits per year" anchors, kept separate from computed sums |
| `courses` | the course catalogue (credits, NQF level, convener, entry requirements) |
| `course_fees`, `programme_fees_published` | the fees book as data (§12 and §11 respectively) |
| `degree_rules` | the **rules layer**: one row per printed degree-level rule statement, with rule code, page and verbatim quote |
| `main_dataset` / `main_dataset_final` | the assembled fact table: specialisation × study-year × course-slot, with credits, fees, `ideal_student`, and (final) resolution columns |
| `ideal_student_summary` / `…_final` | the per specialisation-year roll-up analysts actually query |

The pipeline (`run_pipeline.py`) runs per year: fees extractor → every
faculty extractor whose PDF is present → assembly → validation; then the
final-clean layer for all loaded years.

## 4. The ideal student

Handbooks list more than any one student takes: either/or choices, named
option streams, "choose n from" menus, elective slots. Credit load and
cost are therefore computed for a deterministic **ideal student**: every
core course; the first-listed branch of any choice (alternates retained,
so "what if they took B" is a filter, not a re-count); elective slots at
their stated credits, priced at the median same-level fee of the
departments the specialisation draws on and always flagged as estimates;
minima taken exactly. The selection is a *documented convention*, not a
behavioural claim — and it is visible inside the dataset as a boolean on
every row rather than in a separate calculation.

**Validation triangle.** Each specialisation-year is checked from
independent directions: computed credits vs the handbook's printed
per-year total; computed cost vs the fees book's published programme-year
fee; and — since the rules layer landed — each specialisation's
whole-degree credit sum vs the faculty rules' printed minimum
(`validation/degree_check_<year>.csv`). A mismatch is a *finding, not an
error*: most turn out to be defects in the books themselves, which is
precisely what a curriculum-review dataset should surface.

## 5. The rules layer: using faculty rules to verify the dataset

The faculty-rules sections had never been parsed; they turned out to hold
the strongest evidence in the project. `common/degree_rules.py` extracts
every degree-level statement — minimum total credits, level-specific
requirements, durations, Law's stream grand totals, Science/Humanities'
composition rules — into `degree_rules.csv` (387 rows), each with the
rule reference, page, and verbatim quote.

Two parsing contracts proved essential: **key rules on the degree-heading
text, never the rule code** (Commerce silently re-assigned its rule-code
families wholesale between 2023 and 2024 — FBE stopped meaning "BBusSc
Actuarial Science AD" and started meaning "BCom"), and tolerate sentences
that wrap mid-clause with wording drift ("NQF" vs "HEQSF", "will be" vs
"must be").

The rules layer serves three purposes:

1. **It dates the credit re-think authoritatively** (§1's headline
   table): BBusSc 623→528 and its Actuarial stream 681→528 at 2025; BCom
   450→440 as early as 2022; EBE's blanket 4-year rule 576→560 at 2026
   after departments moved first; LLB 660→637 at 2026; Science re-based
   its degree from "nine full-year courses" to "360 NQF credits (≥180
   Science)" at 2025.
2. **It closes the validation triangle at whole-degree level**, catching
   what per-year checks cannot: a silently missing year table, or a
   handbook whose own sections disagree (§7's per-faculty findings).
3. **It anchors the faculties that print no per-year totals.** Science
   and Humanities curricula are *majors* — deliberately less than a
   degree — so their per-year records carry the status `no_anchor` and
   their credit accountability lives at degree level in the rules.

## 6. The final-clean layer: the justified dataset

The as-printed layer preserves defects; the final layer resolves them —
visibly. Rules apply in fixed order so human judgment pre-empts
automation and arithmetic certainty pre-empts inference:

- **R0** — computed equals stated: nothing to do (high confidence).
- **R3** — an entry in the faculty's adjudication register
  (`resolutions/<faculty>.csv`) applies, citing page evidence and a
  written rationale.
- **R1a** — the stated total exceeds the taken-course sum by *exactly*
  the credits of the non-taken choice branches: the printed total
  demonstrably counts both branches; trust the rows (high confidence).
- **R2a** — the taken-course set is identical to ≥2 sibling editions
  that reconcile exactly, but this edition's stated total diverges:
  trust the rows (medium confidence).
- **R1b/R2b** — detectors (probable misprint; probable extraction gap)
  that never resolve automatically: they file suggestions in
  `validation/pending_adjudication_<year>.csv` for human confirmation.
- **R4** — nothing applies: carry the computed value, flag `unresolved`
  at low confidence, list it in the pending report.

"Computed" is the default because, where both sides can be tested, the
rows win: they reproduce UCT's own published fees to the rand for most
programmes, while stated totals are demonstrably wrong in identifiable
classes. Every resolution writes its class, register reference, and
rationale onto the affected rows; `validate_final.py` asserts the
original columns remain byte-identical and fails on stale register
entries, so the register cannot rot silently. Commerce's register holds
44 provisional adjudications awaiting human sign-off; the other
registers are empty (EBE/LAW/FHS passes queued; SCI/HUM empty by
design).

Current state across 3,287 specialisation-years: **1,949 consistent, 80
resolved, 337 unresolved** (carried at computed value, low confidence,
individually listed with suggested actions), **921 `no_anchor`**
major-years.

## 7. Faculty-by-faculty findings

### 7.1 Commerce (COM) — the template faculty

*71–75 specialisations per edition; 14,282 main-dataset rows; the
faculty that defined the shared engine.*

Commerce publishes each specialisation in up to three variants (regular,
Academic Development augmented, AD extended), and its six editions drift
the most in layout: 2024 switched to Title-Case headers and inline plan
codes; 2026 to per-degree running headers and "HEQSF" wording.

**Accurate.** Most curricula reconcile: 219 of 268 anchored
specialisation-years in the 2025 baseline are consistent or resolved,
and computed fees match published fees at 0.0% median absolute delta —
for most programmes to the rand, e.g. BCom Actuarial Science year 1
matches exactly in all of 2021–2025.

**The credit change.** BCom Actuarial Science year 1 drops 185 → 180
credits at the 2024 edition. At rules level: BCom 450 → 440 at 2022;
BBusSc 623 → 528 (and BBusSc ActSci 681 → 528) at 2025 with the level-8
requirement rising 96 → 120. The 2026 curricula still sum well above the
new BBusSc floor (544–675 credits) — the rule change *precedes* the
curriculum change, which is exactly what a "floor" revision looks like.

**Inconsistent / erroneous.** Three recurring defect classes, all
preserved as printed and resolved downstream:
- *Misprints*: CB025BUS09 year 1 prints "Total … 382" over a table
  summing 182 (its sibling variant prints 182); adjudicated
  `COM-2025-008` with a single-digit-edit argument.
- *Both-branch totals*: printed totals that count both sides of an
  either/or (CB001INF01 year 1: rows sum 150 taking one branch, 168
  taking both; the book prints 168). Rule R1a resolves these
  arithmetically.
- *Unprinted selection rules*: the Computer Science stream's 4th-year
  menu carries no "choose n" instruction in the 2023/2025 editions —
  while 2022/2024/2026 print "required to take two options", now cited
  as cross-edition evidence in the register. The faculty-rules sections
  never state the rule in any edition (a genuine editorial gap).
- *Below their own floor*: in 2026, three BCom specialisations
  (CB001ECO03 at 420, CB001INF01 at 432, CB001INF06 at 438 credits) sum
  below the BCom's own 440-credit rule.

**Open.** 44 provisional adjudications await review; 229 unresolved
specialisation-years (mostly small ±6…±24 gaps) sit in the pending
queue.

### 7.2 Engineering & the Built Environment (EBE) — ranges, menus, and a disclaimer

*25–26 specialisations per edition including the 5-year Extended
Curriculum Programmes (800-series plan codes); 4,729 rows.*

EBE prints elective loads as **ranges** ("Approved elective courses …
0–48"), so stated totals are often ranges too; the ideal student takes
the minimum and both ends are retained. The
Electrical/Mechatronics/Mechanical families print in-year elective menus
("Second Year Elective Core Courses (EE)") and "Optional Courses"
sections whose printed instructions ("Select two out of the following
three") decide the ideal load. The faculty also prints a remarkable
disclaimer — students should *ignore NQF credit values* and complete
degrees by counting courses — worth remembering when comparing EBE
credit sums.

**Accurate.** After the August 2026 engine refinements (footnote-marked
year headings, five distinct elective-slot line shapes), EBE reconciles
at 94%: 509 consistent vs 31 unresolved specialisation-years. The
ECP invariant — each 800-series programme's totals must equal its
mainstream twin's — holds and is checked mechanically.

**The credit change — departments moved before the faculty.** Chemical
Engineering's whole-degree load falls **544 → 496 → 468** across the
2024→2026 editions. Electrical prints cohort-split minima from 2025
("registers in 2025 … 560 / registered before 2025 … 576"); Civil prints
"576 (or 560 if admitted from 2025)"; the faculty's blanket rule FB3.2
(4-year ≥ 576, 3-year ≥ 432) only drops to 560 in 2026, *after* the
departments. Geomatics phases in 519/511 totals in 2026.

**Inconsistent / erroneous.** The 2026 Bachelor of Architectural Studies
curriculum sums 376 credits — 56 below the faculty's own 432 three-year
minimum; the 2026 Property Studies programme states a 452 minimum its own
tables no longer support (411). Both are handbook-side inconsistencies
surfaced by the whole-degree check, queued for adjudication. Geomatics
sub-streams share one plan code (the second stream is recorded but
suppressed from the ideal selection).

**Open.** The 31 residuals; a plan-code suffix scheme if stream-level
analysis is wanted; the register is empty pending its adjudication pass.

### 7.3 Law (LAW) — three streams and a vindicated legacy table

*Three LLB streams; 451 rows; the smallest and cleanest faculty.*

The undergraduate content is the "Rules for LLB Degree Streams" section:
`LP001` (two-year graduate LLB), `LB002` (four-year undergraduate),
`LB003` (legacy five-year stream, no new intake after 2019, absent from
2026). Totals print per *level* rather than per year, in three wordings.

**Accurate.** The graduate stream is the dataset's precision benchmark:
LP001 sums to its printed 504-credit stream total **exactly in all six
editions**, and its first-year computed fee matches the published figure
to the rand. Law publishes one **flat annual fee per stream**
(`flat_annual`), so per-year fee comparisons legitimately diverge from
the flat figure — a structural label, not a defect.

**The credit change.** The four-year LLB's printed stream total falls
**660 → 637 at the 2026 edition** — rules-level evidence of the
re-think reaching Law.

**Inconsistent / erroneous.** The legacy LB003 stream was initially
believed to print no totals; it actually prints them in a third wording
and *wraps discontinued-course rows before their credits* ("PVL1006W …
(No longer on ⏎ offer after 2019) … 36 5"). Once parsed, LB003
reconciles to its printed 660 total in 2021–2023 — and then exposes
genuine print drift: the 2024/2025 editions silently drop discontinued
rows, so their tables sum 642 and 624 against a stated total still
printed as 660. Those seven specialisation-years are Law's only
unresolved cases, correctly flagged as findings.

### 7.4 Health Sciences (FHS) — professional degrees, bespoke parser

*11–16 register entries per edition; 1,187 rows; the first faculty that
would not fit the shared engine.*

FHS prints programme blocks as bracket lines carrying *several* plan
codes with shared curricula ("[BSc Audiology MB011/MB019 & BSc
Speech-Language Pathology MB010/MB018]"), totals *after* their tables
with slashed variant values ("162/168"), and the MBChB across six study
years with rule-prefixed headings. A bespoke parser handles this while
reusing the shared row grammar and catalogue parser.

**Accurate.** The MBChB reconciles across all six study years exactly
(455 credits), and its years 1–3 computed fees match the published
figures to the rand. FHS professional degrees are **duration-ruled, not
credit-ruled** — the rules print durations but almost no minimum-credit
rules (the exception: intercalated BSc(Med) ≥ 360) — so their
whole-degree checks read `NO_RULE` by design.

**Inconsistent / erroneous / open.** The combined Audiology /
Speech-Language block interleaves both degrees' sub-tables before shared
totals; until a dedicated splitter exists, its specialisation-years
dominate FHS's 70 unresolved. MBChB clinical years (4–6) compute far
below published fees because many clinical rotation codes have no §12
fee row — a billing-model question for the fees office, not a parsing
one. A residue of 39 curriculum rows sits outside any year-table
context.

### 7.5 Science (SCI) — majors, and a degree re-based from courses to credits

*20–23 majors per edition; 2,515 rows; plan codes synthesised as
`SB001` + stream.*

Science's curriculum unit is the **major** ("Major in Mathematics",
`[MAM01]` stream brackets). A BSc student combines majors and electives
under faculty composition rules, so a major's credit sum is deliberately
below any degree total, and **majors print no per-year totals** — their
records carry `no_anchor` (387 major-years), with credit accountability
at degree level.

**The rules finding.** Science re-based its entire degree definition at
the 2025 edition: FB7.1 "at least nine full-year courses" (2021–2024)
becomes "at least 360 NQF credits of which at least 180 must be Science
credits"; FB7.2 "four full-year senior courses" becomes "120 credits at
level 7". The dataset records both regimes as printed (`course_unit`
column — counts are never converted to credits), and the majors rule
silently renumbered FB7.6 → FB7.5 at the same moment — the same
key-on-text-not-code lesson Commerce taught.

**Fees.** Published fees are per degree ("Bachelor of Science" prices
every major; method `degree_flat`), so per-major fee deltas are
indicative only.

**Open.** The high-value next step is a **composed-degree ideal
student**: with majors as data and the composition rules in
`degree_rules.csv`, a builder can synthesise a full BSc (two majors +
electives to the 360 floor) and give Science true whole-degree series
comparable to other faculties. A residue of rows with blank credits
(no catalogue entry to join from) is flagged for revisit.

### 7.6 Humanities (HUM) — forty majors serving two degrees

*39–41 majors per edition; 1,372 rows; plan codes `HB001` + stream.*

Humanities prints "Requirements for a major in X" blocks *inside the
department sections*, as bare "CODE Title" lines — credits and NQF
levels are joined from the book's own catalogue. The same majors serve
both the BA and the BSocSc.

**The rules finding.** Humanities' award minima are **stable across all
six editions** — 3 years, 20 semester courses, 10 senior, 2 majors (at
least one from a Humanities department) — making it the control group of
the credit re-think so far. The extended programme prints the same over
four years; specialised programmes print their own counts (Fine Art: 27
semester courses).

**Scope decisions and open items.** The specialised programmes (Fine
Art, BMus, Social Work, PPE, Film & Media) publish their own fee blocks
but print Commerce-style curricula with their own plan codes — currently
out of scope, and their fee labels surface in the unmatched report by
design. Like Science, majors carry `no_anchor` (534 major-years), fees
match `degree_flat`, and the composed-degree builder is the next step.
A blank-credit residue exists where catalogue joins found no entry;
per-major credit series should be read with that caveat.

### 7.7 The fees handbooks

Six editions parsed into `course_fees` (26,298 rows; the 2025 book alone
yields 4,496 with zero conflicting fees) and
`programme_fees_published` (3,197 rows). Notable handling: a state
machine separates fee rows from interleaved margin notes in §11; amount
formats vary by edition (`R 91 190`, `R 84690`, `R 68,900`) and all
three parse; one 2024/2025 page prints two rows character-interleaved
(recovered via a documented override); `N`-suffixed course variants
(~R600, assumed exam-only) are excluded from costing pending
confirmation. Published-fee matching is by name with a curated alias
table (fees-book "Analytics" = handbook "Statistics and Data Sciences"),
duration-aware for Academic Development variants, and labels its method
on every row — including the structural `flat_annual` (Law) and
`degree_flat` (Science/Humanities) cases.

## 8. State of the dataset

Consistent / resolved / unresolved per faculty and edition (Science and
Humanities major-years are `no_anchor` by design):

| Year | COM | EBE | LAW | FHS | SCI | HUM |
|---|---|---|---|---|---|---|
| 2021 | 227 / 17 / 30 | 85 / 0 / 5 | 11 / 0 / 1 | 7 / 0 / 12 | 66 | 89 |
| 2022 | 240 / 11 / 24 | 86 / 0 / 4 | 11 / 0 / 1 | 8 / 0 / 11 | 66 | 88 |
| 2023 | 225 / 15 / 36 | 88 / 0 / 2 | 11 / 0 / 1 | 14 / 0 / 11 | 60 | 88 |
| 2024 | 203 / 13 / 55 | 86 / 0 / 4 | 10 / 0 / 2 | 14 / 0 / 11 | 63 | 91 |
| 2025 | 219 / 13 / 36 | 84 / 0 / 6 | 10 / 0 / 2 | 11 / 0 / 12 | 66 | 91 |
| 2026 | 202 / 11 / 48 | 80 / 0 / 10 | 7 / 0 / 0 | 10 / 0 / 13 | 66 | 87 |

Whole-degree reconciliation against the rules layer: 237 OK, 33
BELOW_MIN, 18 ELECTIVE_GAP, 687 NO_RULE (degrees whose books print
durations but no credit rule — chiefly the AD variants and the FHS
professional degrees). Every BELOW_MIN row is a curriculum printed below
its own faculty's stated floor — review material in itself.

What remains open, in value order: reviewing Commerce's 44 provisional
adjudications; the EBE/LAW/FHS adjudication passes (much smaller since
the engine refinements); the Audiology/Speech-Language splitter; the
SCI/HUM composed-degree builder; then the analysis layer itself
(`analysis/` is still empty — see §10).

## 9. Why the numbers can be trusted

1. **Immutability and provenance.** Sources are read-only; every row
   points to its page.
2. **Determinism.** Same inputs, same outputs, byte-for-byte; re-running
   one year/faculty provably cannot alter another.
3. **Separation of fact and judgment.** The as-printed layer is a
   faithful record; every departure from it in the final layer carries a
   rule class, evidence, confidence, and written rationale, and is
   reversible.
4. **Triangulated validation.** Credits check against printed totals;
   costs against published fees; whole degrees against faculty rules —
   three independent legs, each producing public exception reports
   rather than silent absorption.
5. **External reproduction.** The strongest check is that computed costs
   reproduce UCT's independently published fee figures to the rand for
   most of Commerce, EBE and the MBChB's pre-clinical years.

## 10. Recommendation: a DuckDB exploration layer

The dataset is complete enough that its consumers should no longer need
to open CSVs. The recommendation — validated against the actual files
during the writing of this report — is a two-part layer: a **DuckDB
database as the semantic layer**, and a **visual, narrative interface**
on top of it.

### 10.1 Why DuckDB

- **Zero infrastructure, one file.** `analysis/handbooks.duckdb` ships
  in (or is built from) the repo; no server, no accounts. It reads the
  processed CSVs directly (`read_csv_auto` handles every table today,
  including the union of per-year validation reports), so the CSVs stay
  the versioned source of truth and the database is a disposable build
  artifact — consistent with the project's determinism rule.
- **Fast and analytical.** Columnar execution makes the natural queries
  (six-edition trajectories, faculty roll-ups, cohort comparisons)
  instant at this scale and at 10× this scale.
- **A semantic layer in SQL.** Views encode the project's hard-won
  semantics once, so every downstream tool inherits them instead of
  re-implementing them (the `no_anchor` rule, the fee-method labels, the
  final-vs-as-printed distinction).
- **Universal connectivity.** Python/pandas, R, Excel/Power BI (via
  ODBC), Evidence, Streamlit, Superset, and the DuckDB CLI/notebook UI
  all read it natively.

### 10.2 The database design

A ~60-line build script (`analysis/build_database.py`) creates the file:
raw tables loaded 1:1 from `data/processed/*.csv` and
`validation/*_<year>.csv` (typed, with a `report` column for the
per-year files), plus semantic views. The essential views:

```sql
-- Credit trajectory per programme-year across editions (the core chart)
CREATE VIEW v_credit_series AS
SELECT plan_code, faculty, degree_abbrev, specialisation, variant,
       study_year, year AS edition, final_credits, final_credit_status,
       confidence, credits_stated, source_page
FROM ideal_student_summary_final;

-- Whole-degree load vs the printed rules floor, per edition
CREATE VIEW v_degree_vs_rule AS
SELECT s.year, s.faculty, s.plan_code, s.degree_abbrev,
       sum(s.final_credits) AS degree_credits,
       r.min_total_credits  AS rule_floor,
       sum(s.final_credits) - r.min_total_credits AS surplus
FROM ideal_student_summary_final s
LEFT JOIN degree_rules r
  ON r.year = s.year AND r.degree_scope = s.degree_abbrev
GROUP BY ALL;

-- Rule changes: every degree-level requirement that moved between editions
CREATE VIEW v_rule_changes AS
SELECT degree_scope, rule_kind, year, value, quote, source_page,
       lag(value) OVER (PARTITION BY degree_scope, rule_kind
                        ORDER BY year) AS previous_value
FROM degree_rules QUALIFY value IS DISTINCT FROM previous_value;

-- Fee reconciliation with structural labels first-class
CREATE VIEW v_fee_reconciliation AS
SELECT year, faculty, plan_code, study_year, final_fee_zar,
       fee_published_zar, fee_delta_pct, fee_match_method,
       fee_estimated_component_zar,
       fee_match_method IN ('flat_annual','degree_flat') AS structural
FROM ideal_student_summary_final;

-- The quality ledger and the human work-queue
CREATE VIEW v_quality AS
SELECT year, faculty, final_credit_status, confidence, count(*) AS n
FROM ideal_student_summary_final GROUP BY ALL;
CREATE VIEW v_pending_queue AS
SELECT * FROM pending_adjudication ORDER BY abs(credits_ideal - credits_stated) DESC;
```

(Column names above follow the current CSVs; the build script is the one
place to adjust if they evolve.)

### 10.3 The interface

**Primary recommendation: [Evidence](https://evidence.dev)** — a
markdown-plus-SQL static-site framework with first-class DuckDB support.
Pages are written exactly like this project's documentation (markdown,
versioned in git, reviewable in diffs), each chart backed by a visible
SQL query against the views above, and the built site is polished enough
to put in front of a dean or Senate without apology. It produces a
*narrative* — the medium this project's findings deserve — rather than a
wall of filters. Alternative if the team prefers to stay pure-Python:
**Streamlit** (interactive, quick to build, ideal for internal working
sessions such as adjudication review) — the two are complementary, and
both read the same `.duckdb` file, which is the point of the semantic
layer.

Recommended page inventory, each drawing only on the views:

1. **Overview** — KPI band (editions, faculties, rows, % reconciled,
   median fee delta); a six-faculty timeline annotated with every rule
   change from `v_rule_changes`.
2. **The credit re-think** — small-multiple trajectories per faculty:
   whole-degree credits per edition with the rules floor drawn as a
   stepped line underneath (`v_degree_vs_rule`) — the BBusSc floor
   dropping under an unchanged curriculum, and EBE curricula sliding
   down toward a floor that moves later, are each a single striking
   chart.
3. **Faculty pages** (one per faculty) — the §7 narrative of this
   report, live: register, per-programme trajectories, findings tables.
4. **Programme drill-down** — pick a plan code: year-by-year curriculum
   grid with ideal-student rows highlighted, credits and fees per year,
   the printed totals beside computed ones, and every number carrying
   its `source_page` chip.
5. **Fees** — computed-vs-published scatter by faculty with structural
   methods (`flat_annual`, `degree_flat`) visually separated; estimated
   components shown as ranges, never false precision.
6. **Data quality & adjudication** — the §8 table as a heatmap;
   confidence badges; the pending queue sorted by delta with suggested
   actions — doubling as the reviewer's worklist.
7. **Method** — the two layers, the rule taxonomy, and the register,
   condensed from this report.

Design concerns to honour throughout (these are semantics, not
styling): never plot `no_anchor` majors as if they were whole degrees;
always label structural fee divergence as structural; default every view
to the final layer with an explicit as-printed toggle; show confidence
wherever a resolved number appears; and keep provenance one click away
everywhere — the page reference is the project's signature and should be
the interface's too.

### 10.4 Suggested build order

1. `analysis/build_database.py` + views, committed with a `make db`-style
   one-liner (半 day).
2. Evidence project under `analysis/explorer/` with pages 1, 2 and 6
   (the highest-value trio) (1–2 days).
3. Programme drill-down and faculty pages (1–2 days).
4. Streamlit adjudication-review companion, if the register review
   process (§8) wants interactivity (optional).

---

## Appendix A — file inventory

| Location | Contents |
|---|---|
| `faculty-handbooks-undergraduate/` | 42 source PDFs, immutable |
| `data/processed/main_dataset_final.csv` | the final-clean dataset (analysis) |
| `data/processed/ideal_student_summary_final.csv` | final per specialisation-year roll-up |
| `data/processed/main_dataset.csv`, `ideal_student_summary.csv` | as-printed layer (audit) |
| `data/processed/degree_rules.csv` | the rules layer |
| `data/processed/` (others) | register, curriculum, catalogue, fees tables |
| `resolutions/<faculty>.csv` | adjudication registers with rationales |
| `validation/` | per-year exception reports, degree checks, pending queues, resolution logs |
| `docs/USER-MANUAL.md` (+ .docx) | reviewer/dean manual |
| `docs/REPLICATION.md` | process log and 40-hazard catalogue |
| `docs/FINAL-DATASET-METHOD.md` | final-layer rule taxonomy |
| `docs/commerce-review-and-proposal.md` | original design document |

## Appendix B — glossary (compact)

**Plan code** — 10-character programme key (`CB004FTX04`); called a
specialisation (COM/EBE/LAW/FHS) or major (SCI/HUM). **Edition** — the
handbook year (`year` column). **Ideal student** — the deterministic
course selection of §4. **Stated total** — the handbook's printed
per-year credit total. **Rules floor** — the faculty rules' printed
minimum credits for the whole degree. **`no_anchor`** — a SCI/HUM
major-year: no per-year total exists to reconcile against, by design.
**`flat_annual` / `degree_flat`** — published-fee structures (one fee
per stream / per degree). **Register** — a faculty's adjudication file
in `resolutions/`. **Provenance** — the `year` + `source_page` columns
on every row.
