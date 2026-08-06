# Adjudication register

One CSV per faculty (`com.csv` … `hum.csv` — all six exist) holding
**per-case adjudications** of handbook print errors and ambiguities.
Commerce's is the only seeded register so far (44 provisional entries);
EBE/LAW/FHS passes are queued in DEV-TODO.md, and SCI/HUM are empty by
design (major-years carry `no_anchor` — nothing to adjudicate per year). Consumed by
`build_final_dataset.py` (rule R3, which pre-empts all auto-rules). The
as-printed tables are never touched — every adjudication is applied only in
the final-clean layer, with the original values retained alongside.

## Adding an entry

1. Confirm the discrepancy against the PDF (the `source_page` column in the
   as-printed tables points at the page).
2. Append a row (columns below). `res_id` must be unique and stable
   (`<FAC>-<year>-<seq>`, e.g. `COM-2025-008`); one row per
   (year, plan_code, study_year) — a case
   recurring across editions gets one row per year, sharing the rationale.
3. Re-run `python build_final_dataset.py --year <year>` (or the batch
   runner). `validation/validate_final.py` fails if a register row goes
   unconsumed (typo'd plan code / year), so mistakes surface immediately.

## Columns

| Column | Values / meaning |
|---|---|
| `res_id` | `COM-2025-001` — stable, referenced by `resolution_ref` in outputs |
| `year`, `faculty`, `plan_code`, `study_year` | which specialisation-year |
| `scope` | `spec_year` (default), `row`, `published_fee` |
| `row_selector` | course_code (or seq) when scope=row |
| `issue` | `stated_misprint`, `unlabelled_choice_menu`, `or_double_count`, `missing_block`, `fee_label_mismatch`, `other` |
| `action` | `accept_computed`, `accept_stated`, `set_stated_corrected`, `set_final_credits`, `pin_choice`, `include_row`, `exclude_row`, `set_final_fee`, `set_published_ref` |
| `value` | number for set_* actions; `;`-separated course codes for pin_choice |
| `rationale` | the argued justification, in full sentences |
| `evidence` | PDF page refs, cross-edition comparisons, arithmetic |
| `decided_by`, `decided_date` | provenance of the judgment |

`decided_by="provisional (Claude), pending review"` marks machine-proposed
adjudications awaiting human sign-off; amend the row (and `decided_by`) when
reviewed.
