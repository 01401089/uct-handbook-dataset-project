"""Health Sciences (FHS) undergraduate handbook extractor.

FHS does NOT fit the shared block engine (see CLAUDE.md ground rule): its
programme blocks are delimited by bracket lines carrying one or MORE plan
codes ("[MB014, MB020]", "[BSc Audiology MB011/MB019 & BSc Speech-Language
Pathology MB010/MB018]"), curricula are shared between sibling codes, year
headings are rule-prefixed ("FBA3.4 Second Year", up to SIXTH year for the
MBChB), and stated totals trail the tables with several wordings and
sometimes slashed variant values ("162/168"). This module is therefore a
bespoke programme parser that REUSES the shared grammar and the catalogue
parser from common/handbook_parser.

Conventions (documented in docs/REPLICATION.md):
- The FIRST plan code of a block carries the curriculum; sibling codes get
  specialisation rows with a shared-curriculum note and no rows of their own.
- In a code pair (MB014, MB020 / MB011/MB019 / "MB003AHS09 or MB016") the
  second code is the intervention/extended variant -> variant "extended".
- Slashed totals: first value -> stated_total_credits, second ->
  stated_total_max (variant value, noted).

Run from the repo root:
    python -m extractors.fhs.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.csv_io import write_year_rows
from common.handbook_parser import (
    COLUMN_HEADER, COURSE_ROW, CRED_CONT, DOTS_ONLY, OR_LINE, AND_LINE,
    FacultyConfig, classify_pages, parse_catalogue, resolve_course_code,
    write_csv,
)
from common.pdf_text import dump_pages, iter_pages

ROOT = Path(__file__).resolve().parents[2]
FACULTY = "FHS"

ORDINALS6 = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5,
             "Sixth": 6, "first": 1, "second": 2, "third": 3, "fourth": 4,
             "fifth": 5, "sixth": 6}

MB_CODE = re.compile(r"\bM[BU]\d{3}(?:[A-Z]{2,3}\d{2})?\b")
# Block-start bracket: contains at least one MB code and is not a prose note.
# 2021-2023 print multi-line brackets ("[BSc Audiology programme code: MB011
# or MB019 (Fundamentals of Health ..." with the ] on a later line), so the
# closing bracket is optional.
BLOCK_BRACKET = re.compile(r"^\[(?P<inner>[^\]]*\bM[BU]\d{3}[^\]]*?)"
                           r"(?:\](?:\s*\[[^\]]+\])*)?\s*$")
NOTE_BRACKET = re.compile(r"^\[\s*(?:\*?Note|Refer|See|Intercalated|NB)", re.I)

YEAR_HEADING = re.compile(
    r"^(?:FB[A-Z]?\d+(?:\.\d+)?\s+)?"
    r"(First|Second|Third|Fourth|Fifth|Sixth)[ -]Year\b(?P<tail>.{0,60})$")
TOTAL_LINE = re.compile(
    r"^Total (?:NQF )?credits(?: (?:for|in))?(?: the)?"
    r"(?: year (?P<n>\d)|\s*(?P<ord>first|second|third|fourth|fifth|sixth)"
    r"[ -]year|(?P<bare>))\s*:?[\s.…]*"
    r"(?P<credits>\d{2,4})(?:\s*/\s*(?P<alt>\d{2,4}))?\s*$", re.I)
PROG_TOTAL = re.compile(r"^Total (?:NQF )?credits for (?:the )?programme", re.I)
TITLE_LINE = re.compile(r"^(Bachelor of|MBChB|MB ?ChB|Doctor of)", re.I)

DEGREE_CANON = [
    (re.compile(r"MB\s?ChB|Bachelor of Medicine", re.I),
     ("Bachelor of Medicine and Bachelor of Surgery", "MBChB", "Medicine")),
    (re.compile(r"Audiology", re.I),
     ("Bachelor of Science in Audiology", "BSc(Audiology)", "Audiology")),
    (re.compile(r"Speech[- ]Language", re.I),
     ("Bachelor of Science in Speech-Language Pathology", "BSc(SLP)",
      "Speech-Language Pathology")),
    (re.compile(r"Occupational Therapy", re.I),
     ("Bachelor of Science in Occupational Therapy", "BSc(OT)",
      "Occupational Therapy")),
    (re.compile(r"Physiotherapy", re.I),
     ("Bachelor of Science in Physiotherapy", "BSc(Physio)", "Physiotherapy")),
]


def degree_for(context: str):
    for pat, canon in DEGREE_CANON:
        if pat.search(context):
            return canon
    m = re.search(r"(Higher Certificate|Advanced Diploma|Intercalated"
                  r"|Postgraduate Diploma)[^.\[\]]{0,60}", context, re.I)
    if m:
        t = re.sub(r"\s+", " ", m.group(0)).strip()
        return (t, "", t)
    return (context.strip()[:80] or "Health Sciences programme", "", "")


def parse_programmes(dump_path: Path, sections: dict, year: int):
    """Bespoke FHS programme parser over the RULES AND CURRICULA pages."""
    programmes, curriculum, totals = [], [], {}

    lines = []
    for page_no, text in iter_pages(dump_path):
        if sections.get(page_no) != "programmes":
            continue
        first_seen = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if not first_seen:
                first_seen = True  # running header
                continue
            if not COLUMN_HEADER.match(line):
                lines.append((page_no, line))

    prog = None           # primary programme dict of the current block
    codes = []            # all codes of the block (primary first)
    study_year = 0
    seq = 0
    pending_or = False
    unstamped = []        # rows awaiting a year (stamped by a trailing total)
    title_buf = []

    def close_block():
        nonlocal unstamped
        unstamped = []

    def start_block(inner: str, extra_note: str, page_no: int):
        nonlocal prog, codes, study_year, seq, pending_or, unstamped
        close_block()
        codes = list(dict.fromkeys(MB_CODE.findall(inner)))
        # Where a 10-char PLAN code is printed alongside its 5-char programme
        # code ("Programme code: MB003 ... Plan code: MB003AHS09"), the plan
        # code is authoritative: drop 5-char codes it subsumes and put
        # 10-char codes first.
        long = [c for c in codes if len(c) > 5]
        if long:
            short = [c for c in codes if len(c) == 5
                     and not any(l.startswith(c) for l in long)]
            codes = long + short
        context = inner + " " + " ".join(title_buf[-3:])
        # Combined blocks name several degrees, each with its own code pair
        # ("BSc Audiology MB011/MB019 & BSc Speech-Language Pathology
        # MB010/MB018"): assign each code the degree named in its segment,
        # and within a segment the second code is the extended variant.
        segments = re.split(r"\s*&\s*", inner) if "&" in inner else [context]
        code_meta = {}
        for seg in segments:
            seg_codes = list(dict.fromkeys(MB_CODE.findall(seg)))
            deg, abbrev, spec = degree_for(seg if "&" in inner else context)
            for k, c in enumerate(seg_codes):
                code_meta[c] = (deg, abbrev, spec,
                                "regular" if k == 0 else "extended")
        prog = None
        for k, code in enumerate(codes):
            deg, abbrev, spec, variant = code_meta.get(
                code, (*degree_for(context)[:3], "regular"))
            p = {
                "year": year, "faculty": FACULTY, "plan_code": code,
                "plan_code_raw": "", "programme_code": code[:5],
                "dept_code": code[5:], "degree_name": deg,
                "degree_abbrev": abbrev, "specialisation": spec,
                "variant": variant, "source_page": page_no,
                "notes": ([] if k == 0 else
                          [f"curriculum shared with {codes[0]} (printed in one "
                           f"combined block); see that plan's rows"]),
            }
            if extra_note:
                p["notes"].append(extra_note)
            programmes.append(p)
            if k == 0:
                prog = p
        study_year, seq, pending_or = 0, 0, False

    def stamp(rows, y):
        for r in rows:
            r["study_year"] = y

    for page_no, line in lines:
        m = BLOCK_BRACKET.match(line)
        if m and not NOTE_BRACKET.match(line) and ".." not in line:
            inner = m.group("inner")
            start_block(inner, "", page_no)
            title_buf = []
            continue

        if prog is None:
            title_buf.append(line)
            continue

        m = YEAR_HEADING.match(line)
        if m and len(line) < 90:
            study_year = ORDINALS6[m.group(1)]
            if unstamped:   # stragglers after the previous total open this year
                stamp(unstamped, study_year)
                unstamped = []
            seq, pending_or = 0, False
            continue

        if PROG_TOTAL.match(line):
            unstamped = []
            continue
        m = TOTAL_LINE.match(line)
        if m:
            y = (int(m.group("n")) if m.group("n")
                 else ORDINALS6.get(m.group("ord") or "", None))
            if y is None:
                y = study_year or 1
            if unstamped:
                stamp(unstamped, y)
                unstamped = []
            totals[(prog["plan_code"], y)] = {
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": y, "table_index": 1,
                "stated_total_credits": int(m.group("credits")),
                "stated_total_max": int(m.group("alt")) if m.group("alt") else "",
                "is_minimum": False, "source_page": page_no,
            }
            # Totals TRAIL their tables: rows that follow belong to the next
            # year, so buffer them until a heading or the next total decides.
            study_year = 0
            continue

        if OR_LINE.match(line):
            pending_or = True
            continue
        if AND_LINE.match(line) or DOTS_ONLY.match(line):
            continue

        m = COURSE_ROW.match(line)
        if m:
            seq += 1
            title = re.sub(r"[\s.…]+$", "", m.group("title"))
            title = re.sub(r"\s+", " ", title)
            row_or = False
            if re.search(r"\bOR$", title):
                title, row_or = title[:-2].rstrip(), True
            req, group, member, pick_n = "core", "", "", ""
            if pending_or and curriculum:
                prev = curriculum[-1]
                if not prev["choice_group"]:
                    prev["choice_group"] = f"G{seq}"
                    prev["choice_member"], prev["choice_pick_n"] = 1, 1
                    prev["requirement"] = "option"
                req, group = "option", prev["choice_group"]
                member = int(prev["choice_member"]) + 1
                pick_n = prev["choice_pick_n"]
            row = {
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": study_year or "", "table_index": 1, "seq": seq,
                "course_code_raw": m.group("code"),
                "course_code": resolve_course_code(m.group("code")),
                "course_title": title,
                "nqf_credits": int(m.group("credits")),
                "nqf_level": int(m.group("level")),
                "requirement": req, "choice_group": group,
                "choice_member": member, "choice_pick_n": pick_n,
                "choice_note": "", "is_minimum": False, "source_page": page_no,
            }
            curriculum.append(row)
            if not study_year:
                unstamped.append(row)
            pending_or = row_or
            continue

        prog["notes"].append(line)
        title_buf.append(line)

    for p in programmes:
        p["notes"] = " | ".join(p["notes"])
    # Rows that never received a year (no heading, no trailing total) keep "".
    return programmes, curriculum, sorted(
        totals.values(), key=lambda t: (t["plan_code"], t["study_year"]))


CATALOGUE_CONFIG = FacultyConfig(
    faculty=FACULTY,
    slug="fhs",
    plan_code_any=re.compile(r"^(?P<pre>.*?)\[(?P<code>M[BU]\d{3}[A-Z]{2,3}\d{2})\]\s*$"),
    normalise_plan_code=lambda c: c,
    parse_degree=lambda t: (t, "", ""),
    title_start=re.compile(r"^(Bachelor of|MBChB)", re.I),
    # 2021/2024-2026 use a section header; 2022-2023 use per-degree running
    # headers (BACHELOR OF ... / HIGHER CERTIFICATE ... / ADVANCED DIPLOMA
    # ... / FUNDAMENTALS ... / NELSON MANDELA FIDEL CASTRO ...).
    prog_page=re.compile(
        r"^(?:\d+\s+)?(?:RULES AND CURRICULA FOR UNDERGRADUATE PROGRAMMES"
        r"|BACHELOR OF [A-Z &()\-]+(?: IN [A-Z &()\-]+)?"
        r"|HIGHER CERTIFICATE IN [A-Z &()\-]+|ADVANCED DIPLOMA IN [A-Z &()\-]+"
        r"|FUNDAMENTALS OF HEALTH SCIENCES.*"
        r"|NELSON MANDELA FIDEL CASTRO.*)(?:\s+\d+)?\s*$", re.I),
    cat_page=re.compile(
        r"^(?:\d+\s+)?(?:DEPARTMENTS IN THE FACULTY"
        r"|FACULTIES AND DEPARTMENTS OFFERING COURSES.*|OTHER COURSES OFFERED)"
        r"(?:\s+\d+)?\s*$", re.I),
    page_header=re.compile(
        r"^(?:\d+\s+)?(?:RULES AND CURRICULA.*|DEPARTMENTS IN THE FACULTY"
        r"|FACULTIES AND DEPARTMENTS.*|OTHER COURSES OFFERED|GENERAL INFORMATION"
        r"|IMPORTANT INFORMATION|ADDITIONAL INFORMATION|RESEARCH STRUCTURES"
        r"|GENERAL RULES FOR UNDERGRADUATE STUDENTS|INDEX OF COURSES|INDEX"
        r"|BACHELOR OF [A-Z &()\-]+(?: IN [A-Z &()\-]+)?"
        r"|HIGHER CERTIFICATE IN [A-Z &()\-]+|ADVANCED DIPLOMA IN [A-Z &()\-]+"
        r"|FUNDAMENTALS OF HEALTH SCIENCES.*|NELSON MANDELA FIDEL CASTRO.*)"
        r"(?:\s+\d+)?\s*$", re.I),
    year_heading=YEAR_HEADING,
    dept_by_prefix={
        "AHS": "Health & Rehabilitation Sciences", "HUB": "Human Biology",
        "IBS": "Integrated Biomedical Sciences", "MDN": "Medicine",
        "PED": "Paediatrics", "CHM": "Surgery", "OBS": "Obstetrics & Gynaecology",
        "PPH": "Public Health", "PRY": "Psychiatry", "PTY": "Physiotherapy",
        "CSC": "Computer Science", "SLL": "Languages & Literatures",
        "HSE": "Health Sciences Education", "FCE": "Family Medicine",
        "DOM": "Medicine (Intercalated)", "PSY": "Psychology",
        "STA": "Statistical Sciences", "CEM": "Chemistry", "PHY": "Physics",
        "BIO": "Biological Sciences", "MAM": "Mathematics",
    },
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()

    pdf = ROOT / "faculty-handbooks-undergraduate" / f"{args.year}-fhs-ug.pdf"
    dump = ROOT / "data" / "interim" / f"{args.year}-fhs-ug.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(ROOT)}")

    sections, _hints = classify_pages(CATALOGUE_CONFIG, dump)
    n_prog = sum(1 for v in sections.values() if v == "programmes")
    n_cat = sum(1 for v in sections.values() if v == "catalogue")
    print(f"programme pages: {n_prog}, catalogue pages: {n_cat}")

    programmes, curriculum, totals = parse_programmes(dump, sections, args.year)
    courses, _ = parse_catalogue(CATALOGUE_CONFIG, dump, sections, args.year)

    def merge(path, rows):
        write_year_rows(
            path, rows, args.year,
            keep=lambda r: (r.get("faculty") or r.get("faculty_book") or "")
            not in ("", FACULTY))

    merge(ROOT / "data" / "processed" / "specialisations.csv", programmes)
    merge(ROOT / "data" / "processed" / "curriculum.csv", curriculum)
    merge(ROOT / "data" / "processed" / "curriculum_totals.csv", totals)
    merge(ROOT / "data" / "processed" / "courses.csv", courses)

    print(f"specialisations: {len(programmes)}  curriculum rows: {len(curriculum)}  "
          f"totals: {len(totals)}  courses: {len(courses)}")


if __name__ == "__main__":
    main()
