SELECT q.*, s.faculty, s.specialisation
FROM v_pending_queue q
LEFT JOIN (
    SELECT year, plan_code, any_value(faculty) AS faculty,
           any_value(specialisation) AS specialisation
    FROM specialisations GROUP BY year, plan_code
) s USING (year, plan_code)
