"""Status derivation shared by validation and the final-clean layer.

Single source of truth for what counts as a credit/fee discrepancy: both
validation/validate.py (reporting) and build_final_dataset.py (resolution)
import these, so the two layers can never disagree about a row's status.
"""

FEE_TOLERANCE_PCT = 5.0


def credit_status(s: dict) -> str:
    """Status for an ideal_student_summary row.

    OK               computed credits equal the stated total (or exceed a
                     stated minimum)
    MISMATCH         both sides known, they disagree
    UNRESOLVED_SLOTS an elective slot's credits could not be resolved
    NO_STATED_TOTAL  the handbook prints no total for this table
    """
    if s["credits_stated"] == "":
        return "NO_STATED_TOTAL"
    if s["credits_unresolved_slots"] != "0":
        return "UNRESOLVED_SLOTS"
    delta = int(s["credit_delta"])
    is_min = s["stated_is_minimum"] == "True"
    if delta == 0 or (is_min and delta > 0):
        return "OK"
    return "MISMATCH"


def fee_status(s: dict) -> str | None:
    """Status for an ideal_student_summary row's published-fee comparison.

    None when no published fee was matched (nothing to compare against).
    """
    if not s["fee_published_zar"]:
        return None
    if s["fee_delta_pct"] == "":
        return "NO_COMPUTED_FEE"
    return "OK" if abs(float(s["fee_delta_pct"])) <= FEE_TOLERANCE_PCT else "MISMATCH"
