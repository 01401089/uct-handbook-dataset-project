---
title: Fees — computed vs published
sidebar_position: 5
---

Each programme-year's cost is computed course-by-course from the fees book,
then compared with UCT's independently published "typical annual fee". Where
both sides can be tested, the computation reproduces the published figure —
the strongest external check on the whole dataset.

```sql med_by_fac
SELECT faculty,
       median(abs(fee_delta_pct)) / 100 AS med_delta,
       count(*) AS n
FROM handbooks.fee_reconciliation
WHERE fee_delta_pct IS NOT NULL AND NOT structural
GROUP BY faculty ORDER BY faculty
```

<BigValue data={med_by_fac.where(`faculty = 'COM'`)} value=med_delta title="COM median |Δ|" fmt=pct2 />
<BigValue data={med_by_fac.where(`faculty = 'EBE'`)} value=med_delta title="EBE median |Δ|" fmt=pct2 />
<BigValue data={med_by_fac.where(`faculty = 'FHS'`)} value=med_delta title="FHS median |Δ|" fmt=pct2 />

## In 2025 rands: separating curriculum change from price escalation

Nominal fee trends conflate two things: what the curriculum asks students to
take, and UCT's annual fee escalation. The dataset derives its own deflator
from the fees books — for each consecutive edition pair, the median fee
ratio across every course code present in both books (~3,900 matched codes
per pair; the spread is a few hundredths of a percentage point, i.e. the
escalation is applied near-uniformly across the fee book). **Fee income
gain/loss should be read from the real series, not inferred from credits** —
a dropped course may carry little or no fee.

```sql fee_index
SELECT year AS edition, yoy_ratio - 1 AS escalation, matched_codes,
       index_2025
FROM handbooks.fee_index ORDER BY edition
```

<DataTable data={fee_index}>
  <Column id=edition fmt=id />
  <Column id=escalation title="Escalation vs prior edition" fmt=pct2 />
  <Column id=matched_codes title="Matched course codes" />
  <Column id=index_2025 title="Index (2025 = 1.0)" fmt='0.0000' />
</DataTable>

```sql real_example
SELECT year AS edition, final_fee_zar AS "Nominal", final_fee_real_2025 AS "Real 2025"
FROM handbooks.fee_real
WHERE plan_code = 'CB019BUS01' AND study_year = 1
ORDER BY edition
```

<LineChart data={real_example} x=edition xFmt=id
  y={['Nominal','Real 2025']}
  colorPalette={['#898781','#2a78d6']} yAxisTitle="ZAR" yFmt='#,##0'
  title="Worked example — BCom Actuarial Science year 1"
  subtitle="Nominal +29% over six editions; flat in 2025 rands" />

The nominal series rises 29% over 2021–2026; in 2025 rands the fee is
essentially flat — *even through the 2024 credit cut*, whose dropped credits
carried no fee. Credit changes are not a proxy for fee-income changes.

## Distribution of differences (comparable fees)

Histograms of the percentage difference between computed and published fees,
for the faculties whose fees are published per programme-year. Trimmed to
±25% for readability; the outliers appear in the divergence table below.

```sql hist_com
SELECT fee_delta_pct / 100 AS delta FROM handbooks.fee_reconciliation
WHERE faculty = 'COM' AND fee_delta_pct IS NOT NULL AND NOT structural
  AND abs(fee_delta_pct) <= 25
```

```sql hist_ebe
SELECT fee_delta_pct / 100 AS delta FROM handbooks.fee_reconciliation
WHERE faculty = 'EBE' AND fee_delta_pct IS NOT NULL AND NOT structural
  AND abs(fee_delta_pct) <= 25
```

```sql hist_fhs
SELECT fee_delta_pct / 100 AS delta FROM handbooks.fee_reconciliation
WHERE faculty = 'FHS' AND fee_delta_pct IS NOT NULL AND NOT structural
  AND abs(fee_delta_pct) <= 25
```

<Grid cols=3>
<Histogram data={hist_com} x=delta xFmt=pct fillColor="#2a78d6"
  title="COM" subtitle="computed vs published, % difference" />
<Histogram data={hist_ebe} x=delta xFmt=pct fillColor="#eb6834"
  title="EBE" subtitle="computed vs published, % difference" />
<Histogram data={hist_fhs} x=delta xFmt=pct fillColor="#eda100"
  title="FHS" subtitle="computed vs published, % difference" />
</Grid>

## Structural divergence is not error

Three faculties publish fees at a coarser grain than the year, so per-year
differences are **expected by design** and labelled, never "corrected":

```sql structural
SELECT faculty, fee_match_method,
       median(abs(fee_delta_pct)) / 100 AS med_delta,
       count(*) AS n
FROM handbooks.fee_reconciliation
WHERE fee_delta_pct IS NOT NULL AND structural
GROUP BY ALL ORDER BY faculty
```

<DataTable data={structural}>
  <Column id=faculty />
  <Column id=fee_match_method title="Published structure" />
  <Column id=med_delta title="Median |Δ|" fmt=pct1 />
  <Column id=n title="Programme-years" />
</DataTable>

- **`flat_annual`** — Law publishes one flat annual fee per LLB stream; the
  graduate stream's year 1 still matches to the rand.
- **`degree_flat`** — Science and Humanities publish one fee per degree,
  covering every major; per-major deltas are indicative only.

## Largest divergences (comparable fees only)

Worth reading with the findings pages: the biggest gaps are mostly
menu-inflated estimates (a choice menu with no printed pick-rule) or clinical
years whose rotation codes carry no fee row — documented cases, not noise.

```sql divergences
SELECT '/programmes/' || plan_code AS link, plan_code, faculty, year AS edition,
       study_year, final_fee_zar, fee_published_zar,
       fee_delta_pct / 100 AS delta, fee_match_method
FROM handbooks.fee_reconciliation
WHERE fee_delta_pct IS NOT NULL AND NOT structural
ORDER BY abs(fee_delta_pct) DESC
LIMIT 30
```

<DataTable data={divergences} search=true rows=15>
  <Column id=link contentType=link linkLabel=plan_code title="Programme" />
  <Column id=faculty />
  <Column id=edition fmt=id />
  <Column id=study_year title="Year" />
  <Column id=final_fee_zar title="Computed (R)" fmt='#,##0' />
  <Column id=fee_published_zar title="Published (R)" fmt='#,##0' />
  <Column id=delta title="Δ" fmt=pct1 contentType=delta downIsGood=true />
  <Column id=fee_match_method title="Match method" />
</DataTable>

*Elective-slot costs are median-based estimates and are always carried in a
separate column (`fee_estimated_component_zar`) so exact-figure analyses can
exclude them.*
