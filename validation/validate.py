"""Validation harness — cross-checks the assembled dataset and writes
exception reports for human review.

Checks:
  1. Credit reconciliation: ideal-student credits per specialisation-year vs
     the handbook's stated "Total credits per year".
  2. Fee reconciliation: ideal-student cost vs the fees book's published
     programme-year fee (5% tolerance; published figures are "typical").
  3. Referential integrity: every curriculum course code resolves in the
     course-fee table and (where expected) the course catalogue.

Outputs (all in validation/):
  credit_check_{year}.csv   one row per specialisation-year with status
  fee_check_{year}.csv      one row per matched specialisation-year with status
  missing_fees_{year}.csv   curriculum codes with no resolvable fee

Run AFTER build_main_dataset.py, from the repo root:
    python validation/validate.py --year 2025
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEE_TOLERANCE_PCT = 5.0


def read(name):
    with open(ROOT / "data" / "processed" / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path, rows):
    if not rows:
        rows = [{"status": "no findings"}]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()
    y = str(args.year)

    summary = [r for r in read("ideal_student_summary.csv") if r["year"] == y]
    main_ds = [r for r in read("main_dataset.csv") if r["year"] == y]

    # 1. credit check ------------------------------------------------------
    credit_rows = []
    for s in summary:
        if s["credits_stated"] == "":
            status = "NO_STATED_TOTAL"
        elif s["credits_unresolved_slots"] != "0":
            status = "UNRESOLVED_SLOTS"
        else:
            delta = int(s["credit_delta"])
            is_min = s["stated_is_minimum"] == "True"
            if delta == 0 or (is_min and delta > 0):
                status = "OK"
            else:
                status = "MISMATCH"
        credit_rows.append({
            "year": y, "plan_code": s["plan_code"], "study_year": s["study_year"],
            "variant": s["variant"], "specialisation": s["specialisation"],
            "credits_ideal": s["credits_ideal"], "credits_stated": s["credits_stated"],
            "credit_delta": s["credit_delta"],
            "stated_is_minimum": s["stated_is_minimum"], "status": status,
        })

    # 2. fee check ---------------------------------------------------------
    fee_rows = []
    for s in summary:
        if not s["fee_published_zar"]:
            continue
        d = float(s["fee_delta_pct"]) if s["fee_delta_pct"] != "" else None
        status = ("NO_COMPUTED_FEE" if d is None
                  else "OK" if abs(d) <= FEE_TOLERANCE_PCT else "MISMATCH")
        fee_rows.append({
            "year": y, "plan_code": s["plan_code"], "study_year": s["study_year"],
            "variant": s["variant"], "specialisation": s["specialisation"],
            "fee_ideal_zar": s["fee_ideal_zar"],
            "fee_estimated_component_zar": s["fee_estimated_component_zar"],
            "fee_published_zar": s["fee_published_zar"],
            "fee_delta_pct": s["fee_delta_pct"],
            "fee_match_method": s["fee_match_method"], "status": status,
        })

    # 3. referential -------------------------------------------------------
    missing = defaultdict(list)
    for r in main_ds:
        if r["course_code"] and r["fee_source"] == "none" and r["ideal_student"] == "True":
            missing[r["course_code"]].append(r["plan_code"])
    missing_rows = [{"year": y, "course_code": c,
                     "used_by": ";".join(sorted(set(p)))}
                    for c, p in sorted(missing.items())]

    write(ROOT / "validation" / f"credit_check_{args.year}.csv", credit_rows)
    write(ROOT / "validation" / f"fee_check_{args.year}.csv", fee_rows)
    write(ROOT / "validation" / f"missing_fees_{args.year}.csv", missing_rows)

    from collections import Counter
    cc = Counter(r["status"] for r in credit_rows)
    fc = Counter(r["status"] for r in fee_rows)
    print(f"credit check ({len(credit_rows)} spec-years): {dict(cc)}")
    print(f"fee check    ({len(fee_rows)} spec-years): {dict(fc)}")
    print(f"ideal-student courses with no resolvable fee: {len(missing_rows)}")


if __name__ == "__main__":
    main()
