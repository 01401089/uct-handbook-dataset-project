# The Final-Clean Dataset — Method and Justification

*How `main_dataset_final.csv` and `ideal_student_summary_final.csv` resolve
the errors and inconsistencies preserved in the as-printed layer.*

## 1. The routing principle

Every discrepancy in this project is one of two kinds, and each kind is fixed
in a different place:

- **Parse artifacts** — the PDF *prints* correct values but text extraction
  garbled them (interleaved characters, unusual number formats, layout
  drift). These are fixed **upstream**, in the extractors and their
  `overrides` files, because the as-printed layer's contract is "exactly what
  the handbook prints". Examples: the character-interleaved fee rows of 2024
  and 2025; the `R 68,900` comma-format published fee.
- **Print errors and ambiguities** — the handbook itself is wrong,
  self-contradictory, or silent (a misprinted total, a choice menu with no
  selection rule). These are resolved **downstream**, in the final-clean
  layer, so the as-printed tables remain a faithful record of the
  publication. The resolution, its rule, its evidence and its confidence are
  recorded on every affected row.

The as-printed tables are therefore never edited by the final layer —
`validate_final.py` asserts byte-identity of every original column.

## 2. The rule catalogue

Rules apply in a fixed order — **R0 → R3 → R1 → R2 → R4** — so that human
adjudication (R3) always pre-empts automatic rules, and arithmetic certainty
(R1) pre-empts cross-edition inference (R2).

| Rule | Trigger | Resolution | Confidence |
|---|---|---|---|
| **R0** pass-through | computed credits equal the stated total (or exceed a stated minimum) | none needed | high |
| **R3** adjudication | an entry in `resolutions/com.csv` for this specialisation-year | per the entry's action | high |
| **R1a** OR-double-count | the stated total exceeds the taken-course sum by *exactly* the credits of the non-taken choice rows (all groups, or exactly one group) | trust the taken-course sum — the printed total demonstrably counts both branches of a choice | high |
| **R1b** misprint detector | the gap is ≥ 84 credits and the stated total is a single digit-edit of the row sum (or of the both-branches sum) | none — reported to `pending_adjudication` with a suggested correction for human confirmation | — |
| **R2a** cross-edition | the taken-course set is *identical* to ≥ 2 other editions where credits reconcile exactly, but this edition's stated total diverges | trust the taken-course sum — corroborated by sibling editions | medium |
| **R2b** row-set drift detector | the stated total matches reconciling sibling editions but the extracted course set is unique to this edition | none — reported as a probable extraction gap (`check_extraction`); rows are never fabricated downstream | — |
| **R4** residual | nothing above applies | the **default-trust policy** (`computed`, confirmed by the project owner): carry the taken-course sum, flag `unresolved`, list in `pending_adjudication` | low |

**Why "computed" is the default.** Where both sides can be tested, the rows
win: summing each taken course's fee reproduces UCT's published programme
fees to the rand for most programmes (median delta 0.0%), while stated totals
are demonstrably wrong in identifiable classes (R1a, misprints). The stated
total remains in every output row for comparison, and `--default-trust
stated|none` is available for sensitivity analysis.

**Fees.** `final_fee_zar` is always recomputed from the finally-included
rows. Published-fee divergence is a *reference disagreement*, not a data
error: it is flagged (`final_fee_status = published_divergent`) rather than
"corrected", because the published figures are themselves "typical"
estimates. A wrong published-fee match can be repaired via the register
action `set_published_ref`.

**Confidence rubric.** `high` = same-edition arithmetic identity, or a human
adjudication citing PDF evidence. `medium` = cross-edition inference with
identical row-sets. `low` = the default policy applied without corroboration.

## 3. Worked examples

