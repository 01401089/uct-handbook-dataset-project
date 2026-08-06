---
title: Faculty
hide_title: true
---

```sql fac_name
SELECT CASE '${params.faculty}'
         WHEN 'COM' THEN 'Commerce'
         WHEN 'EBE' THEN 'Engineering & the Built Environment'
         WHEN 'LAW' THEN 'Law'
         WHEN 'FHS' THEN 'Health Sciences'
         WHEN 'SCI' THEN 'Science'
         WHEN 'HUM' THEN 'Humanities'
       END AS name
```

# {params.faculty} — <Value data={fac_name} column=name />

```sql fac_kpis
SELECT count(DISTINCT plan_code) AS programmes,
       count(*) AS spec_years,
       sum(CASE WHEN final_credit_status = 'consistent' THEN 1 ELSE 0 END) AS consistent,
       sum(CASE WHEN final_credit_status = 'unresolved' THEN 1 ELSE 0 END) AS unresolved
FROM handbooks.credit_series
WHERE faculty = '${params.faculty}'
```

<BigValue data={fac_kpis} value=programmes title="Programmes / majors" />
<BigValue data={fac_kpis} value=spec_years title="Specialisation-years" />
<BigValue data={fac_kpis} value=consistent title="Consistent" />
<BigValue data={fac_kpis} value=unresolved title="Unresolved" />

{#if params.faculty === 'SCI' || params.faculty === 'HUM'}

> **This faculty's curriculum unit is the *major*, not the whole degree.** A
> BSc/BA/BSocSc student combines majors and electives under the faculty's
> composition rules, so a major's credit sum is deliberately below any degree
> total. Majors print no per-year credit totals — their records carry
> `no_anchor`, and credit accountability lives in the degree-level rules
> (`degree_rules`). Published fees are per degree, applied to every major
> (`degree_flat`), so per-major fee deltas are indicative only.

{/if}

{#if params.faculty === 'EBE'}

> The EBE handbook prints elective loads as **ranges** ("0–48 credits"); the
> ideal student takes the minimum, so curricula legitimately sit below the
> rules floor (`ELECTIVE_GAP`). The faculty also instructs students to
> complete degrees by *counting courses*, not NQF credits — worth remembering
> when comparing credit sums across editions.

{/if}

## Reconciliation by edition

```sql fac_quality
SELECT year AS edition,
       CASE
         WHEN final_credit_status = 'consistent' THEN 'consistent'
         WHEN final_credit_status LIKE 'resolved%' THEN 'resolved'
         WHEN final_credit_status = 'no_anchor' THEN 'no anchor (majors)'
         ELSE 'unresolved'
       END AS status,
       sum(n) AS n
FROM handbooks.quality
WHERE faculty = '${params.faculty}'
GROUP BY ALL
```

<BarChart
  data={fac_quality}
  x=edition xFmt=id
  y=n
  series=status
  type=stacked
  seriesOrder={['consistent','resolved','unresolved','no anchor (majors)']}
  seriesColors={{'consistent':'#0ca30c','resolved':'#fab219','unresolved':'#ec835a','no anchor (majors)':'#898781'}}
  yAxisTitle="specialisation-years"
  title="Status per edition"
/>

## Programmes, latest edition

Whole-programme credit sums against the printed rules floor, in the most
recent edition each programme appears in. Click through for the full profile.

```sql fac_programmes
WITH latest AS (
  SELECT plan_code, max(edition) AS edition
  FROM handbooks.degree_series
  WHERE faculty = '${params.faculty}'
  GROUP BY plan_code
)
SELECT '/programmes/' || s.plan_code AS link, s.plan_code,
       p.degree_abbrev, p.specialisation, p.variant,
       s.edition, s.degree_credits, r.rule_min_credits, r.status
FROM handbooks.degree_series s
JOIN latest USING (plan_code, edition)
LEFT JOIN handbooks.programmes p ON p.plan_code = s.plan_code
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
ORDER BY s.plan_code
```

<DataTable data={fac_programmes} search=true rows=30>
  <Column id=link contentType=link linkLabel=plan_code title="Code" />
  <Column id=degree_abbrev title="Degree" />
  <Column id=specialisation title="Specialisation / major" />
  <Column id=variant />
  <Column id=edition title="Latest edition" fmt=id />
  <Column id=degree_credits title="Credits" />
  <Column id=rule_min_credits title="Floor" />
  <Column id=status title="Degree check" />
</DataTable>

## Open findings

Unresolved specialisation-years in this faculty's adjudication queue, largest
gaps first.

```sql fac_queue
SELECT '/programmes/' || plan_code AS link, plan_code, year AS edition,
       study_year, credits_ideal, credits_stated, credit_gap, suggested_action
FROM handbooks.pending_queue
WHERE faculty = '${params.faculty}'
ORDER BY credit_gap DESC
```

{#if params.faculty === 'SCI' || params.faculty === 'HUM'}

Nothing is pending by design — major-years carry `no_anchor` and are kept out
of the adjudication queue.

{:else}

<DataTable data={fac_queue} search=true rows=15>
  <Column id=link contentType=link linkLabel=plan_code title="Programme" />
  <Column id=edition fmt=id />
  <Column id=study_year title="Year" />
  <Column id=credits_ideal title="Computed" />
  <Column id=credits_stated title="Stated" />
  <Column id=credit_gap title="Gap" />
  <Column id=suggested_action title="Suggested action" wrap=true />
</DataTable>

{/if}
