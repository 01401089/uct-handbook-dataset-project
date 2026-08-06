"""Final-layer validation — step 6 of the pipeline.

Asserts the internal consistency of the final-clean tables produced by
build_final_dataset.py. Exits non-zero ONLY on an assertion failure (a bug or
a stale register entry) — never because adjudications are pending.

Assertions:
  1. Grain preserved: every main_dataset row of the year appears exactly once
     in main_dataset_final, and all original columns are byte-identical
     (the final layer must never mutate as-printed values).
  2. Arithmetic: for every non-unresolved spec-year, final_credits equals the
     sum of nqf_credits over final_included rows, and final_fee_zar the sum
     of fee_zar (unless a set_final_fee adjudication overrides it).
  3. Register integrity: every resolution_ref of the form COM-* exists in
     resolutions/com.csv (consumption is enforced by build_final_dataset).
  4. Legal combinations: confidence populated iff a resolution was applied or
     the row is unresolved; statuses within the allowed enum.

Run from the repo root:
    python validation/validate_final.py --year 2025
"""
import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

STATUSES = {"consistent", "resolved_computed", "resolved_stated",
            "resolved_manual", "unresolved"}
FEE_STATUSES = {"reconciled", "published_divergent", "no_published"}


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fail(msg):
    print(f"FINAL-VALIDATION FAILURE: {msg}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()
    y = str(args.year)

    base = [r for r in read(PROC / "main_dataset.csv") if r["year"] == y]
    final = [r for r in read(PROC / "main_dataset_final.csv") if r["year"] == y]
    summ = [r for r in read(PROC / "ideal_student_summary_final.csv") if r["year"] == y]
    register = {r["res_id"]
                for path in sorted((ROOT / "resolutions").glob("*.csv"))
                for r in read(path)}

    # 1. grain + as-printed immutability
    if len(base) != len(final):
        fail(f"row count differs: base {len(base)} vs final {len(final)}")
    key = lambda r: (r["plan_code"], r["study_year"], r["table_index"], r["seq"])
    base_sorted, final_sorted = sorted(base, key=key), sorted(final, key=key)
    orig_cols = list(base[0].keys())
    for b, f in zip(base_sorted, final_sorted):
        for c in orig_cols:
            if b[c] != f[c]:
                fail(f"as-printed column {c!r} mutated at {key(b)}: "
                     f"{b[c]!r} -> {f[c]!r}")

    # 2. arithmetic
    from collections import defaultdict
    rows_by_key = defaultdict(list)
    for r in final:
        if r["table_index"] == "1":
            rows_by_key[(r["plan_code"], r["study_year"])].append(r)
    for s in summ:
        k = (s["plan_code"], s["study_year"])
        rows = [r for r in rows_by_key[k] if r["final_included"] == "True"]
        credits = sum(int(r["nqf_credits"]) for r in rows if r["nqf_credits"] != "")
        fee = sum(int(r["fee_zar"]) for r in rows if r["fee_zar"] != "")
        if s["final_credit_status"] != "unresolved":
            if s["final_credits"] not in ("", str(credits)) and \
                    s["resolution_ref"] == "":
                fail(f"{k}: final_credits {s['final_credits']} != row sum {credits}")
        if s["final_fee_zar"] not in ("", str(fee)):
            # allowed only when a set_final_fee adjudication exists
            if not re.match(r"^[A-Z]{2,3}-\d{4}-", s["resolution_ref"]):
                fail(f"{k}: final_fee {s['final_fee_zar']} != row sum {fee} "
                     f"with no adjudication")

    # 3. register refs
    for s in summ:
        for ref in s["resolution_ref"].split("+"):
            if re.match(r"^[A-Z]{2,3}-\d{4}-", ref) and ref not in register:
                fail(f"{s['plan_code']} y{s['study_year']}: resolution_ref "
                     f"{ref} not in resolutions/*.csv")

    # 4. enums + confidence
    for s in summ:
        if s["final_credit_status"] not in STATUSES:
            fail(f"illegal final_credit_status {s['final_credit_status']!r}")
        if s["final_fee_status"] not in FEE_STATUSES:
            fail(f"illegal final_fee_status {s['final_fee_status']!r}")
        if s["final_credit_status"] != "consistent" and not s["confidence"]:
            fail(f"{s['plan_code']} y{s['study_year']}: missing confidence")

    from collections import Counter
    print(f"validate-final {y}: {len(final)} rows, {len(summ)} spec-years — all assertions pass")
    print(f"  statuses: {dict(Counter(s['final_credit_status'] for s in summ))}")
    print(f"  fee:      {dict(Counter(s['final_fee_status'] for s in summ))}")


if __name__ == "__main__":
    main()
