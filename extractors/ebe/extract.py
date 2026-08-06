"""Engineering & the Built Environment (EBE) undergraduate handbook extractor.

Faculty configuration for the shared engine in common/handbook_parser.py.
EBE uses the same publisher template as Commerce with these deltas
(stable across 2021-2026 — EBE shows no cross-edition layout drift):

- Year headings say "Core Courses" (not "Core Modules").
- Plan codes are EB###XXX## ; the 800-series (EB8xx) are the 5-year Extended
  Curriculum Programmes (ECP) -> variant "extended".
- Headings glue the degree abbreviation before the bracket
  ("BSc(Engineering)(Chemical Engineering)[EB001CHE01]") under a descriptive
  line ("Bachelor of Science in Engineering in Chemical Engineering 4-year
  curriculum").
- Stated totals are frequently ranges ("Total credits per year ... 108-156")
  because elective loads are ranges ("Approved elective courses ... 0-48");
  the minimum anchors the ideal student, the maximum is retained.
- Each programme is followed by an "ELECTIVE COURSES" pool section listing
  approved elective menus by category -> requirement "alternative".
- A transferee access programme reuses an existing plan code; repeat blocks
  are suppressed with a note (see DEV-TODO).

Run from the repo root:
    python -m extractors.ebe.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.handbook_parser import FacultyConfig, run_extractor, tidy_caps

ROOT = Path(__file__).resolve().parents[2]

PLAN_CODE_ANY = re.compile(
    r"^(?P<pre>.*?)\s*\[(?P<code>E[BM][0-9O]{2,4}[A-Z]{2,3}\d{2})[#*\s]*\]"
    r"(?:\s*\[[^\]]+\])*\s*$")

DEGREE_CANON = [
    (re.compile(r"^Bachelor of Science in Engineering", re.I),
     ("Bachelor of Science in Engineering", "BSc(Eng)")),
    (re.compile(r"^Bachelor of Architectural Studies", re.I),
     ("Bachelor of Architectural Studies", "BAS")),
    (re.compile(r"^Bachelor of Science in Geomatics", re.I),
     ("Bachelor of Science in Geomatics", "BSc(Geomatics)")),
    (re.compile(r"^Bachelor of Science in Construction Studies", re.I),
     ("Bachelor of Science in Construction Studies", "BSc(ConStud)")),
    (re.compile(r"^Bachelor of Science in Property Studies", re.I),
     ("Bachelor of Science in Property Studies", "BSc(PropStud)")),
]


def normalise_plan_code(raw: str) -> str:
    m = re.match(r"^(E[BM])([0-9O]{2,4})([A-Z]{2,3}\d{2})$", raw)
    head, num, tail = m.groups()
    num = num.replace("O", "0")
    while len(num) > 3 and num.startswith("0"):
        num = num[1:]
    return head + num.zfill(3) + tail


def parse_degree(title: str) -> tuple[str, str, str]:
    """-> (degree_name, degree_abbrev, specialisation)

    "Bachelor of Science in Engineering in Chemical Engineering 4-year
    curriculum BSc(Engineering)(Chemical Engineering)" -> BSc(Eng),
    "Chemical Engineering".
    """
    t = re.sub(r"\s+", " ", title).strip()
    # Strip the glued abbreviation tail and the N-year qualifier.
    t = re.sub(r"\s*(?:BAS|BSc\s*\([^)]*\)\s*(?:\([^)]*\))?)\s*$", "", t)
    t = re.sub(r"\s*\d-\s*year curriculum\b", "", t).strip(" .")
    for pat, (deg, abbrev) in DEGREE_CANON:
        m = pat.match(t)
        if not m:
            continue
        rest = t[m.end():].strip(" :")
        rest = re.sub(r"^in\s+", "", rest)
        return deg, abbrev, tidy_caps(rest) if rest else ""
    return t, "", ""


def variant_from_code(code: str) -> str:
    """EB8xx plan codes are the 5-year Extended Curriculum Programmes."""
    return "extended" if code[2] == "8" else "regular"


CONFIG = FacultyConfig(
    faculty="EBE",
    slug="ebe",
    plan_code_any=PLAN_CODE_ANY,
    normalise_plan_code=normalise_plan_code,
    parse_degree=parse_degree,
    title_start=re.compile(r"^(Bachelor of|Programme for University of Technology)", re.I),
    prog_page=re.compile(
        r"^(?:\d+\s+)?PROGRAMMES OF STUDY(?:\s+\d+)?\s*$", re.I),
    cat_page=re.compile(
        r"^(?:\d+\s+)?DEPARTMENTS IN (?:THE FACULTY|OTHER FACULTIES)"
        r"(?: AND COURSES OFFERED)?(?:\s+\d+)?\s*$", re.I),
    page_header=re.compile(
        r"^(?:\d+\s+)?(?:PROGRAMMES OF STUDY|DEPARTMENTS IN (?:THE FACULTY|OTHER FACULTIES).*"
        r"|RULES FOR UNDERGRADUATE DEGREES|GENERAL INFORMATION"
        r"|CENTRES AND OTHER ENTITIES.*|SCHOLARSHIPS, PRIZES.*)"
        r"(?:\s+\d+)?\s*$", re.I),
    # EBE mixes "Core Courses" and "Core Modules" within one edition (2021),
    # suffixes headings with parentheticals ("(from 2020)", "(EE)") and, in
    # 2025/2026, with footnote markers ("First Year Core Courses (EE)*†").
    year_heading=re.compile(
        r"^(First|Second|Third|Fourth|Fifth) Year Core (?:Courses|Modules)"
        r"(?:\s*\([^)]*\))?[\s*†‡]*$"),
    # In-year elective menus: "(Ordinal) Year (Further) Elective Core Courses
    # (EE)". Their rows are candidates for the year's elective slot (or a
    # pick-n choice), NOT additional core load.
    elective_core_heading=re.compile(
        r"^(First|Second|Third|Fourth|Fifth) Year (?:Further )?Elective Core "
        r"(?:Courses|Modules)(?:\s*\([^)]*\))?[\s*†‡]*$"),
    optional_heading=re.compile(r"^Optional Courses\s*$"),
    # "Select courses amounting to at least 48 credits from the following:"
    # -> a minimum elective slot; the menu rows below are alternatives.
    select_min_instruction=re.compile(
        r"^Select courses amounting to at least (?P<credits>\d{1,3}) credits"
        r" from the following:?\s*$", re.I),
    # "Select two out of the following three courses." -> pick-n menu.
    select_pick_instruction=re.compile(
        r"^Select (?P<n>one|two|three|four|\d+) out of the following "
        r"(?:one|two|three|four|five|six|\d+) courses\b", re.I),
    dept_by_prefix={
        "CHE": "Chemical Engineering", "CIV": "Civil Engineering",
        "EEE": "Electrical Engineering", "MEC": "Mechanical Engineering",
        "APG": "Architecture, Planning and Geomatics",
        "CON": "Construction Economics and Management",
        "END": "Engineering Faculty Office", "GEO": "Geological Sciences",
        "MAM": "Mathematics and Applied Mathematics", "PHY": "Physics",
        "CEM": "Chemistry", "STA": "Statistical Sciences", "CSC": "Computer Science",
        "EGS": "Environmental & Geographical Science",
    },
    variant_from_code=variant_from_code,
    pool_marker=re.compile(r"^ELECTIVE COURSES\s*$"),
    # Slot lines, all requiring a dotted leader before the credits so prose
    # never matches: the range form ("Approved elective courses ... 0-48"),
    # bare in-table forms ("Electives ... 18" [2021 Property Studies],
    # "Elective ... 18 5" [Geomatics]), the complementary-studies line with a
    # period-code prefix ("F/S/P/L *Approved Complementary Studies Elective
    # F/S/P/L ... 18 7"), and the Mechanical year-4 slots with level-range
    # tails ("*Approved Complementary Studies (b) elective ... 18 5-8",
    # "**Approved F and S Open electives ...Totalling at least ... 24 5-8").
    extra_elective=re.compile(
        r"^(?:[FSWPLZ/]+\s+)?\*{0,2}"
        r"(?P<desc>Approved\b[^\n]*?electives?\b[^\n]*?|Electives?)"
        r"[\s.…]*[.…]{2}[\s.…]*"
        r"(?P<credits>\d{1,3})(?:\s*-\s*(?P<max>\d{1,3}))?"
        r"(?:\s+(?P<level>\d)(?:\s*-\s*\d)?)?\s*$", re.I),
    suppress_duplicate_blocks=True,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()
    run_extractor(CONFIG, args, ROOT)


if __name__ == "__main__":
    main()
