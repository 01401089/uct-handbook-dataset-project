"""Humanities (HUM) undergraduate handbook extractor.

HUM's unit of curriculum is the MAJOR, printed INSIDE the department
sections (not in a programmes section): ~39-41 blocks of
"Requirements for a major in X" + a stream bracket ("[AFS01]"), followed by
(First|Second|Third) Year courses sub-blocks whose rows are bare
"CODE Title" lines WITHOUT credit columns — credits and NQF levels are
joined from the book's own course catalogue. "ONE of the following:" lines
open pick-n menus. Plan codes are synthesised as HB001 + the printed stream
code (HB001AFS01) per the documented UCT scheme.

Majors serve both the BA and the BSocSc; the degree-level composition rules
(how many majors + electives make a degree) belong to the rules layer, so
no stated year totals are emitted here.

Run from the repo root:
    python -m extractors.hum.extract --year 2025 [--skip-dump]
"""
import argparse
import re
from pathlib import Path

from common.csv_io import write_year_rows
from common.handbook_parser import (
    COURSE_ROW, DOTS_ONLY, FacultyConfig, parse_catalogue, resolve_course_code,
)
from common.pdf_text import dump_pages, iter_pages

ROOT = Path(__file__).resolve().parents[2]
FACULTY = "HUM"
PROGRAMME_CODE = "HB001"   # the BA/BSocSc programme family per the UCT scheme

MAJOR_HEADING = re.compile(
    r"^Requirements for (?:a|the) [Mm]ajor in (?P<name>[A-Z][^.\[]{2,70}?)\s*$")
STREAM_BRACKET = re.compile(r"^\[(?P<code>[A-Z]{2,3}\d{2})\]\s*$")
YEAR_HEADING = re.compile(r"^(First|Second|Third|Fourth) Year [Cc]ourses\s*$")
ORD = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4}
CODE_TITLE_HEADER = re.compile(r"^Code Title\s*$")
MENU = re.compile(
    r"^(?:And |Plus )?(?P<n>one|two|three|four)\s+(?:of|from)\b[^.]*?:?\s*$", re.I)
WORD_N = {"one": 1, "two": 2, "three": 3, "four": 4}
# Bare row: code + mixed-case title, no credit columns.
BARE_ROW = re.compile(
    r"^(?P<code>[A-Z]{3}\d{4}[A-Z]{0,2}(?:/(?:[A-Z]|\d{4}[A-Z]?))?)\s+"
    r"(?P<title>[A-Z(].*?)[\s.…]*$")

SKIP_HEADERS = re.compile(
    r"^(?:\d+\s+)?(?:GENERAL INFORMATION|CONTENTS|INDEX|UNIVERSITY OF CAPE TOWN"
    r"|The University has made every effort.*)(?:\s+\d+)?\s*$", re.I)

CATALOGUE_CONFIG = FacultyConfig(
    faculty=FACULTY,
    slug="hum",
    plan_code_any=STREAM_BRACKET,
    normalise_plan_code=lambda c: c,
    parse_degree=lambda t: (t, "", ""),
    title_start=MAJOR_HEADING,
    prog_page=re.compile(r"$^"),           # majors live in dept pages: no
    cat_page=re.compile(r"$^"),            # header-based sectioning (see below)
    page_header=re.compile(r"^(?:\d+\s+)?[A-Z][A-Z ,&'()\-]+(?:\s+\d+)?\s*$"),
    year_heading=YEAR_HEADING,
    dept_by_prefix={},                     # prefix fallback names the dept
)


def classify_all_pages(dump_path: Path):
    """HUM prints majors inside department sections, so both parsers scan
    every content page (front matter excluded); the catalogue parser's
    credits-line confirmation keeps it safe on non-catalogue text."""
    sections = {}
    for page_no, text in iter_pages(dump_path):
        head = next((l.strip() for l in text.splitlines() if l.strip()), "")
        if not SKIP_HEADERS.match(head):
            sections[page_no] = "catalogue"
    return sections


