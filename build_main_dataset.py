"""Assemble the main dataset — the single source of truth.

Joins the extracted tables (specialisations, curriculum, curriculum_totals,
courses, course_fees) into:

- data/processed/main_dataset.csv
    one row per specialisation x study_year x course-slot, carrying degree,
    credit, course and fee information, an `ideal_student` boolean marking the
    rows a deterministic "ideal student" takes, and provenance columns.

- data/processed/ideal_student_summary.csv
    one row per specialisation x study_year: computed ideal credits and cost
    vs the handbook's stated credit total and the fees book's published fee.

Ideal-student rules (see docs/commerce-review-and-proposal.md section 3):
  core rows            -> taken
  option rows          -> taken if choice_member <= choice_pick_n
  elective slots       -> taken (the slot itself represents the choice);
                          missing credits inferred from the stated year total;
                          fee estimated as the median fee of same-level courses
                          in the departments this specialisation draws on
  alternative rows     -> not taken
  secondary tables     -> table_index > 1 is kept but never ideal (flagged)

Run AFTER the extractors, from the repo root:
    python build_main_dataset.py --year 2025
"""
import argparse
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path

from common.csv_io import write_year_rows

ROOT = Path(__file__).resolve().parent
PROC = ROOT / "data" / "processed"


def read(name):
    with open(PROC / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --- published-fee label matching -------------------------------------------

SPEC_ALIASES = {
    # fees-book label form -> handbook specialisation form (normalised)
    "analytics": "statistics and data sciences",
    "finance non ca option": "finance investment and banking",
    "finance with accounting ca option": "finance with accounting",
    "chartered accounting": "financial accounting chartered accountant",
    "financial chartered accounting": "financial accounting chartered accountant",
    "financial accounting general accounting": "financial accounting general accounting",
    "philosophy politics economics": "philosophy politics and economics ppe",
    "philosophy politics and economics": "philosophy politics and economics ppe",
    "financial accounting chartered accounting": "financial accounting chartered accountant",
    # The AD BBusSc "Finance" label corresponds to Finance, Investment and
    # Banking (the CA option is published separately as "Finance with
    # Accounting").
    "finance": "finance investment and banking",
}


def norm_spec(text: str) -> str:
    t = text.lower().replace("&", "and")
    t = re.sub(r"\bstream\b|\bprogramme\b", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return SPEC_ALIASES.get(t, t)


def parse_fee_label(label: str):
    """Commerce labels -> (degree_abbrev, is_academic_development, spec) or None."""
    l = label.strip()
    if re.search(r"Honours|Master|Doctor|PhD|Postgraduate", l, re.I):
        return None  # postgraduate blocks are out of scope for UG spec-years
    deg = None
    if re.search(r"\bBBusSc\b|Bachelor of Business Science", l):
        deg = "BBusSc"
    elif re.search(r"\bBCom\b|Bachelor of Commerce", l):
        deg = "BCom"
    elif re.search(r"Advanced Diploma", l):
        deg = "AdvDip"
    if not deg:
        return None
    is_ad = bool(re.search(r"Academic Development", l))
    m = re.search(r"(?:specialising in|in the field of|Diploma in)\s+(.*)$", l, re.I)
    spec = m.group(1) if m else l.split("|")[-1]
    return deg, is_ad, norm_spec(spec)


EBE_SPEC_ALIASES = {
    "chemical": "chemical engineering", "civil": "civil engineering",
    "electrical": "electrical engineering",
    "electrical and computer": "electrical and computer engineering",
    "mechanical": "mechanical engineering",
    "mechanical and mechatronic": "mechanical and mechatronic engineering",
}


def parse_fee_label_ebe(label: str):
    """EBE labels -> (degree_abbrev, normalised spec) or None.

    Published forms: "BSc Eng (Chemical)", "BSc in Construction Studies",
    "Bachelor of Architectural Studies", "courses BSc (Geomatics)" (margin
    noise). ECP variants are not published separately — duration matching in
    match_published_fees assigns the block to the right variant.
    """
    l = label.strip()
    if re.search(r"Hons|Honours|Master|Doctor|PhD|Postgraduate|Diploma", l, re.I):
        return None
    m = re.search(r"BSc\.?\s*Eng\.?\s*\(([^)]+)\)", l, re.I)
    if m:
        spec = norm_spec(m.group(1))
        spec = EBE_SPEC_ALIASES.get(spec, spec)
        if not spec.endswith("engineering") and "mechatronics" not in spec:
            spec = EBE_SPEC_ALIASES.get(spec, spec)
        return "BSc(Eng)", spec
    if re.search(r"Bachelor of Architectural Studies|\bBAS\b", l, re.I):
        return "BAS", ""
    if re.search(r"BSc.*Construction Studies", l, re.I):
        return "BSc(ConStud)", ""
    if re.search(r"BSc.*Property Studies", l, re.I):
        return "BSc(PropStud)", ""
    if re.search(r"BSc\s*\(?\s*Geomatics", l, re.I):
        return "BSc(Geomatics)", "*"   # matches every Geomatics stream
    return None


def match_published_fees(prog_fees, specialisations, duration_by_plan):
    """Map fees-book programme labels to plan codes.

    Academic Development fees are published once per specialisation. The
    published block's year-count identifies which AD variant it prices: a
    5-year block is the extended BBusSc, a 4-year block the 4-year variant,
    etc. If both AD variants share the block's duration the fee is applied to
    both ('ad_shared'); otherwise only to the duration-matching variant
    ('ad_duration').
    """
    by_key = defaultdict(list)
    for s in specialisations:
        key = (s["degree_abbrev"], s["variant"] != "regular",
               norm_spec(s["specialisation"]))
        by_key[key].append(s["plan_code"])

    # Group the published rows into blocks per (section, label). LAW publishes
    # single year-less amounts, kept under study_year "".
    blocks = defaultdict(dict)  # (section, label) -> {study_year: fee}
    for r in prog_fees:
        section = ("Commerce" if r["faculty_section"] == "Commerce"
                   else "EBE" if r["faculty_section"].startswith("Engineering")
                   else "LAW" if r["faculty_section"].startswith("Law")
                   else "FHS" if r["faculty_section"].startswith("Health")
                   else "SCI" if r["faculty_section"].startswith("Science")
                   else "HUM" if r["faculty_section"].startswith("Humanities")
                   else None)
        if section is None:
            continue
        if not r["study_year"] and section != "LAW":
            continue
        blocks[(section, r["programme_label"])][r["study_year"]] = int(r["fee_zar"])

    fee_map = {}   # (plan_code, study_year) -> (fee, label, method)
    unmatched = []
    for (section, label), years in blocks.items():
        if section == "Commerce":
            parsed = parse_fee_label(label)
            plans = by_key.get(parsed) if parsed else None
            if not plans:
                unmatched.append(label)
                continue
            deg, is_ad, spec = parsed
            if is_ad and len(plans) > 1:
                matching = [p for p in plans
                            if duration_by_plan.get(p) == len(years)]
                if len(matching) == 1:
                    plans, method = matching, "ad_duration"
                else:
                    method = "ad_shared"
            else:
                method = "label_match"
        elif section == "FHS":
            # Five UG degrees publish clean per-year blocks; everything else
            # in the Health Sciences pages is postgraduate noise.
            if re.search(r"PG Dip|Master|MPhil|MMed|PhD|Dissertation|Honours"
                         r"|Postgrad|\bMD\b|Diploma", label, re.I):
                unmatched.append(label)
                continue
            fhs_map = [(r"MBChB", "MBChB"), (r"Audiology", "BSc(Audiology)"),
                       (r"Speech", "BSc(SLP)"),
                       (r"Occupational Therapy", "BSc(OT)"),
                       (r"Physiotherapy", "BSc(Physio)")]
            abbrev = next((a for pat, a in fhs_map if re.search(pat, label, re.I)),
                          None)
            if not abbrev:
                unmatched.append(label)
                continue
            plans = [p for (a, _ad, _s), ps in by_key.items() if a == abbrev
                     for p in ps]
            if not plans:
                unmatched.append(label)
                continue
            if len(plans) > 1:
                matching = [p for p in plans
                            if duration_by_plan.get(p) == len(years)]
                if matching:
                    plans, method = matching, "duration"
                else:
                    method = "shared"
            else:
                method = "label_match"
        elif section == "LAW":
            # "Undergraduate LLB ... R 76 810" / "Graduate LLB ... R 76 240":
            # one flat annual fee per stream, applied to every study year.
            low = label.lower()
            if "undergraduate llb" in low:
                plans = [p for (a, _ad, s), ps in by_key.items()
                         if a == "LLB" and "undergraduate" in s for p in ps]
            elif "graduate llb" in low:
                plans = [p for (a, _ad, s), ps in by_key.items()
                         if a == "LLB" and s.startswith("graduate") for p in ps]
            else:
                unmatched.append(label)
                continue
            if not plans:
                unmatched.append(label)
                continue
            fee = next(iter(years.values()))
            for p in plans:
                for sy in range(1, (duration_by_plan.get(p) or 1) + 1):
                    fee_map[(p, str(sy))] = (fee, label, "flat_annual")
            continue
        elif section in ("SCI", "HUM"):
            # One published block per degree covers every major: "Bachelor
            # of Science" prices all SCI majors, "Bachelor of Arts and
            # Bachelor of Social Science" all HUM majors (the handbooks'
            # majors serve both degrees). Specialised Humanities programmes
            # (Fine Art, BMus, BSW, PPE, Film & Media) publish their own
            # blocks but have no major rows to price — they surface in the
            # unmatched report by design.
            low = label.lower().strip()
            if section == "SCI" and low == "bachelor of science":
                abbrev = "BSc"
            elif section == "HUM" and \
                    "bachelor of arts and bachelor of social science" in low:
                abbrev = "BA/BSocSc"
            else:
                unmatched.append(label)
                continue
            plans = [p for (a, _ad, _s), ps in by_key.items() if a == abbrev
                     for p in ps]
            if not plans:
                unmatched.append(label)
                continue
            method = "degree_flat"
        else:  # Engineering & the Built Environment
            parsed = parse_fee_label_ebe(label)
            if not parsed:
                unmatched.append(label)
                continue
            deg, spec = parsed
            if spec == "*":  # every stream of the degree (Geomatics)
                plans = [p for (a, _ad, _s), ps in by_key.items() if a == deg
                         for p in ps]
            else:
                plans = (by_key.get((deg, False, spec), [])
                         + by_key.get((deg, True, spec), []))
            if not plans:
                unmatched.append(label)
                continue
            if len(plans) > 1:
                matching = [p for p in plans
                            if duration_by_plan.get(p) == len(years)]
                if matching:
                    plans, method = matching, "duration"
                else:
                    method = "shared"
            else:
                method = "label_match"
        for p in plans:
            for sy, fee in years.items():
                fee_map[(p, sy)] = (fee, label, method)
    return fee_map, unmatched


# --- fee resolution ---------------------------------------------------------

def build_fee_index(course_fees):
    return {r["course_code"]: int(r["fee_zar"]) for r in course_fees}


def resolve_fee(code, fee_idx):
    """-> (fee, source) trying the printed code then suffix variants."""
    if code in fee_idx:
        return fee_idx[code], "exact"
    m = re.match(r"^([A-Z]{3}\d{4})([A-Z]?)$", code)
    if m:
        for suffix in "FSWHZ":
            variant = m.group(1) + suffix
            if variant != code and variant in fee_idx:
                return fee_idx[variant], f"variant:{variant}"
    return "", "none"


def median_level_fee(level, prefixes, fee_idx):
    """Median fee of courses at NQF-ish level `level` in the given departments
    (level digit approximated by the course-code year digit)."""
    digit = str(min(int(level) - 4, 4)) if level else ""
    pool = [f for c, f in fee_idx.items()
            if (not prefixes or c[:3] in prefixes) and (not digit or c[3] == digit)]
    return round(statistics.median(pool)) if pool else ""


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()
    y = str(args.year)

    specs = [r for r in read("specialisations.csv") if r["year"] == y]
    cur = [r for r in read("curriculum.csv") if r["year"] == y]
    totals = [r for r in read("curriculum_totals.csv") if r["year"] == y]
    catalogue = {r["course_code"]: r for r in read("courses.csv") if r["year"] == y}
    course_fees = [r for r in read("course_fees.csv") if r["year"] == y]
    prog_fees = [r for r in read("programme_fees_published.csv") if r["year"] == y]

    spec_by_code = {s["plan_code"]: s for s in specs}
    fee_idx = build_fee_index(course_fees)
    duration_by_plan = defaultdict(int)
    for r in cur:
        if r["study_year"]:  # FHS rows without a resolvable year stay blank
            duration_by_plan[r["plan_code"]] = max(
                duration_by_plan[r["plan_code"]], int(r["study_year"]))
    fee_map, unmatched_labels = match_published_fees(prog_fees, specs, duration_by_plan)
    stated = {(t["plan_code"], t["study_year"], t["table_index"]):
              (int(t["stated_total_credits"]), t["is_minimum"] == "True") for t in totals}

    # Department prefixes each specialisation draws on (for elective estimates).
    prefixes_by_plan = defaultdict(set)
    for r in cur:
        if r["course_code"]:
            prefixes_by_plan[r["plan_code"]].add(r["course_code"][:3])

    # --- pass 1: ideal flag + fee per row --------------------------------
    main_rows = []
    for r in cur:
        s = spec_by_code[r["plan_code"]]
        flags = []
        ideal = True
        if r["table_index"] != "1":
            ideal = False
            flags.append("secondary_table")
        if r["requirement"] == "alternative":
            ideal = False
        elif r["requirement"] == "option":
            if int(r["choice_member"]) > int(r["choice_pick_n"]):
                ideal = False

        fee, fee_source = "", "none"
        if r["course_code"]:
            fee, fee_source = resolve_fee(r["course_code"], fee_idx)
            if fee == "":
                flags.append("fee_missing")
        # (elective-slot fees are estimated after credit inference, pass 3)

        cat = catalogue.get(r["course_code"])
        if cat and r["nqf_credits"] and cat["nqf_credits"] != r["nqf_credits"]:
            flags.append(f"catalogue_credits={cat['nqf_credits']}")

        main_rows.append({
            "year": r["year"], "faculty": r["faculty"],
            "plan_code": r["plan_code"], "programme_code": s["programme_code"],
            "dept_code": s["dept_code"], "degree_abbrev": s["degree_abbrev"],
            "degree_name": s["degree_name"], "specialisation": s["specialisation"],
            "variant": s["variant"],
            "study_year": r["study_year"], "table_index": r["table_index"],
            "seq": r["seq"], "course_code": r["course_code"],
            "course_code_raw": r["course_code_raw"], "course_title": r["course_title"],
            "nqf_credits": r["nqf_credits"], "nqf_level": r["nqf_level"],
            "requirement": r["requirement"], "choice_group": r["choice_group"],
            "choice_member": r["choice_member"], "choice_pick_n": r["choice_pick_n"],
            "choice_note": r["choice_note"], "is_minimum": r["is_minimum"],
            "ideal_student": ideal, "credits_inferred": False,
            "fee_zar": fee, "fee_source": fee_source,
            "in_catalogue": bool(cat), "source_page": r["source_page"],
        })

    # --- pass 2: infer missing elective credits from stated totals -------
    by_table = defaultdict(list)
    for r in main_rows:
        by_table[(r["plan_code"], r["study_year"], r["table_index"])].append(r)
    for key, rows in by_table.items():
        blanks = [r for r in rows if r["ideal_student"] and r["nqf_credits"] == ""]
        if len(blanks) != 1 or key not in stated:
            continue
        st, _ = stated[key]
        known = sum(int(r["nqf_credits"]) for r in rows
                    if r["ideal_student"] and r["nqf_credits"] != "")
        if st - known > 0:
            blanks[0]["nqf_credits"] = st - known
            blanks[0]["credits_inferred"] = True

    # --- pass 3: estimate elective-slot fees, scaled by slot credits -----
    # A slot's cost = median per-course fee among same-level courses in the
    # departments this specialisation draws on, scaled by slot_credits/18
    # (18 = the modal course size at UCT).
    for r in main_rows:
        if r["requirement"] == "elective" and r["course_code"] == "" and r["fee_zar"] == "":
            base = median_level_fee(r["nqf_level"], prefixes_by_plan[r["plan_code"]], fee_idx)
            if base != "" and r["nqf_credits"] != "":
                r["fee_zar"] = round(base * int(r["nqf_credits"]) / 18)
                r["fee_source"] = "estimated_median"

    # --- summary per specialisation-year ---------------------------------
    summary = []
    for key in sorted(by_table, key=lambda k: (k[0], k[1], k[2])):
        plan, sy, ti = key
        if ti != "1":
            continue
        rows = by_table[key]
        s = spec_by_code[plan]
        ideal_rows = [r for r in rows if r["ideal_student"]]
        credits = sum(int(r["nqf_credits"]) for r in ideal_rows if r["nqf_credits"] != "")
        unknown_credits = sum(1 for r in ideal_rows if r["nqf_credits"] == "")
        fee_exact = sum(int(r["fee_zar"]) for r in ideal_rows
                        if r["fee_zar"] != "" and r["fee_source"] != "estimated_median")
        fee_est = sum(int(r["fee_zar"]) for r in ideal_rows
                      if r["fee_zar"] != "" and r["fee_source"] == "estimated_median")
        missing_fees = sum(1 for r in ideal_rows if r["fee_zar"] == "")
        st, is_min = stated.get(key, ("", False))
        credit_delta = credits - st if st != "" else ""
        pub = fee_map.get((plan, sy))
        fee_total = fee_exact + fee_est
        summary.append({
            "year": y, "faculty": s["faculty"], "plan_code": plan,
            "degree_abbrev": s["degree_abbrev"], "specialisation": s["specialisation"],
            "variant": s["variant"], "study_year": sy,
            "credits_ideal": credits, "credits_unresolved_slots": unknown_credits,
            "credits_stated": st, "stated_is_minimum": is_min,
            "credit_delta": credit_delta,
            "fee_ideal_zar": fee_total, "fee_estimated_component_zar": fee_est,
            "fee_slots_missing": missing_fees,
            "fee_published_zar": pub[0] if pub else "",
            "fee_published_label": pub[1] if pub else "",
            "fee_match_method": pub[2] if pub else "unmatched",
            "fee_delta_pct": (round(100 * (fee_total - pub[0]) / pub[0], 1)
                              if pub and fee_total else ""),
        })

    write_year_rows(PROC / "main_dataset.csv", main_rows, y)
    write_year_rows(PROC / "ideal_student_summary.csv", summary, y)

    n_ideal = sum(1 for r in main_rows if r["ideal_student"])
    print(f"main_dataset: {len(main_rows)} rows ({n_ideal} ideal-student rows)")
    print(f"ideal_student_summary: {len(summary)} specialisation-years")
    matched = sum(1 for s in summary if s['fee_published_zar'] != "")
    print(f"published-fee coverage: {matched}/{len(summary)} spec-years; "
          f"{len(unmatched_labels)} Commerce labels unmatched")


if __name__ == "__main__":
    main()
