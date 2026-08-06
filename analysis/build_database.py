"""Build analysis/handbooks.duckdb — the DuckDB semantic layer.

The processed CSVs remain the versioned source of truth; the database is a
disposable build artifact (gitignored) rebuilt from them at any time:

    python analysis/build_database.py            # writes analysis/handbooks.duckdb
    python analysis/build_database.py --db PATH  # elsewhere (e.g. a scratch copy)

Layers created:
  raw tables    — every data/processed/*.csv 1:1, each validation report
                  family unioned across years, the per-faculty adjudication
                  registers unioned into one table
  semantic views — v_* views encoding the project's semantics once (the
                  no_anchor rule, structural fee labels, rule-change
                  detection with the EBE cohort/phase-in caveats) so every
                  downstream tool inherits them; documented in
                  docs/PROJECT-REPORT.md §10.

Explore interactively with:  duckdb analysis/handbooks.duckdb
"""
import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
VALIDATION = ROOT / "validation"
RESOLUTIONS = ROOT / "resolutions"

# Validation report families, unioned across their per-year files.
REPORT_FAMILIES = [
    "credit_check", "fee_check", "missing_fees", "degree_check",
    "pending_adjudication", "resolution_log", "fees_unparsed",
]

# Real-rand normalisation is expressed in this base year's rands (the
# project's baseline edition). Nominal fee trends conflate curriculum change
# with UCT's annual fee escalation; the deflator separates them.
BASE_YEAR = 2025

# The internal fee deflator: for each consecutive edition pair, the median
# fee ratio across ALL course codes present in both fees books (~3,850-3,930
# matches per pair; the interquartile range is ~±0.05pp, i.e. UCT applies a
# near-uniform annual escalation, so one university-wide number per year is
# essentially exact). Chained and rebased so index_2025 = 1.0 at BASE_YEAR;
# real fee = nominal / index_2025.
FEE_INDEX_SQL = f"""
    CREATE TABLE fee_index AS
    WITH ratios AS (
        SELECT a.year + 1 AS year,
               median(b.fee_zar / a.fee_zar) AS yoy_ratio,
               count(*) AS matched_codes
        FROM course_fees a
        JOIN course_fees b
          ON b.course_code = a.course_code AND b.year = a.year + 1
        WHERE a.fee_zar > 0 AND b.fee_zar > 0
        GROUP BY a.year + 1
    ),
    years AS (SELECT DISTINCT year FROM course_fees),
    chained AS (
        SELECT y.year,
               coalesce(exp(sum(ln(r.yoy_ratio))), 1.0) AS idx_from_first
        FROM years y
        LEFT JOIN ratios r ON r.year <= y.year
        GROUP BY y.year
    )
    SELECT c.year,
           r.yoy_ratio,
           r.matched_codes,
           c.idx_from_first
             / (SELECT idx_from_first FROM chained WHERE year = {BASE_YEAR})
             AS index_2025
    FROM chained c
    LEFT JOIN ratios r USING (year)
    ORDER BY c.year"""