**CB025BUS09 year 1, 2025 (compound misprint — R3 + R1a).** The handbook
prints "Total credits per year … 382" over a table whose rows sum to 182
counting both branches of its one OR choice (CSC1015F OR ECO1110F, 18
credits), and 164 taking one. The sibling variant CB025BUS01 prints 182 for
the same table. Register entry `COM-2025-008` corrects the anchor (382 → 182,
a single digit-edit); the remaining 18-credit gap is then the OR double-count
and rule R1a resolves the final load to **164** (status `resolved_computed`,
class R3, high confidence).

**CB004INF01 year 1, 2025 (pure R1a).** Rows sum to 150 taking INF1002F, or
168 taking both INF1002F and its alternative CSC1015F; the handbook states
168. The 18-credit excess equals the non-taken branch exactly, so the final
load is **150**. No human judgment required — the arithmetic identity is the
argument.

**CB001ECO02 year 2, 2024 (the R2 non-example).** The stated total 150
matches 2021–2023, where the year reconciles; 2024's rows sum to 132. A
naive cross-edition rule would "fix" the stated total — but the 2024 row-set
genuinely differs (the curriculum changed), so the identical-row-set
precondition fails, no rule fires, and the case is correctly left
**unresolved** for human review. This example is why R2a demands identical
row-sets rather than stable stated totals.

## 4. The adjudication register

`resolutions/com.csv` — schema and workflow in `resolutions/README.md`. The
2026-08 seeding contains **44 provisional entries**
(`decided_by = "provisional (Claude), pending review"`), covering:

- **Unlabelled choice menus** (CSC 4th year, PPE year 2, senior Economics
  years, …): the year table lists a module menu with no printed selection
  rule, so the row sum counts every offering. Adjudicated `accept_stated` —
  the stated total is the only authoritative signal of intended load, stable
  across editions. The computed fee remains menu-inflated and is flagged
  `published_divergent` until the menu rule is confirmed with the faculty.
- **Missing blocks** (open-elective years without a parsable slot line,
  rows unparsed in older layouts): adjudicated `accept_stated`, corroborated
  by sibling editions.
- **The CB025BUS09 misprint** (`set_stated_corrected`, above).

Reviewers amend entries (and `decided_by`) as they confirm or overturn them;
`validate_final.py` fails on stale or unconsumed entries, so register rot is
caught mechanically.

## 5. Outputs and how to read them

| Output | Content |
|---|---|
| `main_dataset_final.csv` | every as-printed row (byte-identical original columns) + `final_included`, `resolution_class`, `resolution_ref`, `final_note` |
| `ideal_student_summary_final.csv` | per specialisation-year: `final_credits`, `credits_stated_corrected`, `final_credit_status`, `final_fee_zar`, `final_fee_status`, `resolution_class/_ref`, `confidence`, `resolution_rationale` |
| `validation/resolution_log_<year>.csv` | every applied resolution with before/after values and evidence |
| `validation/pending_adjudication_<year>.csv` | R4 residuals and detector suggestions, each with a `suggested_action` |

`final_credit_status` values: `consistent` (no discrepancy), `resolved_computed`
(R1a/R2a), `resolved_manual` / `resolved_stated` (register), `unresolved`
(default policy applied; treat with care and see the pending report).

**State of the 2021–2026 load (2026-08-06):** of 1,625 specialisation-years,
**1,315 consistent**, **80 resolved** by rules or adjudications, **230
unresolved** (14%) — almost all small ±6…±24 credit gaps, carried at the
computed value with low confidence and enumerated in the pending reports.

## 6. Pipeline integration

`run_pipeline.py` runs finalise + validate-final for **every loaded year**
after the per-year extraction loop, because cross-edition rules mean any
year's change can legitimately update other years' *final* rows (the
as-printed layer stays append-only per year). The finaliser is a pure
function of (main dataset, summaries, register): re-running it twice is
byte-idempotent, and re-running one year leaves other years' final rows
untouched unless cross-edition evidence actually changed.

New handbook years flow through automatically: unmatched discrepancies
surface as `unresolved` + pending-report entries and **never block the
pipeline** (`--strict` exists for anyone wanting a blocking gate).
