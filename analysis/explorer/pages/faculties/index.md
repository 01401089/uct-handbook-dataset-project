---
title: Faculties
sidebar_position: 3
---

One page per faculty: its programmes, reconciliation record, credit changes
and open findings.

```sql fac_summary
SELECT '/faculties/' || faculty AS link, faculty,
       CASE faculty
         WHEN 'COM' THEN 'Commerce'
         WHEN 'EBE' THEN 'Engineering & the Built Environment'
         WHEN 'LAW' THEN 'Law'
         WHEN 'FHS' THEN 'Health Sciences'
         WHEN 'SCI' THEN 'Science'
         WHEN 'HUM' THEN 'Humanities'
       END AS name,
       count(DISTINCT plan_code) AS programmes,
       count(*) AS spec_years,
       sum(CASE WHEN final_credit_status = 'consistent' THEN 1 ELSE 0 END) AS consistent,
       sum(CASE WHEN final_credit_status = 'unresolved' THEN 1 ELSE 0 END) AS unresolved,
       sum(CASE WHEN final_credit_status = 'no_anchor' THEN 1 ELSE 0 END) AS no_anchor
FROM handbooks.credit_series
GROUP BY faculty
ORDER BY faculty
```

<DataTable data={fac_summary} rows=6>
  <Column id=link contentType=link linkLabel=faculty title="Faculty" />
  <Column id=name title="Name" />
  <Column id=programmes title="Programmes / majors" />
  <Column id=spec_years title="Specialisation-years" />
  <Column id=consistent />
  <Column id=unresolved />
  <Column id=no_anchor title="No anchor (majors)" />
</DataTable>
