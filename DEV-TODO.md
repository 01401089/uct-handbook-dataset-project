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
- Blank-credit rows: a residue of SCI/HUM curriculum rows have no credits
  (no catalogue entry to join from); revisit joins or flag per row.
- Specialised HUM programmes (Fine Art, BMus, BSW, PPE, Film & Media)
  publish their own fee blocks but have no major rows — decide whether to
  extract them as programmes (they print COM-style curricula with own
  plan codes) or leave them out of scope.
- SCI/HUM adjudication registers are empty (nothing pending by design —
  major-years are `no_anchor`).

## 6. Analysis layer

- `analysis/` trend queries over `ideal_student_summary_final.csv`:
  credit-load and cost per specialisation across editions, faculty-level
  aggregates, augmented/extended vs regular comparisons.
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
