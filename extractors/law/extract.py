"""Law (LAW) undergraduate handbook extractor.

Faculty configuration for the shared engine in common/handbook_parser.py.
The LAW book follows the common template with these deltas (stable across
2021-2026 — no cross-edition layout drift observed):

- The undergraduate content is the "RULES FOR LLB DEGREE STREAMS" section.
  Three streams, printed with 5-character programme codes and no department
  suffix: [LP001] graduate LLB, [LB002] four-year undergraduate LLB,
  [LB003] legacy five-year stream (no new intake after 2019 -> "extended").
- Year headings: "First Year YEAR 1 (PRELIMINARY LEVEL)" etc.
- Stated totals are per LEVEL: "Total credits for Preliminary Level ... 144"
  (a stream grand total also prints; it is deliberately NOT matched so it
  cannot overwrite the level totals).
- The many bracketed postgraduate codes (LM.../LG002...) live in the
  postgraduate sections, which the page classification excludes.
- Published fees (fees book sec 11.6) are single year-less amounts
  ("Undergraduate LLB ... R 76 810") -> handled as flat annual fees in
  build_main_dataset.

Run from the repo root:
    python -m extractors.law.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.handbook_parser import FacultyConfig, run_extractor

ROOT = Path(__file__).resolve().parents[2]

PLAN_CODE_ANY = re.compile(
    r"^(?P<pre>.*?)\s*\[(?P<code>L[BPG][0-9O]{3}(?:[A-Z]{2,3}\d{2})?)[#*\s]*\]"
    r"(?:\s*\[[^\]]+\])*\s*$")


def normalise_plan_code(raw: str) -> str:
    return raw.replace("O", "0")


def parse_degree(title: str) -> tuple[str, str, str]:
    """All UG LAW streams are the Bachelor of Laws; the stream is the spec."""
    t = re.sub(r"\s+", " ", title).strip()
    t = re.sub(r"\s*-\s*\*.*$", "", t)  # drop "- *No new intake..." tails
    return "Bachelor of Laws", "LLB", t or ""


def variant_from_code(code: str) -> str:
    return "extended" if code == "LB003" else "regular"


CONFIG = FacultyConfig(
    faculty="LAW",
    slug="law",
    plan_code_any=PLAN_CODE_ANY,
    normalise_plan_code=normalise_plan_code,
    parse_degree=parse_degree,
    title_start=re.compile(
        r"^(Graduate LLB|Four-year undergraduate LLB|Five-year stream"
        r"|Two-year graduate)", re.I),
    prog_page=re.compile(
        r"^(?:\d+\s+)?RULES FOR LLB DEGREE STREAMS(?:\s+\d+)?\s*$", re.I),
    cat_page=re.compile(
        r"^(?:\d+\s+)?(?:COURSE OUTLINES \(LLB\)|COURSES IN THE FACULTY"
        r"|DEPARTMENTS IN THE FACULTY)(?:\s+\d+)?\s*$", re.I),
    page_header=re.compile(
        r"^(?:\d+\s+)?(?:RULES FOR LLB DEGREE STREAMS|COURSE OUTLINES \([A-Z]+\)"
        r"|COURSES IN THE FACULTY|DEPARTMENTS IN THE FACULTY|GENERAL INFORMATION"
        r"|POSTGRADUATE STUDY PROGRAMMES|RULES FOR POSTGRADUATE PROGRAMMES"
        r"|BURSARIES, SCHOLARSHIPS AND PRIZES|EXCHANGE COURSES)"
        r"(?:\s+\d+)?\s*$", re.I),
    # Graduate/4-year streams: "First Year YEAR 1 (PRELIMINARY LEVEL)";
    # the legacy five-year stream uses COM-style "First Year Core Modules".
    year_heading=re.compile(
        r"^(First|Second|Third|Fourth|Fifth) Year "
        r"(?:YEAR \d \([A-Z ]+LEVEL\)|Core Modules)\s*$"),
    dept_by_prefix={
        "PVL": "Private Law", "PBL": "Public Law", "CML": "Commercial Law",
        "DOL": "Faculty of Law (skills/community)", "SLL": "School for Legal Practice",
    },
    variant_from_code=variant_from_code,
    # Three printed wordings — "Total credits for Preliminary Level",
    # "... for first (Preliminary) year", and the legacy five-year stream's
    # "... for first year" (no parenthetical). The stream grand totals
    # ("... for the undergraduate LLB stream") deliberately do NOT match here;
    # they are captured by the rules layer (degree_rules.csv) instead.
    total_line=re.compile(
        r"^Total credits for (?:(?:Preliminary|Intermediate|Final) Level"
        r"|(?:first|second|third|fourth|fifth)"
        r"(?: \((?:Preliminary|Intermediate|Final)\))? year)"
        r"[\s.…]*(?P<credits>\d{2,3})(?P<plus>\+)?\s*$"),
    # Cross-faculty / language / research requirement lines that carry their
    # own credits ("AND two semester courses in another faculty ... 36 5",
    # "Research Component (elective courses and research paper) ... 36 8").
    extra_elective=re.compile(
        r"^(?P<desc>(?:AND\s+|One\s+|Two\s+|Three\s+)?[A-Za-z(][^.]*?"
        r"\b(?:courses?|Component|faculty|language)\b[^.]*?)"
        r"[\s.…]*(?P<credits>\d{1,3})\s+(?P<level>\d)\s*$", re.I),
    # Slot description whose credits arrive on the next line ("Two semester
    # courses in a single language, or a whole course in a language" +
    # "..... 36 5"). Must end in a letter, so rule prose (which ends with a
    # full stop) never matches.
    extra_elective_nocred=re.compile(
        r"^(?P<desc>(?:One|Two|Three|AND|and)\b[^.…]*\bcourses?\b[^.…]*[a-z])\s*$"),
    # LB003 wraps discontinued-course rows before their credits:
    # "PVL1006W Foundations of South African Law (5YP) (No longer on" +
    # "offer after 2019) ... 36 5".
    course_row_nocred=re.compile(
        r"^(?P<code>[A-Z]{3}\d{4}[A-Z])\s+"
        r"(?P<title>.*(?:\(5YP\).*|\(No(?: longer on)?))\s*$"),
    course_cred_cont=re.compile(
        r"^(?P<tail>[^.…]{0,60}?\))[\s.…]*"
        r"(?P<credits>\d{1,3})\s+(?P<level>\d)\s*$"),
    content_reclassify=True,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()
    run_extractor(CONFIG, args, ROOT)


if __name__ == "__main__":
    main()
