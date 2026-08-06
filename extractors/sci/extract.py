"""Science (SCI) undergraduate handbook extractor.

SCI's unit of curriculum is the MAJOR, not the specialisation: the "DEGREES
OFFERED IN THE FACULTY" section prints ~20-23 "Major in X" blocks, each with
a department-stream bracket ("[MAM01]") and (First|Second|Third) Year Core
Courses tables. Plan codes are not printed in full; per the documented UCT
scheme they are the SB001 programme code + the printed stream code
(SB001MAM01), and are synthesised that way here (`plan_code_raw` keeps the
printed bracket).

Distinct structures (bespoke parser, FHS mould, reusing the shared grammar):
- "Either / MAM1000W / Or both / MAM1031F / and / MAM1032S" alternatives:
  first-listed member is the ideal pick, the "Or both" bundle is member 2.
- "And two of ... / One of ..." pick-n menus.
- No stated year totals are printed for majors: credit anchors come from the
  degree-rules layer, not this parser (totals output is empty by design).
- Rows whose credits wrap to the next line are completed from the book's own
  course catalogue (credits + NQF level joined by course code).

Run from the repo root:
    python -m extractors.sci.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.csv_io import write_year_rows
from common.handbook_parser import (
    COLUMN_HEADER, COURSE_ROW, DOTS_ONLY, OR_LINE, AND_LINE,
    FacultyConfig, classify_pages, parse_catalogue, resolve_course_code,
)
from common.pdf_text import dump_pages, iter_pages

ROOT = Path(__file__).resolve().parents[2]
FACULTY = "SCI"
PROGRAMME_CODE = "SB001"   # the BSc programme family per the UCT code scheme

MAJOR_HEADING = re.compile(r"^Major in (?P<name>[A-Z][^.\[]{2,70}?)\s*$")
STREAM_BRACKET = re.compile(r"^\[(?P<code>[A-Z]{2,3}\d{2})\]\s*$")
YEAR_HEADING = re.compile(r"^(First|Second|Third|Fourth) Year Core Courses\s*$")
ORD = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4}
MENU = re.compile(
    r"^(?:And |Plus )?(?P<n>one|two|three|four)\s+of\b[\w\s,]*[\s.…]*$", re.I)
EITHER = re.compile(r"^Either\b[\s.…]*$", re.I)
OR_BOTH = re.compile(r"^Or both\b[\s.…]*$", re.I)
WORD_N = {"one": 1, "two": 2, "three": 3, "four": 4}
# Bare row whose credits wrapped to the next line: code + title only.
BARE_ROW = re.compile(
    r"^(?P<code>[A-Z]{3}\d{4}[A-Z]{0,2}(?:/(?:[A-Z]|\d{4}[A-Z]?))?)\s+"
    r"(?P<title>[A-Z(].*?)[\s.…]*$")

CATALOGUE_CONFIG = FacultyConfig(
    faculty=FACULTY,
    slug="sci",
    plan_code_any=STREAM_BRACKET,          # unused for cataloguing
    normalise_plan_code=lambda c: c,
    parse_degree=lambda t: (t, "", ""),
    title_start=re.compile(r"^Major in ", re.I),
    prog_page=re.compile(
        r"^(?:\d+\s+)?DEGREES OFFERED IN THE FACULTY(?:\s+\d+)?\s*$", re.I),
    cat_page=re.compile(
        r"^(?:\d+\s+)?(?:DEPARTMENTS IN THE FACULTY"
        r"|COURSES OFFERED BY DEPARTMENTS IN OTHER FACULTIES.*"
        r"|INTER-FACULTY UNITS)(?:\s+\d+)?\s*$", re.I),
    page_header=re.compile(
        r"^(?:\d+\s+)?(?:DEGREES OFFERED IN THE FACULTY|DEPARTMENTS IN THE FACULTY"
        r"|COURSES OFFERED BY DEPARTMENTS.*|INTER-FACULTY UNITS|SCHEDULE OF COURSES"
        r"|SCIENCE FACULTY COURSES.*|GENERAL INFORMATION|ADDITIONAL INFORMATION"
        r"|INDEX|CONTENTS)(?:\s+\d+)?\s*$", re.I),
    year_heading=YEAR_HEADING,
    dept_by_prefix={
        "MAM": "Mathematics and Applied Mathematics", "STA": "Statistical Sciences",
        "CSC": "Computer Science", "PHY": "Physics", "CEM": "Chemistry",
        "BIO": "Biological Sciences", "MCB": "Molecular & Cell Biology",
        "EGS": "Environmental & Geographical Science", "GEO": "Geological Sciences",
        "AST": "Astronomy", "AGE": "Archaeology", "SEA": "Ocean & Atmosphere Science",
        "HUB": "Human Biology", "PSY": "Psychology",
    },
)


def parse_majors(dump_path: Path, sections: dict, year: int):
    programmes, curriculum = [], []
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
                first_seen = True
                continue
            if not COLUMN_HEADER.match(line):
                lines.append((page_no, line))

    prog = None
    pending_name = None    # "Major in X" seen, awaiting its bracket
    seen_streams = {}
    study_year = 0
    seq = 0
    group_n = 0
    pending_or = pending_and = False
    menu = None            # {"group", "member", "pick"}

    def start_major(name, stream, page_no):
        nonlocal prog, study_year, seq, group_n, pending_or, pending_and, menu
        if not stream:  # synthesise a stream code if the bracket is missing
            stream = "XX" + f"{len(seen_streams)+1:02d}"
        n = seen_streams.get(stream, 0)
        seen_streams[stream] = n + 1
        code = PROGRAMME_CODE + stream
        prog = {
            "year": year, "faculty": FACULTY, "plan_code": code,
            "plan_code_raw": stream, "programme_code": PROGRAMME_CODE,
            "dept_code": stream, "degree_name": "Bachelor of Science (major)",
            "degree_abbrev": "BSc", "specialisation": name.strip(),
            "variant": "regular", "source_page": page_no,
            "notes": ["plan code synthesised as SB001 + printed stream code "
                      "(full code not printed in the handbook)"],
        }
        if n:
            prog["notes"].append(f"DUPLICATE stream bracket [{stream}] on p{page_no}")
        programmes.append(prog)
        study_year, seq, group_n = 0, 0, 0
        pending_or = pending_and = False
        menu = None

    for page_no, line in lines:
        m = MAJOR_HEADING.match(line)
        if m:
            pending_name = (m.group("name"), page_no)
            continue
        m = STREAM_BRACKET.match(line)
        if m and pending_name:
            start_major(pending_name[0], m.group("code"), pending_name[1])
            pending_name = None
            continue
        if pending_name and (YEAR_HEADING.match(line) or COURSE_ROW.match(line)):
            # major with no printed bracket: open it anyway
            start_major(pending_name[0], "", pending_name[1])
            pending_name = None
            # fall through to process this line below

        if prog is None:
            continue

        m = YEAR_HEADING.match(line)
        if m:
            study_year = ORD[m.group(1)]
            seq, group_n = 0, 0
            pending_or = pending_and = False
            menu = None
            continue

        if EITHER.match(line):
            continue                      # next row is simply member 1
        if OR_BOTH.match(line):
            pending_or = True             # the bundle that follows is member 2
            continue
        if OR_LINE.match(line):
            pending_or = True
            continue
        if AND_LINE.match(line) or re.match(r"^and\b[\s.…]*$", line):
            pending_and = True
            continue
        if DOTS_ONLY.match(line):
            continue
        m = MENU.match(line)
        if m and study_year:
            group_n += 1
            menu = {"group": f"Y{study_year}G{group_n}", "member": 0,
                    "pick": WORD_N[m.group("n").lower()]}
            pending_or = pending_and = False
            continue

        row_m = COURSE_ROW.match(line)
        bare_m = None if row_m else BARE_ROW.match(line)
        if (row_m or bare_m) and study_year:
            g = row_m or bare_m
            seq += 1
            title = re.sub(r"[\s.…*]+$", "", g.group("title"))
            title = re.sub(r"\s+", " ", title)
            req, group, member, pick_n, note = "core", "", "", "", ""
            if menu:
                menu["member"] += 1
                req, group, member, pick_n = ("option", menu["group"],
                                              menu["member"], menu["pick"])
                note = f"pick {menu['pick']} from menu"
            elif pending_and and curriculum and \
                    curriculum[-1]["plan_code"] == prog["plan_code"]:
                prev = curriculum[-1]
                req, group, member, pick_n = (prev["requirement"],
                                              prev["choice_group"],
                                              prev["choice_member"],
                                              prev["choice_pick_n"])
            elif pending_or and curriculum and \
                    curriculum[-1]["plan_code"] == prog["plan_code"]:
                prev = curriculum[-1]
                if not prev["choice_group"]:
                    group_n += 1
                    prev["choice_group"] = f"Y{study_year}G{group_n}"
                    prev["choice_member"], prev["choice_pick_n"] = 1, 1
                    prev["requirement"] = "option"
                req, group = "option", prev["choice_group"]
                member = int(prev["choice_member"]) + 1
                pick_n = prev["choice_pick_n"]
            curriculum.append({
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": 1, "seq": seq,
                "course_code_raw": g.group("code"),
                "course_code": resolve_course_code(g.group("code")),
                "course_title": title,
                "nqf_credits": int(row_m.group("credits")) if row_m else "",
                "nqf_level": int(row_m.group("level")) if row_m else "",
                "requirement": req, "choice_group": group,
                "choice_member": member, "choice_pick_n": pick_n,
                "choice_note": note, "is_minimum": False,
                "source_page": page_no,
            })
            pending_or = pending_and = False
            continue

        # any other line: notes; a prose line closes an open menu
        menu = None
        if prog is not None:
            prog["notes"].append(line)

    for p in programmes:
        p["notes"] = " | ".join(p["notes"])
    return programmes, curriculum


def fill_from_catalogue(curriculum, courses):
    """Complete wrapped rows (blank credits) from the book's own catalogue."""
    idx = {c["course_code"]: c for c in courses}
    filled = 0
    for r in curriculum:
        if r["nqf_credits"] == "" and r["course_code"] in idx:
            r["nqf_credits"] = idx[r["course_code"]]["nqf_credits"]
            r["nqf_level"] = idx[r["course_code"]]["nqf_level"]
            filled += 1
    return filled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()

    pdf = ROOT / "faculty-handbooks-undergraduate" / f"{args.year}-sci-ug.pdf"
    dump = ROOT / "data" / "interim" / f"{args.year}-sci-ug.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(ROOT)}")

    sections, _ = classify_pages(CATALOGUE_CONFIG, dump)
    programmes, curriculum = parse_majors(dump, sections, args.year)
    courses, _ = parse_catalogue(CATALOGUE_CONFIG, dump, sections, args.year)
    filled = fill_from_catalogue(curriculum, courses)

    def merge(path, rows):
        write_year_rows(
            path, rows, args.year,
            keep=lambda r: (r.get("faculty") or r.get("faculty_book") or "")
            not in ("", FACULTY))

    merge(ROOT / "data" / "processed" / "specialisations.csv", programmes)
    merge(ROOT / "data" / "processed" / "curriculum.csv", curriculum)
    merge(ROOT / "data" / "processed" / "courses.csv", courses)

    # Rules layer: the degree-composition rules (how majors make a degree)
    # -- see common/degree_rules.py and docs/REPLICATION.md sec 10.
    from common.degree_rules import extract_degree_rules
    degree_rules = extract_degree_rules(FACULTY, args.year, dump)
    if degree_rules:
        merge(ROOT / "data" / "processed" / "degree_rules.csv", degree_rules)

    blank = sum(1 for r in curriculum if r["nqf_credits"] == "")
    print(f"majors: {len(programmes)}  curriculum rows: {len(curriculum)}  "
          f"courses: {len(courses)}  (credits filled from catalogue: {filled}, "
          f"still blank: {blank})")


if __name__ == "__main__":
    main()
