"""Final-clean dataset builder — step 5 of the pipeline.

Resolves the discrepancies preserved in the as-printed layer into a
justified, internally consistent final dataset. The as-printed tables are
never modified; every resolution is recorded with its rule, evidence and
confidence. Methodology: docs/FINAL-DATASET-METHOD.md.

Inputs : data/processed/main_dataset.csv, ideal_student_summary.csv
         (all years — cross-edition rules read sibling editions),
         resolutions/<faculty>.csv (curated adjudications).
Outputs: data/processed/main_dataset_final.csv
         data/processed/ideal_student_summary_final.csv
         validation/resolution_log_{year}.csv
         validation/pending_adjudication_{year}.csv

Rule taxonomy (application order R0 -> R3 -> R1 -> R2 -> R4; human
adjudication pre-empts auto-rules):

  R0  pass-through      credit status OK -> consistent (high confidence)
  R3  adjudication      register row for (year, plan, study_year) (high)
  R1a OR-double-count   stated total exceeds the ideal sum by exactly the
                        credits of the non-taken choice rows (all groups, or
                        exactly one group) -> trust computed (high)
  R1b misprint detector |delta| >= 84 and stated is a single digit-edit of
                        the row sum -> pending report suggestion only
  R2a cross-edition     identical ideal row-set in >= 2 other editions whose
                        status is OK, divergent stated total here -> trust
                        computed (medium)
  R2b row-set detector  stated stable across editions but row-set unique
                        here -> pending report suggestion only
  R4  residual          default-trust policy (computed), low confidence,
                        listed in pending_adjudication; never blocks unless
                        --strict

Run from the repo root:
    python build_final_dataset.py --year 2025
        [--default-trust computed|stated|none] [--strict]
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.checks import FEE_TOLERANCE_PCT, credit_status  # noqa: E402
from common.csv_io import write_year_rows  # noqa: E402

PROC = ROOT / "data" / "processed"

RESOLUTION_COLS = ["res_id", "year", "faculty", "plan_code", "study_year",
                   "scope", "row_selector", "issue", "action", "value",
                   "rationale", "evidence", "decided_by", "decided_date"]


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_register():
    """All per-faculty registers (resolutions/*.csv) combined."""
    rows = []
    for path in sorted((ROOT / "resolutions").glob("*.csv")):
        rows += read(path)
    ids = [r["res_id"] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate res_id in register: {sorted(dupes)}")
    return rows


def edit_distance_le1(a: str, b: str) -> bool:
    """True if strings are within one substitution/insertion/deletion."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):  # delete one char of the longer string
        if b[:i] + b[i + 1:] == a:
            return True
    return False


def int_or_zero(v):
    return int(v) if v not in ("", None) else 0


class SpecYear:
    """Working state for one specialisation-year of the target edition."""

    def __init__(self, summary_row, rows):
        self.s = summary_row
        self.rows = rows                       # main_dataset rows, this spec-year
        self.t1 = [r for r in rows if r["table_index"] == "1"]
        self.final_included = {id(r): r["ideal_student"] == "True" for r in rows}
        self.resolution_class = "none"
        self.resolution_ref = ""
        self.confidence = ""
        self.rationale = ""
        self.final_note = ""
        self.status = ""                       # final_credit_status
        self.final_credits = None
        self.stated_corrected = ""
        self.published_ref = None              # possibly corrected by R3

    def included_rows(self):
        return [r for r in self.t1 if self.final_included[id(r)]]

    def computed_credits(self):
        return sum(int_or_zero(r["nqf_credits"]) for r in self.included_rows())

    def computed_fee(self):
        return sum(int_or_zero(r["fee_zar"]) for r in self.included_rows())

    def unpicked(self):
        """Non-taken choice rows of table 1 (option members beyond pick_n and
        alternatives) — the candidates a stated total may double-count."""
        out = []
        for r in self.t1:
            if r["requirement"] == "alternative" and r["nqf_credits"] != "":
                out.append(r)
            elif (r["requirement"] == "option" and r["choice_member"] != ""
                  and r["choice_pick_n"] != ""
                  and int(r["choice_member"]) > int(r["choice_pick_n"])
                  and r["nqf_credits"] != ""):
                out.append(r)
        return out

    def rowset(self):
        """Comparable identity of the ideal selection (for cross-edition
        comparison): sorted (code-or-title, credits) of included table-1 rows."""
        return tuple(sorted((r["course_code"] or r["course_title"].lower(),
                             r["nqf_credits"]) for r in self.included_rows()))


def apply_r3(sy: SpecYear, entries, log):
    """Apply this spec-year's register entries. Returns True if the credit
    question was settled (an anchor-only correction leaves it open)."""
    settled = False
    for e in entries:
        act, val = e["action"], e["value"]
        sy.resolution_class = "R3"
        sy.resolution_ref = e["res_id"]
        sy.confidence = "high"
        sy.rationale = e["rationale"]
        if act == "accept_computed":
            sy.final_credits = sy.computed_credits()
            sy.status = "resolved_manual"
            settled = True
        elif act == "accept_stated":
            sy.final_credits = int(sy.s["credits_stated"])
            sy.status = "resolved_manual"
            settled = True
        elif act == "set_stated_corrected":
            sy.stated_corrected = int(val)   # anchor corrected; not settled
        elif act == "set_final_credits":
            sy.final_credits = int(val)
            sy.status = "resolved_manual"
            settled = True
        elif act == "pin_choice":
            pinned = set(v.strip() for v in val.split(";") if v.strip())
            groups = {r["choice_group"] for r in sy.t1
                      if r["course_code"] in pinned and r["choice_group"]}
            for r in sy.t1:
                if r["choice_group"] in groups:
                    sy.final_included[id(r)] = r["course_code"] in pinned
            sy.final_credits = sy.computed_credits()
            sy.status = "resolved_manual"
            settled = True
        elif act in ("include_row", "exclude_row"):
            for r in sy.t1:
                if r["course_code"] == e["row_selector"] or r["seq"] == e["row_selector"]:
                    sy.final_included[id(r)] = act == "include_row"
            sy.final_credits = sy.computed_credits()
            sy.status = "resolved_manual"
            settled = True
        elif act == "set_final_fee":
            sy.final_fee_override = int(val)
        elif act == "set_published_ref":
            sy.published_ref = int(val)
        else:
            raise SystemExit(f"unknown register action {act!r} in {e['res_id']}")
        log.append({
            "year": e["year"], "plan_code": e["plan_code"],
            "study_year": e["study_year"], "rule": "R3", "action": act,
            "res_id": e["res_id"], "credits_ideal": sy.s["credits_ideal"],
            "credits_stated": sy.s["credits_stated"],
            "final_credits": sy.final_credits if sy.final_credits is not None else "",
            "evidence": e["evidence"], "confidence": "high",
        })
    return settled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--default-trust", choices=["computed", "stated", "none"],
                    default="computed")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if pending adjudications remain")
    args = ap.parse_args()
    y = str(args.year)

    all_main = read(PROC / "main_dataset.csv")
    all_summary = read(PROC / "ideal_student_summary.csv")
    register = load_register()

    # Index main rows by (year, plan, study_year); summaries by year.
    rows_by_key = defaultdict(list)
    for r in all_main:
        rows_by_key[(r["year"], r["plan_code"], r["study_year"])].append(r)
    summaries = {yr: [] for yr in {s["year"] for s in all_summary}}
    for s in all_summary:
        summaries[s["year"]].append(s)

    # Cross-edition evidence: rowset + status per (year, plan, study_year).
    evidence = {}
    for yr, ss in summaries.items():
        for s in ss:
            key = (yr, s["plan_code"], s["study_year"])
            spec = SpecYear(s, rows_by_key[key])
            evidence[key] = (spec.rowset(), credit_status(s), s["credits_stated"])

    reg_by_key = defaultdict(list)
    for e in register:
        if e["year"] == y:
            reg_by_key[(e["plan_code"], e["study_year"])].append(e)

    log, pending = [], []
    final_summaries = []
    consumed = set()
    spec_states = {}

    for s in summaries.get(y, []):
        key = (y, s["plan_code"], s["study_year"])
        sy = SpecYear(s, rows_by_key[key])
        spec_states[(s["plan_code"], s["study_year"])] = sy
        status0 = credit_status(s)
        stated = int(s["credits_stated"]) if s["credits_stated"] != "" else None

        # ---- R3 first: adjudications pre-empt everything ------------------
        entries = reg_by_key.get((s["plan_code"], s["study_year"]), [])
        settled = apply_r3(sy, entries, log) if entries else False
        for e in entries:
            consumed.add(e["res_id"])
        anchor = sy.stated_corrected if sy.stated_corrected != "" else stated

        if not settled:
            computed = sy.computed_credits()
            unresolved_slots = s["credits_unresolved_slots"] != "0"
            delta = computed - anchor if anchor is not None else None

            if status0 == "OK" and sy.stated_corrected == "":
                # ---- R0 ----
                sy.status = "consistent"
                sy.final_credits = computed
                sy.confidence = "high"
                sy.rationale = "computed credits equal the stated total"
            elif (anchor is not None and not unresolved_slots and delta is not None
                  and delta == 0):
                # corrected anchor now agrees
                sy.status = "resolved_manual" if sy.resolution_class == "R3" else "consistent"
                sy.final_credits = computed
                sy.confidence = sy.confidence or "high"
            elif anchor is not None and not unresolved_slots and delta < 0:
                # ---- R1a: stated counts non-taken choice rows -------------
                unpicked = sy.unpicked()
                total_unpicked = sum(int(r["nqf_credits"]) for r in unpicked)
                group_sums = defaultdict(int)
                for r in unpicked:
                    group_sums[r["choice_group"] or "ALT"] += int(r["nqf_credits"])
                if -delta == total_unpicked or -delta in group_sums.values():
                    ref = "R1a" if sy.resolution_class == "none" else f"{sy.resolution_ref}+R1a"
                    which = ("all choice groups" if -delta == total_unpicked
                             else "one choice group")
                    sy.resolution_class = "R3" if sy.resolution_class == "R3" else "R1a"
                    sy.resolution_ref = ref if sy.resolution_class == "R1a" else sy.resolution_ref
                    sy.status = "resolved_computed"
                    sy.final_credits = computed
                    sy.confidence = sy.confidence or "high"
                    sy.rationale = (sy.rationale + " | " if sy.rationale else "") + (
                        f"stated total exceeds the taken-course sum by exactly the "
                        f"credits of the non-taken alternatives ({which}, "
                        f"{-delta} cr) — the printed total double-counts choices")
                    log.append({
                        "year": y, "plan_code": s["plan_code"],
                        "study_year": s["study_year"], "rule": "R1a",
                        "action": "accept_computed", "res_id": sy.resolution_ref,
                        "credits_ideal": computed, "credits_stated": anchor,
                        "final_credits": computed,
                        "evidence": f"non-taken choice credits = {-delta} ({which})",
                        "confidence": sy.confidence,
                    })

            if sy.final_credits is None and anchor is not None and not unresolved_slots:
                # ---- R1b misprint detector (suggestion only) --------------
                # Compare the stated total against both the ideal sum and the
                # both-branches sum (ideal + non-taken choices): a misprinted
                # total may have been printed for either arithmetic.
                both_branches = computed + sum(
                    int(r["nqf_credits"]) for r in sy.unpicked())
                candidates = {computed, both_branches}
                hit = next((c for c in candidates if abs(delta) >= 84
                            and edit_distance_le1(str(anchor), str(c))), None)
                if hit is not None:
                    pending.append({
                        "year": y, "plan_code": s["plan_code"],
                        "study_year": s["study_year"], "status": status0,
                        "credits_ideal": computed, "credits_stated": anchor,
                        "detector": "R1b",
                        "suggested_action": "set_stated_corrected",
                        "detail": (f"stated {anchor} is a single digit-edit of "
                                   f"{hit} ({'row sum' if hit == computed else 'both-branches sum'})"
                                   f" — likely misprint"),
                    })

                # ---- R2a cross-edition stated drift -----------------------
                my_rowset = sy.rowset()
                corroborating = [
                    yr for (yr, plan, sy_), (rs, st, _) in evidence.items()
                    if plan == s["plan_code"] and sy_ == s["study_year"]
                    and yr != y and rs == my_rowset and st == "OK"
                ]
                if len(corroborating) >= 2:
                    sy.resolution_class = "R2a"
                    sy.resolution_ref = "R2a"
                    sy.status = "resolved_computed"
                    sy.final_credits = computed
                    sy.confidence = "medium"
                    sy.rationale = (
                        f"identical taken-course set reconciles exactly in editions "
                        f"{', '.join(sorted(corroborating))}; the divergent stated "
                        f"total here is edition-local drift")
                    log.append({
                        "year": y, "plan_code": s["plan_code"],
                        "study_year": s["study_year"], "rule": "R2a",
                        "action": "accept_computed", "res_id": "R2a",
                        "credits_ideal": computed, "credits_stated": anchor,
                        "final_credits": computed,
                        "evidence": "corroborated by " + ", ".join(sorted(corroborating)),
                        "confidence": "medium",
                    })
                else:
                    # ---- R2b row-set drift detector (suggestion only) -----
                    stated_matches = [
                        yr for (yr, plan, sy_), (rs, st, stt) in evidence.items()
                        if plan == s["plan_code"] and sy_ == s["study_year"]
                        and yr != y and st == "OK" and stt == s["credits_stated"]
                    ]
                    other_rowsets = [
                        rs for (yr, plan, sy_), (rs, st, _) in evidence.items()
                        if plan == s["plan_code"] and sy_ == s["study_year"] and yr != y
                    ]
                    if len(stated_matches) >= 2 and other_rowsets and \
                            all(rs != my_rowset for rs in other_rowsets):
                        pending.append({
                            "year": y, "plan_code": s["plan_code"],
                            "study_year": s["study_year"], "status": status0,
                            "credits_ideal": computed, "credits_stated": anchor,
                            "detector": "R2b",
                            "suggested_action": "check_extraction",
                            "detail": (f"stated total matches OK editions "
                                       f"{', '.join(sorted(stated_matches))} but the "
                                       f"extracted course set is unique to this "
                                       f"edition — possible extraction gap"),
                        })

            if sy.final_credits is None:
                # ---- R4 residual ------------------------------------------
                # SCI/HUM curricula are MAJORS: the handbooks print no
                # per-year totals for them by design, so there is nothing to
                # adjudicate — status `no_anchor`, kept out of the pending
                # queue. Degree-level anchors live in degree_rules.csv.
                no_anchor_unit = (status0 == "NO_STATED_TOTAL"
                                  and s["faculty"] in ("SCI", "HUM"))
                sy.status = "no_anchor" if no_anchor_unit else "unresolved"
                sy.confidence = "low"
                if args.default_trust == "computed":
                    sy.final_credits = sy.computed_credits()
                elif args.default_trust == "stated" and anchor is not None:
                    sy.final_credits = anchor
                else:
                    sy.final_credits = ""
                if no_anchor_unit:
                    sy.final_note = ("majors print no per-year totals; "
                                     "degree-level anchors are in degree_rules.csv")
                elif status0 == "NO_STATED_TOTAL":
                    sy.final_note = "no stated total printed — nothing to reconcile against"
                elif status0 == "UNRESOLVED_SLOTS":
                    sy.final_note = "elective slot credits unresolved"
                sy.rationale = sy.rationale or (
                    f"no rule or adjudication applies; default-trust="
                    f"{args.default_trust}")
                if status0 != "OK" and not no_anchor_unit:
                    pending.append({
                        "year": y, "plan_code": s["plan_code"],
                        "study_year": s["study_year"], "status": status0,
                        "credits_ideal": sy.computed_credits(),
                        "credits_stated": anchor if anchor is not None else "",
                        "detector": "R4",
                        "suggested_action": "adjudicate in resolutions/com.csv",
                        "detail": sy.final_note or "credit mismatch unexplained by rules",
                    })

        # ---- fees ---------------------------------------------------------
        fee_final = getattr(sy, "final_fee_override", None)
        if fee_final is None:
            fee_final = sy.computed_fee()
        pub = sy.published_ref if sy.published_ref is not None else \
            (int(s["fee_published_zar"]) if s["fee_published_zar"] else None)
        if pub is None:
            fee_status_final = "no_published"
        elif pub and abs(100 * (fee_final - pub) / pub) <= FEE_TOLERANCE_PCT:
            fee_status_final = "reconciled"
        else:
            fee_status_final = "published_divergent"

        final_summaries.append({
            **s,
            "final_credits": sy.final_credits,
            "credits_stated_corrected": sy.stated_corrected,
            "final_credit_status": sy.status,
            "final_fee_zar": fee_final,
            "final_fee_status": fee_status_final,
            "resolution_class": sy.resolution_class,
            "resolution_ref": sy.resolution_ref,
            "confidence": sy.confidence,
            "resolution_rationale": sy.rationale,
        })

    # Register hygiene: every entry for this year must have been consumed.
    stale = [e["res_id"] for e in register if e["year"] == y
             and e["res_id"] not in consumed]
    if stale:
        raise SystemExit(f"register entries not consumed (typo in plan/year?): {stale}")

    # ---- main_dataset_final ----------------------------------------------
    final_rows = []
    for r in all_main:
        if r["year"] != y:
            continue
        sy = spec_states.get((r["plan_code"], r["study_year"]))
        included = sy.final_included.get(id(r), r["ideal_student"] == "True") if sy else False
        note = ""
        if sy and included != (r["ideal_student"] == "True"):
            note = "inclusion changed by " + (sy.resolution_ref or sy.resolution_class)
        final_rows.append({
            **r,
            "final_included": included,
            "resolution_class": sy.resolution_class if sy else "none",
            "resolution_ref": sy.resolution_ref if sy else "",
            "final_note": note,
        })

    write_year_rows(PROC / "main_dataset_final.csv", final_rows, y)
    write_year_rows(PROC / "ideal_student_summary_final.csv", final_summaries, y)

    def write_report(path, rows, fields):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    write_report(ROOT / "validation" / f"resolution_log_{args.year}.csv", log,
                 ["year", "plan_code", "study_year", "rule", "action", "res_id",
                  "credits_ideal", "credits_stated", "final_credits",
                  "evidence", "confidence"])
    write_report(ROOT / "validation" / f"pending_adjudication_{args.year}.csv", pending,
                 ["year", "plan_code", "study_year", "status", "credits_ideal",
                  "credits_stated", "detector", "suggested_action", "detail"])

    from collections import Counter
    statuses = Counter(r["final_credit_status"] for r in final_summaries)
    classes = Counter(r["resolution_class"] for r in final_summaries)
    print(f"final summary ({len(final_summaries)} spec-years): {dict(statuses)}")
    print(f"resolution classes: {dict(classes)}")
    print(f"resolution log: {len(log)} entries; pending adjudication: {len(pending)}")
    if args.strict and pending:
        sys.exit(1)


if __name__ == "__main__":
    main()