VIEWS = {
    # Credit trajectory per programme-year across editions (the core chart).
    # Provenance drill-down joins main_dataset_final on
    # (year, plan_code, study_year) for per-row source_page.
    "v_credit_series": """
        SELECT plan_code, faculty, degree_abbrev, specialisation, variant,
               study_year, year AS edition, final_credits,
               final_credit_status, confidence, credits_stated
        FROM ideal_student_summary_final""",

    # Whole-degree final credits per plan code per edition — the backbone of
    # the re-think trajectory charts. unresolved_years > 0 marks series
    # points whose sum includes low-confidence years.
    "v_degree_credit_series": """
        SELECT s.year AS edition, s.faculty, s.plan_code,
               any_value(s.degree_abbrev) AS degree_abbrev,
               any_value(s.specialisation) AS specialisation,
               any_value(s.variant) AS variant,
               count(*) AS n_years,
               sum(s.final_credits) AS degree_credits,
               sum(s.final_fee_zar) AS degree_fee_zar,
               round(sum(s.final_fee_zar) / any_value(i.index_2025))
                   AS degree_fee_real_2025,
               count(*) FILTER (s.final_credit_status = 'unresolved')
                   AS unresolved_years,
               bool_and(s.final_credit_status = 'no_anchor') AS is_major
        FROM ideal_student_summary_final s
        JOIN fee_index i ON i.year = s.year
        GROUP BY s.year, s.faculty, s.plan_code""",


    # Whole-degree load vs the printed rules floor: the pipeline already did
    # the careful matching (heading text, cohorts, stream totals) — reuse its
    # reports rather than re-deriving the join in SQL.
    "v_degree_vs_rule": """
        SELECT year, faculty, plan_code, degree_abbrev, specialisation,
               variant, n_years, final_credits_total, rule_min_credits,
               rule_basis, surplus, status, unresolved_years
        FROM degree_check""",

    # Every degree whose minimum-credit floor moved between editions.
    # cohort IS NULL drops EBE's cohort-split sentences ("560 if registered
    # from 2025, else 576"); Geomatics 2026 still prints two totals at once
    # (phase-in 519/511 alongside the blanket 576), kept here as printed —
    # aggregate per year or filter on rule_ref before diffing further.
    "v_rule_changes": """
        SELECT faculty, degree_scope, year, previous_value,
               min_total_credits, rule_ref, source_page, quote
        FROM (
            SELECT *, lag(min_total_credits) OVER (
                       PARTITION BY degree_scope ORDER BY year
                   ) AS previous_value
            FROM degree_rules
            WHERE min_total_credits IS NOT NULL AND cohort IS NULL
        )
        WHERE min_total_credits IS DISTINCT FROM previous_value
          AND previous_value IS NOT NULL""",

    # Fee reconciliation with the structural labels first-class: flat_annual
    # (LAW, one fee per stream) and degree_flat (SCI/HUM, one fee per
    # degree) diverge per-year BY DESIGN and must be plotted apart.
    "v_fee_reconciliation": """
        SELECT year, faculty, plan_code, study_year, final_fee_zar,
               fee_published_zar,
               TRY_CAST(fee_delta_pct AS DOUBLE) AS fee_delta_pct,
               fee_match_method, fee_estimated_component_zar,
               final_fee_status,
               coalesce(fee_match_method IN ('flat_annual', 'degree_flat'),
                        FALSE) AS structural
        FROM ideal_student_summary_final""",

    # Fees in constant 2025 rands: nominal / index_2025. This is the series
    # to read "fee income gain/loss" from — nominal trends conflate
    # curriculum change with annual escalation (~4.3-5.8%/yr over
    # 2021-2026), and credit changes are NOT proportional to fee changes
    # (a dropped course may carry little or no fee).
    "v_fee_real": """
        SELECT f.*,
               i.index_2025,
               round(f.final_fee_zar / i.index_2025) AS final_fee_real_2025,
               round(f.fee_published_zar / i.index_2025)
                   AS fee_published_real_2025
        FROM v_fee_reconciliation f
        JOIN fee_index i USING (year)""",

    # The quality ledger behind the per-faculty status tables.
    "v_quality": """
        SELECT year, faculty, final_credit_status, confidence,
               count(*) AS n
        FROM ideal_student_summary_final
        GROUP BY ALL""",

    # The human work-queue, largest credit gaps first.
    "v_pending_queue": """
        SELECT *,
               abs(coalesce(TRY_CAST(credits_ideal AS DOUBLE), 0)
                   - coalesce(TRY_CAST(credits_stated AS DOUBLE), 0))
                   AS credit_gap
        FROM pending_adjudication
        ORDER BY credit_gap DESC""",

    # The ideal student's actual course lists (drill-down grid), with
    # provenance on every row.
    "v_ideal_courses": """
        SELECT year AS edition, faculty, plan_code, study_year, course_code,
               course_title, nqf_credits, nqf_level, requirement,
               fee_zar, fee_source, resolution_class, resolution_ref,
               source_page
        FROM main_dataset_final
        WHERE final_included""",
}


