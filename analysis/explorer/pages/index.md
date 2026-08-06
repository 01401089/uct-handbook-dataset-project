---
title: UCT Handbook Dataset
---

Six editions of every faculty's undergraduate handbook (2021–2026), plus the
student fees handbooks, converted into a relational dataset in which **every
number traces to the page it was printed on**. This explorer sits on the
project's DuckDB semantic layer; the full written account is in
`docs/PROJECT-REPORT.md`.

```sql counts
SELECT * FROM handbooks.counts
```

<BigValue data={counts} value=editions title="Editions" />
<BigValue data={counts} value=faculties title="Faculties" />
<BigValue data={counts} value=curriculum_records title="Curriculum records" fmt='#,##0' />
<BigValue data={counts} value=register_entries title="Programmes & majors" fmt='#,##0' />
<BigValue data={counts} value=rule_statements title="Degree-rule statements" />

## The credit re-think, at rules level

The faculty-rules sections print what each whole degree must total. Those
floors moved — and the dataset dates every move to the edition, with the page
and the printed sentence.

```sql headline_floors
SELECT year AS edition, degree_scope, min_total_credits
FROM handbooks.degree_rules
WHERE cohort IS NULL AND min_total_credits IS NOT NULL
  AND degree_scope IN (
    'Bachelor of Business Science',
    'Bachelor of Commerce',
    '4-year degrees (faculty rule FB3.2)',
    'LLB undergraduate LLB stream')
GROUP BY ALL
ORDER BY degree_scope, edition
```

<LineChart
  data={headline_floors}
  x=edition xFmt=id
  y=min_total_credits
  series=degree_scope
  step=true
  yAxisTitle="minimum credits for the degree"
  title="Printed minimum-credit floors, 2021–2026"
  subtitle="BBusSc 623→528 at 2025 · BCom 450→440 at 2022 · EBE 4-year 576→560 at 2026 · LLB 660→637 at 2026"
/>

```sql rule_changes
SELECT faculty, degree_scope, year AS edition,
       previous_value AS was, min_total_credits AS became,
       min_total_credits - previous_value AS delta,
       rule_ref, source_page
FROM handbooks.rule_changes
ORDER BY faculty, degree_scope, edition
```

Every degree whose printed floor moved between editions:

<DataTable data={rule_changes} rows=20>
  <Column id=faculty />
  <Column id=degree_scope title="Degree / rule scope" />
  <Column id=edition fmt=id />
  <Column id=was />
  <Column id=became />
  <Column id=delta contentType=delta downIsGood=false />
  <Column id=rule_ref title="Rule" />
  <Column id=source_page title="Page" />
</DataTable>

## How much of the dataset reconciles

Each programme-year with a printed credit total is checked against it; Science
and Humanities **majors** print no per-year totals by design ("no anchor" —
their accountability is the degree-level rules above).

```sql quality_by_faculty
SELECT faculty,
       CASE
         WHEN final_credit_status = 'consistent' THEN 'consistent'
         WHEN final_credit_status LIKE 'resolved%' THEN 'resolved'
         WHEN final_credit_status = 'no_anchor' THEN 'no anchor (majors)'
         ELSE 'unresolved'
       END AS status,
       sum(n) AS n
FROM handbooks.quality
GROUP BY ALL
```

<BarChart
  data={quality_by_faculty}
  x=faculty
  y=n
  series=status
  type=stacked
  seriesOrder={['consistent','resolved','unresolved','no anchor (majors)']}
  seriesColors={{'consistent':'#0ca30c','resolved':'#fab219','unresolved':'#ec835a','no anchor (majors)':'#898781'}}
  yAxisTitle="specialisation-years"
  title="Reconciliation status by faculty, all editions"
/>

Of the specialisation-years with a printed anchor, **86% are consistent or
resolved**; every unresolved case is listed with a suggested action on the
[data-quality page](/quality).

## Explore

- **[The credit re-think](/credit-rethink)** — trajectories against the moving floors
- **[Faculties](/faculties)** — one page per faculty: findings, quality, programmes
- **[Programmes](/programmes)** — drill into any programme or major, edition by edition
- **[Fees](/fees)** — computed cost vs UCT's published fees
- **[Data quality](/quality)** — the reconciliation ledger and the adjudication queue
- **[Method](/method)** — how the dataset was built and why it can be trusted
