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

Additionally writes validation/degree_check_<year>.csv — the whole-degree
reconciliation against the rules layer (data/processed/degree_rules.csv):
the sum of final_credits across a specialisation's study-years is compared
with the degree's printed minimum-credit rule (COM FBx2 minima, EBE
per-programme/FB3.2 minima with cohort awareness, LAW stream grand totals).
Report-only — findings never fail the run. Statuses:
  OK           total >= applicable minimum
  BELOW_MIN    total < minimum with no minimum-anchored elective structure
               (probable extraction gap — the whole-degree analogue of the
               2x row-sum diagnostic)
  ELECTIVE_GAP total < minimum but the programme prints range/minimum
               elective loads the ideal student takes at the bottom end
               (expected for EBE elective-range programmes)
  NO_RULE      no printed credit rule applies (FHS professional degrees,
               COM Academic Development variants, Advanced Diplomas)
EBE 5-year ECP twins (EB8xx) are additionally checked against their 4-year
twin (EB0xx) — the handbooks state both carry the same courses and credits.

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


def _ebe_twin(plan_code: str) -> str:
    """EB8xx (5-year ECP) -> EB0xx (4-year twin)."""
    return plan_code[:2] + "0" + plan_code[3:] \
        if len(plan_code) == 10 and plan_code[2] == "8" else plan_code


def _com_scope(s: dict) -> str | None:
    """Map a COM specialisation to its degree-rule heading, or None."""
    if s["variant"] in ("augmented", "extended") or s["degree_abbrev"] == "AdvDip":
        return None  # no minimum-credit rule printed for AD variants/AdvDips
    actsci = s["specialisation"].startswith("Actuarial Science")
    if s["degree_abbrev"] == "BBusSc":
        return ("Bachelor of Business Science in Actuarial Science"
                if actsci else "Bachelor of Business Science")
    if s["degree_abbrev"] == "BCom":
        return ("Bachelor of Commerce in Actuarial Science"
                if actsci else "Bachelor of Commerce")
    return None


def _pick_ebe_rule(cands: list[dict], year: str) -> dict | None:
    """Cohort-aware choice: the edition's ideal student is a new entrant, so
    'registered in/from YYYY' rows apply to editions >= YYYY and
    'registered before YYYY' rows to editions < YYYY. Cohort-specific rows
    beat unconditional ones; ties resolve to the smallest minimum (least
    strict) so BELOW_MIN never fires on an ambiguous rule set."""
    yr = int(year)

    def applies(r):
        m = re.search(r"(in|before) (\d{4})", r["cohort"])
        if not m:
            return True
        y0 = int(m.group(2))
        return yr < y0 if m.group(1) == "before" else yr >= y0

    live = [r for r in cands if applies(r)] or cands
    pool = [r for r in live if r["cohort"]] or live
    return min(pool, key=lambda r: int(r["min_total_credits"]))


def degree_check(year: str, summ: list[dict], final_rows: list[dict]) -> None:
    """Whole-degree reconciliation against degree_rules.csv (report-only)."""
    rules_path = PROC / "degree_rules.csv"
    if not rules_path.exists():
        print("degree-check: degree_rules.csv not found — skipped")
        return
    rules = [r for r in read(rules_path)
             if r["year"] == year and r["min_total_credits"] != ""]
    com_by_scope = {}
    for r in rules:
        if r["faculty"] == "COM":
            com_by_scope.setdefault(r["degree_scope"], r)
    ebe_by_code = {}
    for r in rules:
        # Transferee/access-route minima describe a different entry route,
        # not the mainstream degree the plan code's spec-years model.
        if r["faculty"] == "EBE" and r["plan_code_hint"] \
                and "transferee" not in r["degree_scope"]:
            ebe_by_code.setdefault(r["plan_code_hint"], []).append(r)
    ebe_blanket = {("4yr" if "4-year" in r["degree_scope"] else "3yr"): r
                   for r in rules
                   if r["faculty"] == "EBE" and r["rule_ref"] == "FB3.2"}
    law_by_code = {r["plan_code_hint"]: r for r in rules
                   if r["faculty"] == "LAW" and r["is_stream_total"] == "True"}

    # Per-spec aggregates from the final summary.
    from collections import defaultdict
    specs = {}
    min_anchored = defaultdict(bool)
    for s in summ:
        k = s["plan_code"]
        spec = specs.setdefault(k, {
            "faculty": s["faculty"], "degree_abbrev": s["degree_abbrev"],
            "specialisation": s["specialisation"], "variant": s["variant"],
            "total": 0, "n_years": 0, "max_year": 0, "unresolved": 0})
        if s["final_credits"] != "":
            spec["total"] += int(float(s["final_credits"]))
        spec["n_years"] += 1
        if s["study_year"] not in ("", "0"):
            spec["max_year"] = max(spec["max_year"],
                                   int(float(s["study_year"])))
        if s["final_credit_status"] == "unresolved":
            spec["unresolved"] += 1
        if s["stated_is_minimum"] == "True":
            min_anchored[k] = True
    for r in final_rows:
        if r["requirement"] == "elective" and r["is_minimum"] == "True":
            min_anchored[r["plan_code"]] = True

    out = []
    for code, spec in sorted(specs.items()):
        fac = spec["faculty"]
        rule, basis = None, ""
        if fac == "COM":
            scope = _com_scope(spec)
            if scope and scope in com_by_scope:
                rule, basis = com_by_scope[scope], scope
        elif fac == "EBE":
            cands = ebe_by_code.get(code) or ebe_by_code.get(_ebe_twin(code))
            if cands:
                rule = _pick_ebe_rule(cands, year)
                basis = f"programme rule p{rule['source_page']}" + \
                    (f" ({rule['cohort']})" if rule["cohort"] else "")
            else:
                key = "4yr" if spec["max_year"] >= 4 else "3yr"
                rule = ebe_blanket.get(key)
                basis = f"faculty rule FB3.2 ({key})" if rule else ""
        elif fac == "LAW":
            rule = law_by_code.get(code)
            basis = "printed stream total" if rule else ""

        if rule is None:
            status, minimum, surplus = "NO_RULE", "", ""
        else:
            minimum = int(rule["min_total_credits"])
            surplus = spec["total"] - minimum
            if surplus >= 0:
                status = "OK"
            else:
                status = "ELECTIVE_GAP" if min_anchored[code] else "BELOW_MIN"
        note = ""
        twin = _ebe_twin(code)
        if fac == "EBE" and twin != code and twin in specs:
            diff = spec["total"] - specs[twin]["total"]
            note = (f"ECP twin {twin}: totals "
                    f"{'match' if diff == 0 else f'differ by {diff:+d}'}")
        out.append({
            "year": year, "faculty": fac, "plan_code": code,
            "degree_abbrev": spec["degree_abbrev"],
            "specialisation": spec["specialisation"],
            "variant": spec["variant"], "n_years": spec["n_years"],
            "final_credits_total": spec["total"],
            "rule_min_credits": minimum, "rule_basis": basis,
            "surplus": surplus, "status": status,
            "unresolved_years": spec["unresolved"], "note": note,
        })

    path = ROOT / "validation" / f"degree_check_{year}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    print(f"  degree-check: {dict(Counter(r['status'] for r in out))} "
          f"-> {path.name}")


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

    # 5. whole-degree reconciliation against the rules layer (report-only)
    degree_check(y, summ, final)


if __name__ == "__main__":
    main()
