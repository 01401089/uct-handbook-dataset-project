---
title: Data quality & adjudication
sidebar_position: 6
---

Every specialisation-year is reconciled against its printed credit total.
Nothing is silently corrected: what reconciles is `consistent`; what a
documented rule or adjudication fixes is `resolved`; what remains is
`unresolved` — carried at the computed value, flagged at low confidence, and
listed here as the human work-queue. Science/Humanities majors have **no
per-year anchor by design** and are excluded from that queue.

```sql counts
SELECT * FROM handbooks.counts
```

<BigValue data={counts} value=n_consistent title="Consistent" fmt='#,##0' />
<BigValue data={counts} value=n_resolved title="Resolved" />
<BigValue data={counts} value=n_unresolved title="Unresolved" />
<BigValue data={counts} value=n_no_anchor title="No anchor (majors)" />
<BigValue data={counts} value=adjudications title="Register entries" />

## The ledger, per faculty and edition

```sql quality_matrix
SELECT faculty, year AS edition,
       sum(n) FILTER (final_credit_status = 'consistent')      AS consistent,
       sum(n) FILTER (final_credit_status LIKE 'resolved%')    AS resolved,
       sum(n) FILTER (final_credit_status = 'unresolved')      AS unresolved,
       sum(n) FILTER (final_credit_status = 'no_anchor')       AS no_anchor,
       sum(n) FILTER (final_credit_status = 'unresolved')
         / nullif(sum(n) FILTER (final_credit_status != 'no_anchor'), 0)::double
         AS unresolved_share
FROM handbooks.quality
GROUP BY ALL
ORDER BY faculty, edition
```

<DataTable data={quality_matrix} rows=40>
  <Column id=faculty />
  <Column id=edition fmt=id />
  <Column id=consistent />
  <Column id=resolved />
  <Column id=unresolved />
  <Column id=no_anchor title="No anchor" />
  <Column id=unresolved_share title="Unresolved share of anchored" fmt=pct1 contentType=colorscale colorScale={['#fcfcfb','#ec835a']} />
</DataTable>

## Whole-degree findings from the rules layer

Curricula that no longer sum to their own faculty's printed floor. `BELOW_MIN`
with electives at range-minimum is `ELECTIVE_GAP`; a hard `BELOW_MIN` is a
handbook-side inconsistency worth editorial attention.

```sql degree_findings
SELECT '/programmes/' || plan_code AS link, plan_code, faculty, year AS edition,
       degree_abbrev, final_credits_total, rule_min_credits, surplus, status
FROM handbooks.degree_vs_rule
WHERE status IN ('BELOW_MIN')
ORDER BY surplus ASC
```

<DataTable data={degree_findings} rows=15 search=true>
  <Column id=link contentType=link linkLabel=plan_code title="Programme" />
  <Column id=faculty />
  <Column id=edition fmt=id />
  <Column id=degree_abbrev title="Degree" />
  <Column id=final_credits_total title="Curriculum sum" />
  <Column id=rule_min_credits title="Printed floor" />
  <Column id=surplus contentType=delta downIsGood=false />
</DataTable>

## The adjudication queue

Unresolved cases, largest credit gaps first, each with the detector's
suggested action. Working this queue — confirming misprints, checking
extractions, recording decisions in the faculty registers — is the highest
value contribution a reviewer can make.

```sql queue
SELECT '/programmes/' || plan_code AS link, plan_code, faculty, year AS edition,
       study_year, credits_ideal, credits_stated, credit_gap,
       detector, suggested_action
FROM handbooks.pending_queue
ORDER BY credit_gap DESC
```

<DataTable data={queue} search=true rows=20>
  <Column id=link contentType=link linkLabel=plan_code title="Programme" />
  <Column id=faculty />
  <Column id=edition fmt=id />
  <Column id=study_year title="Year" />
  <Column id=credits_ideal title="Computed" />
  <Column id=credits_stated title="Stated" />
  <Column id=credit_gap title="Gap" />
  <Column id=detector />
  <Column id=suggested_action title="Suggested action" wrap=true />
</DataTable>

## The adjudication register

Every human decision applied by the final layer, with its written rationale
and page evidence. Entries marked *provisional (Claude), pending review* await
sign-off.

```sql register
SELECT res_id, year AS edition, faculty, plan_code, study_year, issue, action,
       value, rationale, evidence, decided_by
FROM handbooks.resolutions
ORDER BY res_id
```

<DataTable data={register} search=true rows=15 wrapTitles=true>
  <Column id=res_id title="Ref" />
  <Column id=edition fmt=id />
  <Column id=plan_code title="Programme" />
  <Column id=study_year title="Year" />
  <Column id=issue />
  <Column id=action />
  <Column id=rationale wrap=true />
  <Column id=evidence wrap=true />
  <Column id=decided_by title="Decided by" />
</DataTable>