def parse_majors(dump_path: Path, sections: dict, year: int):
    programmes, curriculum = [], []
    lines = []
    for page_no, text in iter_pages(dump_path):
        if page_no not in sections:
            continue
        first_seen = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if not first_seen:
                first_seen = True   # running header (department name)
                continue
            if not CODE_TITLE_HEADER.match(line):
                lines.append((page_no, line))

    prog = None
    pending_name = None
    seen_streams = {}
    study_year = 0
    collecting = False     # inside a year sub-block's row run
    seq = 0
    group_n = 0
    menu = None

    def start_major(name, stream, page_no):
        nonlocal prog, study_year, seq, group_n, menu, collecting
        n = seen_streams.get(stream, 0)
        seen_streams[stream] = n + 1
        code = PROGRAMME_CODE + stream
        prog = {
            "year": year, "faculty": FACULTY, "plan_code": code,
            "plan_code_raw": stream, "programme_code": PROGRAMME_CODE,
            "dept_code": stream,
            "degree_name": "Bachelor of Arts / Bachelor of Social Science (major)",
            "degree_abbrev": "BA/BSocSc", "specialisation": name.strip(),
            "variant": "regular", "source_page": page_no,
            "notes": ["plan code synthesised as HB001 + printed stream code "
                      "(full code not printed in the handbook); credits joined "
                      "from the course catalogue"],
        }
        if n:
            prog["notes"].append(f"DUPLICATE stream bracket [{stream}] on p{page_no}")
        programmes.append(prog)
        study_year, seq, group_n = 0, 0, 0
        menu, collecting = None, False

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
        if pending_name and YEAR_HEADING.match(line):
            # bracket missing: synthesise a stream from the first row's dept
            start_major(pending_name[0], f"XX{len(seen_streams)+1:02d}",
                        pending_name[1])
            pending_name = None

        if prog is None:
            continue

        m = YEAR_HEADING.match(line)
        if m:
            study_year = ORD[m.group(1)]
            seq, group_n = 0, 0
            menu, collecting = None, True
            continue

        if not collecting:
            continue

        if DOTS_ONLY.match(line):
            continue
        m = MENU.match(line)
        if m:
            group_n += 1
            menu = {"group": f"Y{study_year}G{group_n}", "member": 0,
                    "pick": WORD_N[m.group("n").lower()]}
            continue

        g = COURSE_ROW.match(line) or BARE_ROW.match(line)
        if g:
            seq += 1
            title = re.sub(r"[\s.…*]+$", "", g.group("title"))
            title = re.sub(r"\s+", " ", title)
            gd = g.groupdict()
            req, group, member, pick_n, note = "core", "", "", "", ""
            if menu:
                menu["member"] += 1
                req, group, member, pick_n = ("option", menu["group"],
                                              menu["member"], menu["pick"])
                note = f"pick {menu['pick']} from menu"
            curriculum.append({
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": 1, "seq": seq,
                "course_code_raw": g.group("code"),
                "course_code": resolve_course_code(g.group("code")),
                "course_title": title,
                "nqf_credits": int(gd["credits"]) if gd.get("credits") else "",
                "nqf_level": int(gd["level"]) if gd.get("level") else "",
                "requirement": req, "choice_group": group,
                "choice_member": member, "choice_pick_n": pick_n,
                "choice_note": note, "is_minimum": False,
                "source_page": page_no,
            })
            continue

        # Any other line ends the current row run (footnotes, prerequisites,
        # prose); the block itself stays open for the next year heading.
        collecting = False
        menu = None
        prog["notes"].append(line)

    for p in programmes:
        p["notes"] = " | ".join(p["notes"][:40])
    return programmes, curriculum


def fill_from_catalogue(curriculum, courses):
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

    pdf = ROOT / "faculty-handbooks-undergraduate" / f"{args.year}-hum-ug.pdf"
    dump = ROOT / "data" / "interim" / f"{args.year}-hum-ug.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(ROOT)}")

    sections = classify_all_pages(dump)
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

    blank = sum(1 for r in curriculum if r["nqf_credits"] == "")
    print(f"majors: {len(programmes)}  curriculum rows: {len(curriculum)}  "
          f"courses: {len(courses)}  (credits filled: {filled}, blank: {blank})")


if __name__ == "__main__":
    main()
