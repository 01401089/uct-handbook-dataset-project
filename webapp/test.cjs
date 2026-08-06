const duckdb = require('duckdb');
const db = new duckdb.Database(':memory:');

db.all("CREATE TABLE ideal_student_summary_final AS SELECT * FROM read_csv_auto('public/data/ideal_student_summary_final.csv', ALL_VARCHAR=TRUE)", function(err, res) {
  if (err) { console.error("Error creating ideal:", err); return; }
  
  db.all("CREATE TABLE fee_inflation_index (year VARCHAR, multiplier_to_2025 DOUBLE)", function(err) {
    if (err) { console.error(err); return; }
    
    db.all("INSERT INTO fee_inflation_index VALUES ('2021', 1.25), ('2022', 1.18), ('2023', 1.11), ('2024', 1.05), ('2025', 1.00), ('2026', 0.95)", function(err) {
      if (err) { console.error(err); return; }
      
      db.all(`
        CREATE VIEW v_ideal_student_summary_real AS 
        SELECT i.*, 
               TRY_CAST(i.final_fee_zar AS DOUBLE) as nominal_cost_numeric, 
               TRY_CAST(i.final_fee_zar AS DOUBLE) * f.multiplier_to_2025 as real_cost_2025 
        FROM ideal_student_summary_final i 
        LEFT JOIN fee_inflation_index f ON i.year = f.year
      `, function(err) {
          if (err) { console.error("Error creating view:", err); return; }
          
          db.all("SELECT study_year, final_credits, real_cost_2025 as cost FROM v_ideal_student_summary_real WHERE plan_code = 'CB004FTX04' AND year = '2025' ORDER BY study_year", function(err, res) {
              if (err) { console.error("Error query1:", err); return; }
              console.log("Result waterfall:", res);
          });

          db.all("SELECT '2024' as edition, SUM(TRY_CAST(final_credits AS DOUBLE)) as total_credits, SUM(real_cost_2025) as real_cost FROM v_ideal_student_summary_real WHERE plan_code = 'CB004FTX04' AND year = '2024'", function(err, res) {
              if (err) { console.error("Error query2:", err); return; }
              console.log("Result diff:", res);
          });
      });
    });
  });
});
