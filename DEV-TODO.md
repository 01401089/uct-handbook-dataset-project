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

## 2. EBE adjudication pass (register is empty)

EBE 2021-2026 is extracted (~90 spec-years/year, ~62% consistent) but
`resolutions/ebe.csv` has no entries yet: ~185 EBE spec-years sit in the
pending reports. Known clusters to adjudicate (same workflow as §1):
- Construction/Property Studies (EB015CON04, EB017CON03): stream/variant
  tables and elective menus inflate row sums (~2× published fees).
- Small −16…−42 gaps in engineering years: elective-range minimums vs stated
  range minimums don't always coincide; decide per family.
- Sub-stream plan codes (Geomatics EB019APG11/EB819APG11): the suppressed
  second stream (EGS specialisation) could be captured via a plan-code
  suffix scheme (e.g. `EB019APG11/B`) if stream-level analysis is wanted;
  also applies to the transferee access routes reusing EB001CHE01/EB002CIV01.

## 3. LAW follow-ups

- Adjudicate the legacy five-year stream (LB003): no printed totals →
  25 spec-years flagged unresolved; `accept_computed` entries with rationale
  would clear them (stream retired after 2019, absent from 2026).
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

## 5. Remaining faculties

- SCI and HUM (major + composition rules — the ideal student is constructed
  from the faculty rules section, not read off a table; bespoke parsers in
  the FHS mould reusing the shared grammar).
- Each faculty gets `extractors/<fac>/`, a `resolutions/<fac>.csv`, and its
  own hazard notes in REPLICATION.md.

## 6. Analysis layer

- `analysis/` trend queries over `ideal_student_summary_final.csv`:
  credit-load and cost per specialisation across editions, faculty-level
  aggregates, augmented/extended vs regular comparisons.
- Flag credit-re-think transition points automatically (year-over-year
  final_credits changes per plan code).

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
