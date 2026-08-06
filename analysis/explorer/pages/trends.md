---
title: Trend cards — credits vs cost
sidebar_position: 2
---

One card per programme: **actual credits** and **cost in 2025 rands**, with
the percentage change from 2021 to the 2025 baseline. Colour reads from the
university's perspective: **reduced credits are green** (the re-think goal)
and **reduced real cost is red** (fee income loss) — the ideal card is green
on both: fewer credits, no real fee income lost.

<TextInput
  name=q
  title="Filter programmes"
  defaultValue=""
  placeholder="e.g. CB001 · FTX04 · Actuarial · BCom"
  description="Matches anywhere in the plan code, name or degree"
/>

```sql cards
WITH s AS (SELECT * FROM handbooks.degree_series),
anchors AS (
  SELECT plan_code,
         min(edition) AS base_ed,
         coalesce(max(edition) FILTER (WHERE edition = 2025), max(edition)) AS anchor_ed
  FROM s GROUP BY plan_code
),
d AS (
  SELECT a.plan_code, a.base_ed, a.anchor_ed,
         b.degree_credits  AS base_credits,
         an.degree_credits AS anchor_credits,
         b.degree_fee_real_2025  AS base_cost,
         an.degree_fee_real_2025 AS anchor_cost,
         an.is_major
  FROM anchors a
  JOIN s b  ON b.plan_code = a.plan_code AND b.edition = a.base_ed
  JOIN s an ON an.plan_code = a.plan_code AND an.edition = a.anchor_ed
  WHERE a.base_ed < a.anchor_ed
)
SELECT d.plan_code,
       d.anchor_credits::int AS anchor_credits,
       d.anchor_cost,
       coalesce(p.specialisation, p.degree_abbrev) AS name,
       p.degree_abbrev,
       p.faculty || ' · Δ ' || d.base_ed::int || '→' || d.anchor_ed::int
         || CASE WHEN d.is_major THEN ' · major' ELSE '' END
         || CASE WHEN p.variant != 'regular' THEN ' · ' || p.variant ELSE '' END
         AS meta,
       upper(d.plan_code || ' ' || coalesce(p.specialisation, '') || ' '
             || coalesce(p.degree_abbrev, '') || ' ' || p.faculty)
         AS searchable,
       d.anchor_ed::int || ' CREDITS' AS credits_label,
       d.anchor_ed::int || ' COST (ZAR)' AS cost_label,
       (d.anchor_credits - d.base_credits) / nullif(d.base_credits, 0)::double
           AS credit_delta,
       (d.anchor_cost - d.base_cost) / nullif(d.base_cost, 0)
           AS cost_delta
FROM d
JOIN handbooks.programmes p USING (plan_code)
ORDER BY d.plan_code
```

```sql series
SELECT plan_code,
       cast(edition::int::varchar || '-01-01' AS date) AS edition_date,
       degree_credits, degree_fee_real_2025
FROM handbooks.degree_series
ORDER BY plan_code, edition
```

{#if cards.length === 0}

Loading the cards…

{:else}

{@const term = String(inputs.q ?? ``).trim().toUpperCase()}
{@const list = cards.filter((c) => c.searchable.includes(term))}

{#if list.length === 0}

No programme matches that filter.

{:else}

Showing **{Math.min(60, list.length)}** of **{list.length}** matching
programmes — type in the filter to narrow the wall.

<Grid cols=2 gapSize=md>

{#each list.slice(0, 60) as c}

<div style="border:1px solid rgba(128,128,128,.3); border-radius:12px; padding:.9rem 1.1rem .7rem;">
  <div style="display:flex; justify-content:space-between; gap:.5rem; font-size:.75rem; opacity:.6;">
    <span>{c.plan_code}</span>
    <span>{c.meta}</span>
  </div>
  <p style="margin:.15rem 0 0; font-weight:700; font-size:1.05rem;"><a href="/programmes/{c.plan_code}" style="color:inherit; text-decoration:none;">{c.degree_abbrev}</a></p>
  <p style="margin:0 0 .6rem; color:#009ADA; font-weight:600;"><a href="/programmes/{c.plan_code}" style="color:inherit; text-decoration:none;">{c.name}</a></p>
  <div style="border-top:1px solid rgba(128,128,128,.22); padding-top:.55rem; display:flex; justify-content:space-between; align-items:flex-end; gap:1rem;">
    <div>
      <p style="margin:0; font-size:.72rem; letter-spacing:.04em; opacity:.65;">{c.credits_label}</p>
      <p style="margin:.15rem 0 0; white-space:nowrap;">
        <span style="font-size:1.3rem; font-weight:700;">{c.anchor_credits}</span>
        <Delta value={c.credit_delta} fmt=pct1 downIsGood=true chip=true />
      </p>
    </div>
    <div style="text-align:right;">
      <p style="margin:0; font-size:.72rem; letter-spacing:.04em; opacity:.65;">{c.cost_label}</p>
      <p style="margin:.15rem 0 0; white-space:nowrap;">
        <Delta value={c.cost_delta} fmt=pct1 chip=true />
        <span style="font-size:1.3rem; font-weight:700;">R {Math.round(c.anchor_cost).toLocaleString()}</span>
      </p>
    </div>
  </div>
  <div style="border-top:1px solid rgba(128,128,128,.22); margin-top:.6rem; padding-top:.45rem; display:flex; gap:1.2rem;">
    <div style="flex:1; min-width:0; text-align:center;">
      <p style="margin:0 0 .2rem; font-size:.75rem; opacity:.65;">Credit trend</p>
      <Sparkline
        data={series.where(`plan_code = '${c.plan_code}'`)}
        dateCol=edition_date valueCol=degree_credits
        dateFmt=yyyy valueFmt=num0
        yScale=true
        color=#1baf7a
        width=135
        height=40
      />
    </div>
    <div style="flex:1; min-width:0; text-align:center;">
      <p style="margin:0 0 .2rem; font-size:.75rem; opacity:.65;">Real fee trend</p>
      <Sparkline
        data={series.where(`plan_code = '${c.plan_code}'`)}
        dateCol=edition_date valueCol=degree_fee_real_2025
        dateFmt=yyyy valueFmt=num0
        yScale=true
        color=#eb6834
        width=135
        height=40
      />
    </div>
  </div>
</div>

{/each}

</Grid>

{/if}

{/if}

*Δ is measured to the 2025 baseline edition (or the latest available for
programmes that end earlier), from the first edition the programme appears
in — each card prints its span. Chips carry the verdict (green/red from the
university's fee-income perspective); trend lines keep fixed colours (teal
credits, orange real fees). Costs are the ideal student's, in constant 2025
rands via the matched-course fee index. Science/Humanities cards are
majors, not whole degrees.*
