# Development TODO

Deferred work, tracked here so nothing rides on memory. Ordered by value.

## 1. Adjudication review process (highest value, human-in-the-loop)

The final-clean layer currently carries **44 provisional adjudications**
(`resolutions/com.csv`, `decided_by = "provisional (Claude), pending
review"`) and **~230 unresolved specialisation-years** flagged at low
confidence (`validation/pending_adjudication_<year>.csv`).

**Review workflow to implement/run:**

1. **Confirm the 44 provisional entries.** For each register row: open the
   PDF at the cited page, check the rationale, then either (a) amend
   `decided_by`/`decided_date` to the reviewer's name to confirm, (b) edit
   the action/value and re-run `python build_final_dataset.py --year <y>`,
   or (c) delete the row (the case returns to the pending report). The
   finaliser fails on stale entries, so typos surface immediately.
2. **Work the pending queue, largest deltas first.** Each row carries a
   `suggested_action`:
   - `set_stated_corrected` (R1b) — confirm the misprint and add an R3 row.
   - `check_extraction` (R2b) — the extracted course set is probably
     incomplete; inspect `data/interim/<year>-com-ug.txt` at the source page
     and fix the parser (as-printed fix), NOT the register.
   - `adjudicate in resolutions/com.csv` (R4) — the ±6…±24 tail; decide
     per case or accept the computed default and record `accept_computed`.
3. **Faculty confirmation items** (need someone with curriculum authority):
   - the un-printed selection rules behind the `unlabelled_choice_menu`
     adjudications (CSC 4th year, PPE year 2, senior Economics years) — a
     one-line rule per menu would upgrade `accept_stated` to `pin_choice`,
     fixing the menu-inflated fee estimates too;
   - the `N`-suffix fee-book rows (~R600, assumed exam-only, excluded from
     costing);
   - the AD published-fee variant mapping (`ad_duration` method).
4. **CU020BUS01 (AdvDip Actuarial Science) 2021/2022**: the early-edition
   AdvDip layout prints an approved-course *pool* (pp17-18 of the 2021
   book — every 3000-level ECO course etc.) which the engine read as a
   672-credit year-1 curriculum (300 in 2022; found 2026-08-06 by a
   >250-credit spec-year scan, alongside SCI hazard H41 which was fixed).
   Needs a COM-config fix (recognise the pool as `alternative` rows or an
   elective list), not an adjudication.

**Tooling idea (nice-to-have):** a small `review.py` that walks the pending
report interactively (show row + PDF page reference, prompt for a decision,
append the register row) would make a review session ~10× faster.

## 2. EBE adjudication pass (register is empty; queue much reduced)

The 2026-08 engine fixes (hazards H37-H39: footnote-marked year headings,
elective-core menus, optional-courses sections, "(minimum)" totals, five
slot-line shapes) resolved most of what this pass had queued — EBE is now
**509 consistent / 31 unresolved** spec-years (was 344/185). Remaining:
- Work the ~31 residuals in `validation/pending_adjudication_<year>.csv`
  (mostly small gaps and the 2026 phase-in years); check
  `validation/degree_check_<year>.csv` BELOW_MIN rows first — 2026 BAS
  (376 vs the 432 rule) and 2026 Property Studies (411 vs its stated 452)
  are handbook-side inconsistencies needing adjudication entries.
- Sub-stream plan codes (Geomatics EB019APG11/EB819APG11): the suppressed
  second stream (EGS specialisation) could be captured via a plan-code
  suffix scheme (e.g. `EB019APG11/B`) if stream-level analysis is wanted;
  also applies to the transferee access routes reusing EB001CHE01/EB002CIV01.

## 3. LAW follow-ups

- ~~Adjudicate LB003 (25 unresolved spec-years, "no printed totals")~~ —
  **superseded 2026-08-06**: LB003 *does* print per-year totals in a third
  wording, and wraps discontinued-course rows before their credits (hazard
  H40); both are parsed now and LB003 reconciles to its printed 660-credit
  stream total. 7 spec-years remain unresolved — the 2024/2025 editions
  drop discontinued rows from print (genuine drift); adjudicate those from
  the pending reports.
- The two-year graduate LLB stream shares LP001's printed table; if
  stream-level analysis is wanted, model it as a variant.

## 4. FHS follow-ups

- **Audiology / Speech-Language combined block**: the two degrees' sub-
  tables interleave inside one block with shared slashed totals; a dedicated
  sub-splitter (detect the per-degree sub-headings between tables) would
  separate MB011/MB019 from MB010/MB018 curricula and clear most FHS
  unresolved spec-years.
- MBChB clinical-year fees: years 4–6 computed fees are far below published
  (many clinical rotation codes have no §12 fee row) — confirm billing
  model with the fees office before adjudicating.
- 39 curriculum rows carry no study_year (orphans outside any table
  context) — inspect and either home or exclude via register.
- FHS adjudication pass (registers empty).

## 5. SCI/HUM follow-ups (extraction + rules layer landed 2026-08-06)

- **Composed-degree ideal student** (the big one): majors are now data and
  the composition rules are in `degree_rules.csv` (SCI FB7.1-7.5, HUM
  award minima) — a builder could synthesise a full BSc/BA/BSocSc
  curriculum (2 majors + electives to the minimum) and give SCI/HUM true
  whole-degree credit/fee series comparable to the other faculties.
