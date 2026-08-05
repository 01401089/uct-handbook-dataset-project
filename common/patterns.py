"""Shared grammar for UCT handbook identifiers and money/credit lines.

Faculty-specific layouts belong in extractors/<fac>/ — only patterns that hold
university-wide are allowed here.
"""
import re

# Course code: dept (3 letters) + level digit + 3-digit distinguisher + period
# suffix. F=1st semester, S=2nd, W=whole year, H=year-long half-course,
# Z=non-standard, N/X observed in fees book, P/U/L=summer/winter terms.
COURSE_CODE = re.compile(r"\b([A-Z]{3})(\d)(\d{3})([FSWHZNXPUL])\b")

# Composite offering like STA2020F/S (same course, either semester).
COURSE_CODE_DUAL = re.compile(r"\b[A-Z]{3}\d{4}[FSWHZ]/[FSWHZ]\b")

# Plan / specialisation / major code: programme code (2 letters + 3 digits)
# + department/stream code (2-3 letters + digits), e.g. CB004FTX04, HB001SOC01.
PLAN_CODE = re.compile(r"\b([A-Z]{2}[0-9O]{3})([A-Z]{2,3}\d{1,2})\b")


def normalise_plan_code(raw: str) -> str:
    """Fix the known O-for-0 typo class (e.g. CBO18BUS01 -> CB018BUS01)."""
    head, tail = raw[:5], raw[5:]
    return head[:2] + head[2:].replace("O", "0") + tail


# "Total credits per year .......... +168" (dots, stray +, 'for the year').
TOTAL_CREDITS_LINE = re.compile(
    r"Total credits (?:per|for the) year[\s.]*\+?\s*(\d{1,3})"
)

# Fees book §12 row: CODE  TITLE  10,440
FEE_ROW = re.compile(r"^([A-Z]{3}\d{4}[A-Z])\s+(.+?)\s+([\d,]+)$")

# Published programme fee amount: "R 91 190" / "R91 190" / "R 78 090"
RAND_AMOUNT = re.compile(r"R\s?([\d]{1,3}(?:[\s ]\d{3})*)")


def parse_rand(text: str) -> int | None:
    m = RAND_AMOUNT.search(text)
    if not m:
        return None
    return int(re.sub(r"[\s ]", "", m.group(1)))


def parse_fee(text: str) -> int:
    """Parse a §12 comma-separated fee like '10,440'."""
    return int(text.replace(",", ""))
