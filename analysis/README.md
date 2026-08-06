# Analysis layer

## The DuckDB semantic layer

`build_database.py` builds **`handbooks.duckdb`** — a single-file
analytical database over the processed CSVs. The CSVs remain the
versioned source of truth; the database is a **disposable build
artifact** (gitignored), rebuilt deterministically at any time:

```bash
python analysis/build_database.py
```

Rebuild it after any pipeline run. The build ends with sanity checks
(row parity between layers, `no_anchor` confined to SCI/HUM, structural
fee methods confined to LAW/SCI/HUM, all six editions present) and fails
loudly if the semantic layer disagrees with the source tables.

Explore it with the DuckDB CLI (`duckdb analysis/handbooks.duckdb`),
Python (`duckdb.connect(...)`), R, or anything with an ODBC driver.

### What's inside

**Raw tables** — every `data/processed/*.csv` 1:1
(`main_dataset_final`, `ideal_student_summary_final`, `degree_rules`,
`curriculum`, `courses`, `course_fees`, …), each validation report
family unioned across years (`credit_check`, `fee_check`,
`degree_check`, `pending_adjudication`, `resolution_log`,
`missing_fees`, `fees_unparsed`), and the per-faculty adjudication
registers as one `resolutions` table.

**Semantic views** — the project's semantics encoded once, so every
downstream tool inherits them (rationale in
[docs/PROJECT-REPORT.md](../docs/PROJECT-REPORT.md) §10):

| View | Answers |
|---|---|
| `v_credit_series` | per programme-year credit trajectory across editions, with status + confidence |
| `v_degree_credit_series` | whole-degree credits/fees per plan code per edition (`is_major` flags SCI/HUM `no_anchor` rows — never plot them as degrees) |
| `v_degree_vs_rule` | whole-degree load vs the printed rules floor (from the pipeline's own `degree_check` reconciliation) |
| `v_rule_changes` | every degree whose minimum-credit floor moved between editions, with page + verbatim quote |
| `v_fee_reconciliation` | computed vs published fees; `structural = TRUE` marks `flat_annual`/`degree_flat` methods that diverge by design |
| `fee_index` (table) | the internal deflator: matched-course median escalation per edition pair, chained and rebased to 2025 = 1.0 |
| `v_fee_real` | fees in constant 2025 rands (`final_fee_real_2025`, `fee_published_real_2025`) — read "fee income gain/loss" here, not from nominal series |
| `v_quality` | the consistent/resolved/unresolved/no-anchor ledger per faculty-year |
| `v_pending_queue` | the human adjudication work-queue, largest credit gaps first |
| `v_ideal_courses` | the ideal student's actual course lists with provenance (`source_page`) per row |

### Example queries (verified against the current build)

The credit re-think signature — BCom Actuarial Science year 1:

```sql
SELECT edition, final_credits, credits_stated, final_credit_status
FROM v_credit_series
WHERE plan_code = 'CB019BUS01' AND study_year = 1 ORDER BY edition;
-- 185,185,185 then 180 from the 2024 edition
```

A whole degree sliding against its rules floor — Chemical Engineering:

```sql
SELECT s.edition, s.degree_credits, r.rule_min_credits, r.status
FROM v_degree_credit_series s
JOIN v_degree_vs_rule r ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'EB001CHE01' ORDER BY s.edition;
-- 544 … 496 (2025) … 468 (2026) against a floor of 576 → 560
```

When did each degree's requirement change?

```sql
SELECT faculty, degree_scope, year, previous_value, min_total_credits
FROM v_rule_changes ORDER BY faculty, degree_scope, year;
```

Does the computation reproduce UCT's published fees?

```sql
SELECT faculty, structural, round(median(abs(fee_delta_pct)), 1) AS med_pct
FROM v_fee_reconciliation WHERE fee_delta_pct IS NOT NULL
GROUP BY ALL ORDER BY faculty;
-- COM 0.0 / EBE 0.5 / FHS 1.8; LAW/SCI/HUM structural by design
```

## The visual explorer (`explorer/`)

An [Evidence](https://evidence.dev) site over the database — the
dean-facing interface. Pages: **Overview** (KPIs, the rule-change
timeline, reconciliation by faculty), **The credit re-think** (flagship
trajectories against their rules floors + chart-any-programme),
**Trend cards** (a filterable KPI-card wall — per programme, credits and
real-2025-rand cost with 2021→2025 deltas and sparklines; green = reduced
credits or increased real cost, red = the reverse, reading from the
university's fee-income perspective),
**Faculties** (one templated page per faculty), **Programmes** (a
templated profile per plan code: credit/fee series, the ideal student's
course lists with `source_page` provenance), **Fees**, **Data quality &
adjudication** (the ledger, the BELOW_MIN findings, the pending queue,
the register), and **Method**.

```bash
python analysis/build_database.py       # 1. (re)build handbooks.duckdb
cd analysis/explorer
npm install                             # 2. first time only
npm run sources                         # 3. materialise queries from the db
npm run dev                             # 4. http://localhost:3000
```

`npm run build` produces a static site in `explorer/build/` that can be
hosted anywhere (or shared as a folder). The site's **Documentation page**
serves every project document (report, manual, replication log, method,
READMEs, plus the Word manual for download), rendered to HTML from the
repo's markdown by `explorer/scripts/sync-docs.js` — this runs
automatically before every build/dev start, so the markdown files remain
the single source of truth. Design rules encoded in the
pages: faculty colours are fixed (COM blue, EBE orange, LAW aqua, FHS
yellow, SCI magenta, HUM green — a CVD-validated palette), status colours
are reserved (green consistent / amber resolved / coral unresolved / grey
no-anchor), majors are never plotted as whole degrees, structural fee
divergence is labelled as such, and every number is one click from its
PDF page.
