---
title: Programmes & majors
sidebar_position: 4
---

Every programme and major in the dataset. Search by code, degree or name;
click through for the full profile — credit and fee trajectories, the ideal
student's course lists, and page-level provenance.

```sql all_programmes
SELECT '/programmes/' || plan_code AS link, plan_code, faculty,
       degree_abbrev, specialisation, variant,
       first_edition, last_edition
FROM handbooks.programmes
ORDER BY faculty, plan_code
```

<DataTable data={all_programmes} search=true rows=25>
  <Column id=link contentType=link linkLabel=plan_code title="Code" />
  <Column id=faculty />
  <Column id=degree_abbrev title="Degree" />
  <Column id=specialisation title="Specialisation / major" />
  <Column id=variant />
  <Column id=first_edition title="From" fmt=id />
  <Column id=last_edition title="To" fmt=id />
</DataTable>
