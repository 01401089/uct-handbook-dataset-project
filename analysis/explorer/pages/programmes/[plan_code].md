---
title: Programme profile
hide_title: true
---

```sql prog_info
SELECT plan_code, faculty, degree_abbrev, specialisation, variant,
       first_edition, last_edition
FROM handbooks.programmes
WHERE plan_code = '${params.plan_code}'
```

# {params.plan_code} — <Value data={prog_info} column=specialisation />

**<Value data={prog_info} column=degree_abbrev />** ·
faculty <Value data={prog_info} column=faculty /> ·
variant <Value data={prog_info} column=variant /> ·
editions <Value data={prog_info} column=first_edition fmt=id />–<Value data={prog_info} column=last_edition fmt=id />

## Credit load per year of study

```sql per_year
SELECT edition, edition::int::varchar AS edition_label,
       'year ' || study_year::int AS study_year, final_credits,
       credits_stated, final_credit_status, confidence
FROM handbooks.credit_series
WHERE plan_code = '${params.plan_code}'
ORDER BY edition, study_year
```

<LineChart
  data={per_year}
  x=edition xFmt=id
  y=final_credits
  series=study_year
  colorPalette={['#9ec5f4','#6da7ec','#3987e5','#256abf','#184f95','#0d366b']}
  yAxisTitle="credits"
  title="Credits per study year, by edition"
  subtitle="Ordinal series: light→dark = year 1→6"
/>

<DataTable data={per_year} rows=40 groupBy=edition_label subtotals=true>
  <Column id=study_year title="Study year" />
  <Column id=final_credits title="Final credits" />
  <Column id=credits_stated title="Stated total" />
  <Column id=final_credit_status title="Status" />
  <Column id=confidence />
</DataTable>

## Whole-programme load vs the rules floor

```sql whole
SELECT s.edition, s.degree_credits, r.rule_min_credits, r.status
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = '${params.plan_code}'
ORDER BY s.edition
```

<LineChart data={whole} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#2a78d6','#898781']} yAxisTitle="credits"
  title="Whole-programme credits vs printed minimum" />

## Cost

```sql fees
SELECT year AS edition, year::int::varchar AS edition_label,
       'year ' || study_year::int AS study_year,
       study_year AS study_year_n, final_fee_zar, fee_published_zar,
       final_fee_real_2025,
       final_fee_zar AS "Computed",
       fee_published_zar AS "Published",
       final_fee_real_2025 AS "Real 2025",
       fee_match_method, fee_delta_pct / 100 AS delta
FROM handbooks.fee_real
WHERE plan_code = '${params.plan_code}'
ORDER BY edition, study_year_n
```

Nominal computed and published fees, alongside the computed fee at constant
2025 prices (deflated by the matched-course fee index) — **read fee income
gain/loss from the Real 2025 series**. For `flat_annual` / `degree_flat`
programmes the published fee legitimately diverges per year.

<LineChart
  data={fees.where(`study_year_n = 1`)}
  x=edition xFmt=id
  y={['Computed','Published','Real 2025']}
  colorPalette={['#86b6ef','#898781','#256abf']}
  yAxisTitle="ZAR"
  yFmt='#,##0'
  title="Year-1 cost by edition"
  subtitle="Nominal computed & published; Real 2025 = constant prices"
/>

<DataTable data={fees} rows=40 groupBy=edition_label subtotals=true>
  <Column id=study_year title="Study year" />
  <Column id=final_fee_zar title="Computed (R)" fmt='#,##0' />
  <Column id=final_fee_real_2025 title="Computed (2025 R)" fmt='#,##0' />
  <Column id=fee_published_zar title="Published (R)" fmt='#,##0' />
  <Column id=delta title="Δ" fmt=pct1 totalAgg="-" />
  <Column id=fee_match_method title="Match method" />
</DataTable>

## The ideal student's courses

Every course the ideal student takes, with the PDF page each row came from.

```sql editions_list
SELECT DISTINCT edition FROM handbooks.ideal_courses
WHERE plan_code = '${params.plan_code}'
ORDER BY edition DESC
```

<Dropdown data={editions_list} name=ed value=edition title="Edition" />

```sql courses
SELECT 'year ' || study_year::int AS study_year, course_code, course_title,
       nqf_credits, nqf_level::int::varchar AS nqf_level,
       requirement, fee_zar, fee_source,
       'p' || source_page::int::varchar AS source_page
FROM handbooks.ideal_courses
WHERE plan_code = '${params.plan_code}'
  AND edition = ${inputs.ed.value}
ORDER BY study_year, course_code
```

<DataTable data={courses} rows=60 groupBy=study_year subtotals=true>
  <Column id=course_code title="Code" />
  <Column id=course_title title="Course" wrap=true />
  <Column id=nqf_credits title="Credits" />
  <Column id=nqf_level title="NQF level" />
  <Column id=requirement />
  <Column id=fee_zar title="Fee (R)" fmt='#,##0' />
  <Column id=fee_source title="Fee source" />
  <Column id=source_page title="PDF page" />
</DataTable>

*Provenance: `PDF page` refers to the year's handbook in
`faculty-handbooks-undergraduate/` — every number above is checkable against
the original in seconds.*
