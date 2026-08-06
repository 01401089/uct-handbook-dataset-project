SELECT
  (SELECT count(*) FROM main_dataset)                     AS curriculum_records,
  (SELECT count(*) FROM specialisations)                  AS register_entries,
  (SELECT count(DISTINCT year) FROM main_dataset)         AS editions,
  (SELECT count(DISTINCT faculty) FROM main_dataset)      AS faculties,
  (SELECT count(*) FROM ideal_student_summary_final)      AS spec_years,
  (SELECT count(*) FROM ideal_student_summary_final
    WHERE final_credit_status = 'consistent')             AS n_consistent,
  (SELECT count(*) FROM ideal_student_summary_final
    WHERE final_credit_status LIKE 'resolved%')           AS n_resolved,
  (SELECT count(*) FROM ideal_student_summary_final
    WHERE final_credit_status = 'unresolved')             AS n_unresolved,
  (SELECT count(*) FROM ideal_student_summary_final
    WHERE final_credit_status = 'no_anchor')              AS n_no_anchor,
  (SELECT count(*) FROM degree_rules)                     AS rule_statements,
  (SELECT count(*) FROM resolutions)                      AS adjudications
