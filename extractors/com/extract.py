"""Commerce (COM) undergraduate handbook extractor.

Faculty configuration for the shared engine in common/handbook_parser.py
(which originated here and was promoted once the grammar proved general).
Layout contracts and the hazard catalogue live in docs/REPLICATION.md.

Run from the repo root:
    python -m extractors.com.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.handbook_parser import FacultyConfig, run_extractor, tidy_caps

ROOT = Path(__file__).resolve().parents[2]

# A programme block starts at any non-TOC line ending with a [PLANCODE]
# bracket. Observed forms across editions:
#   "[CB004FTX04]"                 (code alone, 2025/2026)
#   "[CB003BUS01][SAQA ID:4411]"   (trailing bracket, 2021/2022)
#   "Bachelor of ... [CB004FTX05]" (inline, 2024)
#   "Finance [CB025BUS09]"         (wrapped title tail, 2024)
#   "[CB011ECO03#]"                (footnote marker in the bracket, 2022/2023)
#   "[CB0015ECO03]"                (extra-zero misprint, 2024)
PLAN_CODE_ANY = re.compile(
    r"^(?P<pre>.*?)\s*\[(?P<code>C[BU][0-9O]{2,4}[A-Z]{3}\d{2})[#*\s]*\]"
    r"(?:\s*\[[^\]]+\])*\s*$")

# Known programme-code families (documented in CLAUDE.md). Variant fallback
# when neither a page-header hint nor an umbrella line applies.
VARIANT_BY_PROGCODE = {
    "CB001": "regular", "CB003": "regular", "CB004": "regular", "CB019": "regular",
    "CB023": "augmented", "CB024": "augmented", "CB025": "augmented", "CB026": "augmented",
    "CB011": "extended", "CB015": "extended", "CB018": "extended", "CB020": "extended",
}

ADVDIP_LABELS = [
    (re.compile(r"^Prescribed courses\s*$", re.I), ("core", "")),
    (re.compile(r"^And (two|three) of the following elective courses", re.I),
     ("option", "choose {0} of the listed electives")),
    (re.compile(r"^Approved electives at NQF level \d include", re.I),
     ("alternative", "approved elective pool")),
]


def normalise_plan_code(raw: str) -> str:
    """CBO18BUS01 -> CB018BUS01; CB25BUS09 -> CB025BUS09;
    CB0015ECO03 -> CB015ECO03 (extra-zero misprint)."""
    m = re.match(r"^(C[BU])([0-9O]{2,4})([A-Z]{3}\d{2})$", raw)
    head, num, tail = m.groups()
    num = num.replace("O", "0")
    while len(num) > 3 and num.startswith("0"):
        num = num[1:]
    return head + num.zfill(3) + tail


def parse_degree(title: str) -> tuple[str, str, str]:
    """-> (degree_name, degree_abbrev, specialisation)"""
    t = re.sub(r"\s+", " ", title).strip().rstrip("*")
    # Strip variant qualifiers that some headings glue onto the degree name.
    t = re.sub(r"\s+(?:4 Year AD|Augmented|Extended(?: Academic Development)?"
               r"|Academic Development)\b", "", t)
    m = re.match(
        r"^(?P<deg>Bachelor of (?:Business Science|Commerce)|Advanced Diploma|Postgraduate Diploma)"
        r"(?: in (?P<field>[^\[]+?))?(?: specialising in (?P<spec>.+))?$", t, re.I)
    if not m:
        return t, "", ""
    canon = {"bachelor of business science": ("Bachelor of Business Science", "BBusSc"),
             "bachelor of commerce": ("Bachelor of Commerce", "BCom"),
             "advanced diploma": ("Advanced Diploma", "AdvDip"),
             "postgraduate diploma": ("Postgraduate Diploma", "PGDip")}
    deg, abbrev = canon[m.group("deg").lower()]
    field, spec = m.group("field") or "", m.group("spec") or ""
    if deg.startswith("Advanced") or deg.startswith("Postgraduate"):
        spec = field or spec
        field = ""
    parts = [p for p in (field.strip(), spec.strip()) if p]
    return deg, abbrev, ": ".join(tidy_caps(p) for p in parts)


CONFIG = FacultyConfig(
    faculty="COM",
    slug="com",
    plan_code_any=PLAN_CODE_ANY,
    normalise_plan_code=normalise_plan_code,
    parse_degree=parse_degree,
    title_start=re.compile(
        r"^(Bachelor of|Advanced Diploma in|Postgraduate Diploma in)", re.I),
    prog_page=re.compile(
        r"^(?:\d+\s+)?(?:RULES FOR ADVANCED DIPLOMAS|PROGRAMMES OF STUDY"
        r"|BACHELOR OF (?:COMMERCE|BUSINESS SCIENCE)(?: AUGMENTED| EXTENDED)?)"
        r"(?:\s+\d+)?\s*$", re.I),
    cat_page=re.compile(
        r"^(?:\d+\s+)?(?:DEPARTMENTS IN THE FACULTY.*|FACULTIES AND DEPARTMENTS.*"
        r"|DEPARTMENTS OFFERING COURSES.*|COLLEGE OF .+|SCHOOL OF .+|DEPARTMENT OF .+"
        r"|GRADUATE SCHOOL OF BUSINESS|NELSON MANDELA SCHOOL.*|EDUCATION DEVELOPMENT UNIT.*)"
        r"(?:\s+\d+)?\s*$", re.I),
    page_header=re.compile(
        r"^(?:\d+\s+)?(?:PROGRAMMES OF STUDY|RULES FOR ADVANCED DIPLOMAS|GENERAL INFORMATION"
        r"|DEPARTMENTS IN THE FACULTY OF COMMERCE|FACULTIES AND DEPARTMENTS.*|ADDITIONAL INFORMATION)"
        r"(?:\s+\d+)?\s*$"),
    year_heading=re.compile(r"^(First|Second|Third|Fourth|Fifth) Year Core Modules\s*$"),
    dept_by_prefix={
        "ACC": "College of Accounting", "BUS": "School of Management Studies",
        "DOC": "Demography", "ECO": "School of Economics", "FTX": "Finance and Tax",
        "GPP": "Nelson Mandela School of Public Governance",
        "GSB": "Graduate School of Business", "INF": "Information Systems",
        "CML": "Commercial Law", "CSC": "Computer Science",
        "EGS": "Environmental & Geographical Science", "GEO": "Geological Sciences",
        "MAM": "Mathematics and Applied Mathematics", "PHI": "Philosophy",
        "POL": "Political Studies", "PSY": "Psychology", "PVL": "Private Law",
        "PBL": "Public Law", "STA": "Statistical Sciences", "MUZ": "Music",
    },
    umbrella=re.compile(
        r"^Bachelor of (Business Science|Commerce)\b(?!.* specialising)(?!.* in [A-Z]{2})"),
    variant_by_progcode=VARIANT_BY_PROGCODE,
    advdip_prefix="CU",
    advdip_labels=ADVDIP_LABELS,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()
    run_extractor(CONFIG, args, ROOT)


if __name__ == "__main__":
    main()