def build(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # disposable artifact: always a clean rebuild
    con = duckdb.connect(str(db_path))

    def load(table: str, pattern: str, union: bool = False) -> int:
        opts = ", union_by_name=true" if union else ""
        con.execute(
            f"CREATE TABLE {table} AS "
            f"SELECT * FROM read_csv_auto('{pattern}'{opts})"
        )
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    print(f"building {db_path}")
    print("-- processed tables")
    for csv in sorted(PROCESSED.glob("*.csv")):
        n = load(csv.stem, csv.as_posix())
        print(f"   {csv.stem:32s} {n:7d} rows")

    print("-- validation report families (unioned across years)")
    for fam in REPORT_FAMILIES:
        pattern = (VALIDATION / f"{fam}_*.csv").as_posix()
        n = load(fam, pattern, union=True)
        print(f"   {fam:32s} {n:7d} rows")

    print("-- adjudication registers")
    n = load("resolutions", (RESOLUTIONS / "*.csv").as_posix(), union=True)
    print(f"   {'resolutions':32s} {n:7d} rows")

    print("-- fee deflator (matched-course index, base 2025)")
    con.execute(FEE_INDEX_SQL)
    for year, ratio, matched, idx in con.execute(
            "SELECT * FROM fee_index ORDER BY year").fetchall():
        yoy = f"{100 * (ratio - 1):+.2f}%" if ratio else "   —  "
        print(f"   {year}: yoy {yoy}  matched {matched or 0:5d}  "
              f"index_2025 {idx:.4f}")

    print("-- semantic views")
    for name, sql in VIEWS.items():
        con.execute(f"CREATE VIEW {name} AS {sql}")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"   {name:32s} {n:7d} rows")

    # Sanity checks: the semantic layer must agree with the source tables.
    checks = [
        ("main_dataset and main_dataset_final are row-parallel",
         "SELECT (SELECT count(*) FROM main_dataset) ="
         " (SELECT count(*) FROM main_dataset_final)"),
        ("v_credit_series covers every specialisation-year",
         "SELECT (SELECT count(*) FROM v_credit_series) ="
         " (SELECT count(*) FROM ideal_student_summary_final)"),
        ("no_anchor appears only in SCI/HUM",
         "SELECT NOT EXISTS (SELECT 1 FROM v_credit_series WHERE"
         " final_credit_status = 'no_anchor'"
         " AND faculty NOT IN ('SCI', 'HUM'))"),
        ("structural fee methods appear only in LAW/SCI/HUM",
         "SELECT NOT EXISTS (SELECT 1 FROM v_fee_reconciliation WHERE"
         " structural AND faculty NOT IN ('LAW', 'SCI', 'HUM'))"),
        ("every edition 2021-2026 is present",
         "SELECT count(DISTINCT year) = 6 FROM ideal_student_summary_final"),
        ("fee index is 1.0 at the base year",
         f"SELECT abs(index_2025 - 1.0) < 1e-9 FROM fee_index"
         f" WHERE year = {BASE_YEAR}"),
        ("fee index covers every edition",
         "SELECT NOT EXISTS (SELECT 1 FROM ideal_student_summary_final s"
         " LEFT JOIN fee_index i ON i.year = s.year WHERE i.year IS NULL)"),
        ("year-over-year escalation is plausible (0-15%) on >=1000 matches",
         "SELECT bool_and(yoy_ratio BETWEEN 1.0 AND 1.15"
         " AND matched_codes >= 1000) FROM fee_index"
         " WHERE yoy_ratio IS NOT NULL"),
    ]
    print("-- sanity checks")
    failed = 0
    for label, sql in checks:
        ok = bool(con.execute(sql).fetchone()[0])
        print(f"   {'OK ' if ok else 'FAIL'} {label}")
        failed += not ok
    con.close()
    if failed:
        raise SystemExit(f"{failed} sanity check(s) failed")
    print(f"done: {db_path} ({db_path.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path,
                    default=ROOT / "analysis" / "handbooks.duckdb")
    args = ap.parse_args()
    build(args.db)


if __name__ == "__main__":
    main()
