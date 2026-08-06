SELECT plan_code,
       any_value(faculty ORDER BY year DESC) AS faculty,
       any_value(degree_abbrev ORDER BY year DESC) AS degree_abbrev,
       any_value(specialisation ORDER BY year DESC) AS specialisation,
       any_value(variant ORDER BY year DESC) AS variant,
       min(year) AS first_edition,
       max(year) AS last_edition
FROM ideal_student_summary_final
GROUP BY plan_code