- Blank-credit rows: HUM retains 124 curriculum rows with no credits (no
  catalogue entry to join from); revisit joins or flag per row. SCI's
  blanks all turned out to be the H41 postgraduate spill and are gone
  since the 2026-08-06 fix.
- Specialised HUM programmes (Fine Art, BMus, BSW, PPE, Film & Media)
  publish their own fee blocks but have no major rows — decide whether to
  extract them as programmes (they print COM-style curricula with own
  plan codes) or leave them out of scope.
- SCI/HUM adjudication registers are empty (nothing pending by design —
  major-years are `no_anchor`).

## 6. Analysis layer

- ~~DuckDB semantic layer~~ — **done 2026-08-06**:
  `analysis/build_database.py` builds `handbooks.duckdb` (all processed
  tables + unioned validation reports + `v_*` semantic views, with
  build-time sanity checks). Trend queries now run against
  `v_credit_series` / `v_degree_credit_series` / `v_rule_changes`.
- ~~Visual explorer~~ — **done 2026-08-06**: Evidence site in
  `analysis/explorer/` (overview, credit re-think, faculty and programme
  drill-downs, fees, quality/adjudication queue, method — run
  instructions in `analysis/README.md`). Optional Streamlit
  adjudication-review companion still open if register review wants
  interactivity.
- Remaining query work: faculty-level aggregates, augmented/extended vs
  regular comparisons.
- ~~Real-rand (2025) fee normalisation~~ — **built 2026-08-06**:
  `fee_index` table (matched-course deflator: ~3,850-3,930 matched codes
  per consecutive pair, IQR ≈ ±0.05pp; 2021→22 +4.27%, 22→23 +5.14%,
  23→24 +4.55%, 24→25 +5.83%, 25→26 +4.67%; chained, 2025=1) +
  `v_fee_real` view + `degree_fee_real_2025` in
  `v_degree_credit_series`, with build-time sanity checks (base-year
  index = 1.0, full edition coverage, plausible escalation band).
  Explorer: "In 2025 rands" section on the fees page, real-terms chart +
  column on programme profiles, method note. The as-printed and final
  CSV layers stay nominal (as-printed principle). Still open: optional
  re-pricing-at-2025 cross-check (same-code coverage 87.6-97.6%/year);
  fallback for future sparse years is per-faculty indices, then
  published programme-fee ratios.
- **Composed-degree archetype for SCI/HUM** (design sharpened
  2026-08-06; supersedes the sketch in §5): per major and edition,
  synthesise "major + rules-minimum completion": the major's own courses
  as core, plus elective-slot filler priced at the faculty's median
  fee-per-credit at the levels the rules require, sized to the printed
  composition rules (SCI FB7.1 360 cr with FB7.2 120@L7, FB7.5 ≥1
  major; HUM FB2-FB6 20 semester courses / 10 senior / 2 majors — the
  second HUM major is represented statistically by the filler, never by
  pairing with a real partner major, so a partner's own curriculum
  changes cannot contaminate the analysed major's trend). Hold the SCI
  target at 360 credits for pre-2025 editions (the faculty itself
  equated "nine full-year courses" with 360 in the 2025 re-basing;
  record as assumption). Output: a derived `composed_degree_summary`
  (prototype in the analysis layer first; promote to a pipeline step
  once the conventions are signed off), status `rule_anchor`, validated
  against `degree_rules`, and — the payoff — finally comparable to the
  `degree_flat` published BSc/BA fees.
- Flag credit-re-think transition points automatically (year-over-year
  final_credits changes per plan code) — and join them against
  `degree_rules.csv` rule changes (BBusSc 623→528 at 2025, EBE FB3.2
  576→560 at 2026, LLB 660→637 at 2026) to separate rule-driven cuts from
  curriculum-table drift.

## 6b. Rules-layer follow-ups (from the 2026-08 rules sweep)

Optional tables the rules sections could still yield (evidence and page
refs in the sweep notes; build only if analysis needs them):
- **Progression ladders**: minimum cumulative semester-courses per year of
  registration (COM FBx3.2 families, stable 2021-2026) — a plausibility
  check on per-year course counts.
- **AD↔mainstream substitution maps**: printed 2021-2023 only (COM
  FBD1.2/FBE1.2/FBH1/FBI1: ACC1106F↔ACC1006F, …) — would align augmented
  variants to mainstream courses for like-for-like cost comparison.
- **EBE elective-category minima**: the per-programme "ELECTIVE COURSES"
  category rules (Chemical: science ≥42, humanities ≥18→15, advanced
  engineering ≥32, free ≥16→12; sum 126→104 at 2025) — closes the "0-48"
  ranges more precisely than the range minimum.
- **Choice-menu cardinality imputation**: pin the CSC 4th-year menus in
  2023/2025 to "pick 2" via the sibling editions (needs the faculty
  confirmation queued in §1.3).
- **Handbook 3 (General Rules)** is cited normatively by every faculty's
  rules (credit/exemption rules GB2/GB3); source it if exemption modelling
  is ever needed.

## 7. Smaller engineering items

- `run_pipeline.py`: parallelise the per-year loop (years are independent).
- Course catalogue coverage: ~50-100 curriculum courses per year have no
  catalogue entry (taught by faculties whose handbooks aren't loaded);
  revisit once more faculties land.
- Consider parquet mirrors of the processed CSVs if files grow past
  reviewable size.
- `PROGRAMME_FEE_OVERRIDES` mechanism (designed, not yet needed): add if a
  future fees book has a genuinely garbled published fee that the amount
  grammar cannot recover.
