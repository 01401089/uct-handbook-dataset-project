---
title: The credit re-think
sidebar_position: 1
---

Two different mechanisms of change are visible in the books. In **Commerce the
rules moved first**: the BBusSc floor fell 623→528 at 2025 while its printed
curricula still sum 544–675 in 2026. In **Engineering the departments moved
first**: Chemical Engineering's curriculum falls 544→496→468 across 2024→2026,
a year ahead of the faculty rule (576→560 at 2026). Law cut the four-year LLB
660→637 at 2026. Humanities' award minima have not moved at all — the control
group so far.

## Flagship trajectories against their floors

Whole-degree credit load per edition (solid, faculty colour) against the
printed rules floor (grey). *A curriculum below its floor is a finding, not an
error — Engineering's elective ranges are taken at their minimum, and the
degree-check labels that case `ELECTIVE_GAP`.*

```sql flag_com
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'CB019BUS01' ORDER BY s.edition
```

```sql flag_ebe
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'EB001CHE01' ORDER BY s.edition
```

```sql flag_law
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'LB002' ORDER BY s.edition
```

```sql flag_fhs
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'MB001DOM02' ORDER BY s.edition
```

```sql flag_sci
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'SB001MAM01' ORDER BY s.edition
```

```sql flag_hum
SELECT s.edition, s.degree_credits, r.rule_min_credits
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = 'HB001PSY01' ORDER BY s.edition
```

<Grid cols=2>

<LineChart data={flag_com} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#2a78d6','#898781']} yAxisTitle="credits"
  title="COM — BCom Actuarial Science (CB019BUS01)"
  subtitle="Year-1 load fell 185→180 at 2024; floor 528 throughout" />

<LineChart data={flag_ebe} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#eb6834','#898781']} yAxisTitle="credits"
  title="EBE — Chemical Engineering (EB001CHE01)"
  subtitle="544→496→468; the faculty floor only moves at 2026" />

<LineChart data={flag_law} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#1baf7a','#898781']} yAxisTitle="credits"
  title="LAW — four-year undergraduate LLB (LB002)"
  subtitle="660 exactly for five editions, then 637 at 2026" />

<LineChart data={flag_fhs} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#eda100','#898781']} yAxisTitle="credits"
  title="FHS — MBChB (MB001DOM02)"
  subtitle="Six study years, 455 credits; duration-ruled — no floor" />

<LineChart data={flag_sci} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#e87ba4','#898781']} yAxisTitle="credits"
  title="SCI — Mathematics major (SB001MAM01)"
  subtitle="A major, not a degree — the 360 floor binds the whole BSc" />

<LineChart data={flag_hum} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#008300','#898781']} yAxisTitle="credits"
  title="HUM — Psychology major (HB001PSY01)"
  subtitle="Major only; some rows await catalogue credit joins" />

</Grid>

## Chart any programme

```sql fac_list
SELECT DISTINCT faculty FROM handbooks.programmes ORDER BY faculty
```

<Dropdown data={fac_list} name=fac value=faculty title="Faculty" defaultValue="COM" />

```sql prog_list
SELECT plan_code,
       coalesce(specialisation, degree_abbrev, plan_code)
         || ' — ' || plan_code AS label
FROM handbooks.programmes
WHERE faculty = '${inputs.fac.value}'
ORDER BY plan_code
```

<Dropdown data={prog_list} name=prog value=plan_code label=label title="Programme / major" defaultValue="CB019BUS01" />

```sql picked
SELECT s.edition, s.degree_credits, r.rule_min_credits,
       s.unresolved_years, s.n_years
FROM handbooks.degree_series s
LEFT JOIN handbooks.degree_vs_rule r
  ON r.year = s.edition AND r.plan_code = s.plan_code
WHERE s.plan_code = '${inputs.prog.value}'
ORDER BY s.edition
```

<LineChart data={picked} x=edition xFmt=id y={['degree_credits','rule_min_credits']}
  colorPalette={['#2a78d6','#898781']} yAxisTitle="credits"
  title="Whole-programme credit load vs rules floor"
  subtitle="Series points summing any low-confidence years are listed in the table below" />

<DataTable data={picked}>
  <Column id=edition fmt=id />
  <Column id=degree_credits title="Credits (ideal student)" />
  <Column id=rule_min_credits title="Rules floor" />
  <Column id=n_years title="Study years" />
  <Column id=unresolved_years title="Low-confidence years" />
</DataTable>

Full profile with curricula, fees and provenance:
[/programmes/{inputs.prog.value}](/programmes/{inputs.prog.value})
