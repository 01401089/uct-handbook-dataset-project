"""Commerce (COM) undergraduate handbook extractor.

Reads faculty-handbooks-undergraduate/{year}-com-ug.pdf and writes:

- data/processed/specialisations.csv   one row per plan/specialisation code
- data/processed/curriculum.csv        one row per course-slot per plan-year
- data/processed/curriculum_totals.csv stated "Total credits per year" anchors
- data/processed/courses.csv           course catalogue from department sections
- validation/com_unparsed_{year}.csv   lines that matched no pattern where one
                                       was expected

Run from the repo root:
    python -m extractors.com.extract --year 2025 [--skip-dump]

Layout facts this parser relies on (verified against the 2025 edition; see
docs/REPLICATION.md before pointing it at a new year):

- Programme blocks: 1-2 title lines then "[PLANCODE]" alone on a line.
  Umbrella lines ("Bachelor of Commerce Augmented", "... Extended Academic
  Development") set the variant for subsequent blocks.
- Curriculum tables: "<Ordinal> Year Core Modules" headings, rows of
  "CODE Title ..... credits level", "OR"/"PLUS" separator lines, elective
  placeholder lines, and a "Total credits per year ... N" anchor.
- Advanced Diplomas (CU codes) use block labels ("Prescribed courses",
  "And two of the following elective courses", "Approved electives ...").
- Course catalogue: "CODE TITLE" heading, then within a few lines
  "NN NQF credits at NQF level N", then labelled fields.
"""
import argparse
import csv
import re
from pathlib import Path

from common.csv_io import write_year_rows
from common.pdf_text import dump_pages, iter_pages

ROOT = Path(__file__).resolve().parents[2]
FACULTY = "COM"

# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

# A programme block starts at any non-TOC line ending with a [PLANCODE]
# bracket. Observed forms across editions:
#   "[CB004FTX04]"                                    (code alone, 2025/2026)
#   "[CB003BUS01][SAQA ID:4411]"                      (trailing bracket, 2021/2022)
#   "Bachelor of ... [CB004FTX05]"                    (inline, 2024)
#   "Finance [CB025BUS09]"                            (wrapped title tail, 2024)
# The title is reconstructed from the pre-bracket text plus buffered lines.
#   "[CB011ECO03#]"                                   (footnote marker inside
#                                                      the bracket, 2022/2023)
#   "[CB0015ECO03]"                                    (extra-zero misprint, 2024)
PLAN_CODE_ANY = re.compile(
    r"^(?P<pre>.*?)\s*\[(?P<code>C[BU][0-9O]{2,4}[A-Z]{3}\d{2})[#*\s]*\]"
    r"(?:\s*\[[^\]]+\])*\s*$")

# Known programme-code families (documented in CLAUDE.md). Used as the variant
# fallback when neither a page-header hint nor an umbrella line applies.
VARIANT_BY_PROGCODE = {
    "CB001": "regular", "CB003": "regular", "CB004": "regular", "CB019": "regular",
    "CB023": "augmented", "CB024": "augmented", "CB025": "augmented", "CB026": "augmented",
    "CB011": "extended", "CB015": "extended", "CB018": "extended", "CB020": "extended",
}

TITLE_START = re.compile(r"^(Bachelor of|Advanced Diploma in|Postgraduate Diploma in)", re.I)
UMBRELLA = re.compile(
    r"^Bachelor of (Business Science|Commerce)\b(?!.* specialising)(?!.* in [A-Z]{2})")

YEAR_HEADING = re.compile(r"^(First|Second|Third|Fourth|Fifth) Year Core Modules\s*$")
ORDINALS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5}

COLUMN_HEADER = re.compile(r"^Code Course NQF Credits NQF( Level)?\s*$|^Level\s*$")
PAGE_HEADER = re.compile(
    r"^(?:\d+\s+)?(?:PROGRAMMES OF STUDY|RULES FOR ADVANCED DIPLOMAS|GENERAL INFORMATION"
    r"|DEPARTMENTS IN THE FACULTY OF COMMERCE|FACULTIES AND DEPARTMENTS.*|ADDITIONAL INFORMATION)"
    r"(?:\s+\d+)?\s*$")

# Course row: code + optional composite tail, title, trailing credits + level.
# The separator before credits may be dots, spaces, or nothing at all
# ("...Research** .....142 8", "...Research Report60 8").
CODE_TOKEN = r"[A-Z]{3}\d{4}[A-Z]{0,2}(?:/(?:[A-Z]|\d{4}[A-Z]?))?"
COURSE_ROW = re.compile(
    rf"^(?P<code>{CODE_TOKEN})\s+(?P<title>.+?)[\s.…]*(?P<credits>\d{{1,3}})\s+(?P<level>\d)\s*$")
OR_LINE = re.compile(r"^OR\b[\s.…]*$", re.I)
AND_LINE = re.compile(r"^AND\b[\s.…]*$", re.I)
PLUS_LINE = re.compile(r"^(?:PLUS|Plus)\b[\s.…]*$")
DOTS_ONLY = re.compile(r"^[\s.…]+$")

# "Mathematical Statistics Option: ..." — named alternative blocks of rows.
OPTION_HEADER = re.compile(r"^(?P<name>[A-Z][\w\s&,-]{2,40} Option)\s*:[\s.…]*$")
# "Plus 2 courses from: ..." — pick-n menu of the course rows that follow.
MENU_HEADER = re.compile(
    r"^Plus (?P<n>one|two|three|four|\d+) courses? from\s*:?[\s.…]*$", re.I)
WORD_N = {"one": 1, "two": 2, "three": 3, "four": 4}
# Sub-block labels inside 4th-year tables: "Core courses (totalling 78 NQF
# credits):" resumes core rows; "Elective Courses:" opens a menu whose pick
# count comes from a nearby instruction line ("... required to take two
# options ...").
CORE_LABEL = re.compile(r"^(?:Core|Compulsory) courses.*:[\s.…]*$", re.I)
ELECTIVES_LABEL = re.compile(r"^Elective courses\s*:?[\s.…]*$", re.I)
PICK_INSTRUCTION = re.compile(
    r"\b(?:take|choose|select)\s+(?P<n>one|two|three|four|\d+)\s+(?:option|course|elective)", re.I)
# Continuation line carrying only credits(+level) for a wrapped elective row.
CRED_CONT = re.compile(r"^[\s.…]*(?P<credits>\d{1,3})(?P<plus>\+)?(?:\s+(?P<level>\d))?[\s.…]*$")

# "One elective at 1st year level .... 18 5" / "Plus one NQF Level 7 course ... 18+"
# The NQF-level column is sometimes omitted; credits may carry a trailing +.
ELECTIVE_ROW = re.compile(
    r"^(?P<desc>(?:Plus\s+)?(?:One|Two|Three|Four|Five|Six|\d+|Any|An?)\b[^.]*?"
    r"(?:elective|course)[^.]*?)[\s.…]*\s(?P<credits>\d{1,3})(?P<plus>\+)?"
    r"(?:\s+(?P<level>\d))?\s*$", re.I)
# Elective slot with no credit figure on the same line ("PLUS one elective at
# 1st year level ...", "Plus ECO2008S and 1 NQF level 6 course or ..."):
# credits come from a continuation line or are inferred from the year total.
ELECTIVE_NOCRED = re.compile(
    r"^(?P<desc>Plus\b.*(?:course|elective).*?"
    r"|(?:One|Two|Three|Four|Five|Six|\d+|An?)\b[^.]*?electives?\b[^.]*?)[\s.…]*$", re.I)
# "Any NQF level 7 electives ... " + "(totalling a) minimum of 120 credits"
ELECTIVE_OPEN = re.compile(r"^(?P<desc>Any\b.*electives?\b.*)$", re.I)
ELECTIVE_MIN = re.compile(r"minimum of (?P<credits>\d{1,3}) credits", re.I)

TOTAL_LINE = re.compile(
    r"^Total(?: credits)?(?: (?:per|for the|for) year)?[\s.…]*"
    r"(?P<gte>>=|\+)?\s*(?P<credits>\d{2,3})(?P<plus>\+)?\s*$")
TOTAL_PROSE = re.compile(
    r"^The total credits for year (?P<year>\d) equals (?P<credits>\d{2,3})\.?\s*$")

# Advanced Diploma block labels -> requirement context
ADVDIP_LABELS = [
    (re.compile(r"^Prescribed courses\s*$", re.I), ("core", "")),
    (re.compile(r"^And (two|three) of the following elective courses", re.I),
     ("option", "choose {0} of the listed electives")),
    (re.compile(r"^Approved electives at NQF level \d include", re.I),
     ("alternative", "approved elective pool")),
]

CREDITS_LINE = re.compile(
    r"^(?P<credits>\d{1,3})\s+NQF credits at (?:NQF|HEQSF) level (?P<level>\d{1,2})\b")
COURSE_HEADING = re.compile(r"^(?P<code>[A-Z]{3}\d{4}[A-Z])\s+(?P<title>\S.{2,90})$")
FIELD_LINE = re.compile(
    r"^(Convener|Course convener|Co-convener|Course entry requirements|Course outline"
    r"|Lecture times|DP requirements|Assessment|Course co-requisites)s?\s*:\s*(.*)$", re.I)

DEPT_BY_PREFIX = {
    "ACC": "College of Accounting", "BUS": "School of Management Studies",
    "DOC": "Demography", "ECO": "School of Economics", "FTX": "Finance and Tax",
    "GPP": "Nelson Mandela School of Public Governance",
    "GSB": "Graduate School of Business", "INF": "Information Systems",
    "CML": "Commercial Law", "CSC": "Computer Science",
    "EGS": "Environmental & Geographical Science", "GEO": "Geological Sciences",
    "MAM": "Mathematics and Applied Mathematics", "PHI": "Philosophy",
    "POL": "Political Studies", "PSY": "Psychology", "PVL": "Private Law",
    "PBL": "Public Law", "STA": "Statistical Sciences", "MUZ": "Music",
}


def normalise_plan_code(raw: str) -> str:
    """CBO18BUS01 -> CB018BUS01; CB25BUS09 -> CB025BUS09;
    CB0015ECO03 -> CB015ECO03 (extra-zero misprint)."""
    m = re.match(r"^(C[BU])([0-9O]{2,4})([A-Z]{3}\d{2})$", raw)
    head, num, tail = m.groups()
    num = num.replace("O", "0")
    while len(num) > 3 and num.startswith("0"):
        num = num[1:]
    return head + num.zfill(3) + tail


def resolve_course_code(raw: str) -> str:
    """First-listed variant of a composite code: STA2020F/S -> STA2020F,
    CML1001F/1004S -> CML1001F, ECO1011FS -> ECO1011F."""
    code = raw.split("/")[0]
    m = re.match(r"^([A-Z]{3}\d{4})(FS|SF)$", code)
    return m.group(1) + m.group(2)[0] if m else code


def tidy_caps(text: str) -> str:
    """FINANCE with ACCOUNTING -> Finance with Accounting; keep mixed-case words."""
    words = [w.capitalize() if w.isupper() and len(w) > 1 else w for w in text.split()]
    out = [words[0]] + [w.lower() if w.lower() in
                        {"and", "with", "of", "in", "the", "for"} else w
                        for w in words[1:]] if words else words
    return " ".join(out)


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


# ---------------------------------------------------------------------------
# Programme-section parser
# ---------------------------------------------------------------------------

# Running-header families across editions:
#   2021-2025: "PROGRAMMES OF STUDY 44" / "DEPARTMENTS IN THE FACULTY ..."
#   2024:      Title Case + "Departments offering courses to the Faculty ..."
#   2026:      per-degree headers ("BACHELOR OF COMMERCE AUGMENTED 15") and
#              per-department headers ("SCHOOL OF ECONOMICS 121")
PROG_PAGE = re.compile(
    r"^(?:\d+\s+)?(?:RULES FOR ADVANCED DIPLOMAS|PROGRAMMES OF STUDY"
    r"|BACHELOR OF (?:COMMERCE|BUSINESS SCIENCE)(?: AUGMENTED| EXTENDED)?)"
    r"(?:\s+\d+)?\s*$", re.I)
CAT_PAGE = re.compile(
    r"^(?:\d+\s+)?(?:DEPARTMENTS IN THE FACULTY.*|FACULTIES AND DEPARTMENTS.*"
    r"|DEPARTMENTS OFFERING COURSES.*|COLLEGE OF .+|SCHOOL OF .+|DEPARTMENT OF .+"
    r"|GRADUATE SCHOOL OF BUSINESS|NELSON MANDELA SCHOOL.*|EDUCATION DEVELOPMENT UNIT.*)"
    r"(?:\s+\d+)?\s*$", re.I)


def classify_pages(dump_path: Path) -> tuple[dict, dict]:
    """Map each page to a section based on its running header line.

    Returns (sections, variant_hints): variant_hints carries the programme
    variant when the page header itself states it (2026-style per-degree
    headers), else None.
    """
    sections, hints = {}, {}
    for page_no, text in iter_pages(dump_path):
        head = ""
        for line in text.splitlines():
            line = line.strip()
            if line:
                head = line
                break
        if PROG_PAGE.match(head):
            sections[page_no] = "programmes"
            if re.search(r"BACHELOR OF", head, re.I):
                low = head.lower()
                hints[page_no] = ("augmented" if "augmented" in low
                                  else "extended" if "extended" in low
                                  else "regular")
        elif CAT_PAGE.match(head):
            sections[page_no] = "catalogue"
    return sections, hints


def collect_section_lines(dump_path: Path, sections: dict, which: str):
    """(page_no, line) pairs for pages of a section, dropping each page's
    running-header line (the first non-empty line) and column headers."""
    lines = []
    for page_no, text in iter_pages(dump_path):
        if sections.get(page_no) != which:
            continue
        first_seen = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if not first_seen:
                first_seen = True  # running header — always skip
                continue
            if not PAGE_HEADER.match(line) and not COLUMN_HEADER.match(line):
                lines.append((page_no, line))
    return lines


def parse_programmes(dump_path: Path, sections: dict, hints: dict, year: int):
    programmes, curriculum, totals, unparsed = [], [], {}, []
    lines = collect_section_lines(dump_path, sections, "programmes")

    variant = "regular"
    prog = None            # current programme dict
    study_year = 0
    table_index = 0
    seq = 0
    group_n = 0            # per-table choice-group counter
    pending_or = False     # next row starts a new member of the current group
    pending_and = False    # next row joins the previous row's member
    option_set = None      # {"group": id, "member": int} for named Option blocks
    menu = None            # {"group": id, "member": int, "pick": n} for pick-n menus
    advdip_req = None      # (requirement, pick_n) context inside CU blocks
    elective_open = None   # buffered "Any ... electives" line
    await_credits = None   # elective row waiting for a credits continuation line
    seen_codes = set()

    def reset_table_state():
        nonlocal seq, group_n, pending_or, pending_and, option_set, menu, elective_open, await_credits
        seq, group_n = 0, 0
        pending_or, pending_and = False, False
        option_set, menu, elective_open, await_credits = None, None, None, None

    def start_programme(plan_raw: str, title: str, page_no: int):
        nonlocal prog, study_year, table_index, advdip_req
        code = normalise_plan_code(plan_raw)
        if prog and code == prog["plan_code"]:
            return  # AdvDips repeat their code above the curriculum table
        deg, abbrev, spec = parse_degree(title)
        prog = {
            "year": year, "faculty": FACULTY, "plan_code": code,
            "plan_code_raw": plan_raw if plan_raw != code else "",
            "programme_code": code[:5], "dept_code": code[5:],
            "degree_name": deg, "degree_abbrev": abbrev, "specialisation": spec,
            # Precedence: page-header hint (2026 layout) > known programme-code
            # family > umbrella-line tracking (2021-2025 layouts).
            "variant": (hints.get(page_no) or VARIANT_BY_PROGCODE.get(code[:5])
                        or variant),
            "source_page": page_no, "notes": [],
        }
        if code in seen_codes:
            prog["notes"].append(f"DUPLICATE plan code block on p{page_no}")
        seen_codes.add(code)
        programmes.append(prog)
        study_year, table_index, advdip_req = 0, 0, None
        reset_table_state()
        if code.startswith("CU"):
            # Advanced Diplomas have no year headings: their single table is
            # year 1, table 1 (table_index must be 1 or the assembly layer
            # treats every AdvDip row as a secondary table).
            study_year, table_index = 1, 1

    def emit(row):
        curriculum.append(row)

    title_buf = []  # trailing non-matching lines, newest last (for headings)
    for page_no, line in lines:
        # -- programme boundaries ------------------------------------------
        m = PLAN_CODE_ANY.match(line)
        if m and ".." not in line:  # dotted TOC entries are not headings
            pre = m.group("pre").strip()
            if TITLE_START.match(pre):
                title = pre
            else:
                # Walk back through buffered lines to the title start; `pre`
                # (a wrapped title tail like "Finance") stays last.
                parts = [pre] if pre else []
                for prev in reversed(title_buf[-3:]):
                    parts.insert(0, prev)
                    if TITLE_START.match(prev):
                        break
                title = " ".join(parts)
            # Drop umbrella text glued in front of the real title.
            low = title.lower()
            last = max(low.rfind("bachelor of"), low.rfind("advanced diploma"))
            if last > 0:
                title = title[last:]
            start_programme(m.group("code"), title, page_no)
            title_buf = []
            continue

        if UMBRELLA.match(line) and not any(c.isdigit() for c in line):
            low = line.lower()
            if "extended" in low:
                variant = "extended"
            elif "augmented" in low:
                variant = "augmented"
            elif "academic development" in low:
                variant = "extended"
            else:
                variant = "regular"
            title_buf.append(line)
            continue

        if prog is None:
            title_buf.append(line)
            continue

        # -- inside a programme block --------------------------------------
        m = YEAR_HEADING.match(line)
        if m:
            new_year = ORDINALS[m.group(1)]
            table_index = table_index + 1 if new_year == study_year else 1
            study_year = new_year
            reset_table_state()
            continue

        if prog["plan_code"].startswith("CU"):
            for pat, (req, note) in ADVDIP_LABELS:
                lm = pat.match(line)
                if lm:
                    advdip_req = (req, note.format(*lm.groups()) if lm.groups() else note)
                    break
            else:
                lm = None
            if lm:
                continue

        m = TOTAL_PROSE.match(line)
        if m:
            # Fill-only: never overwrite an inline "Total credits per year"
            # (some prose totals are copy-paste remnants from sibling blocks).
            totals.setdefault((prog["plan_code"], int(m.group("year")), 1), {
                "year": year, "plan_code": prog["plan_code"],
                "study_year": int(m.group("year")), "table_index": 1,
                "stated_total_credits": int(m.group("credits")),
                "is_minimum": False, "source_page": page_no,
            })
            continue
        m = TOTAL_LINE.match(line)
        if m and study_year:
            totals[(prog["plan_code"], study_year, table_index)] = {
                "year": year, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": table_index,
                "stated_total_credits": int(m.group("credits")),
                "is_minimum": bool(m.group("gte") or m.group("plus")),
                "source_page": page_no,
            }
            menu, option_set, await_credits = None, None, None
            continue

        # Credits continuation for a wrapped elective row ("... 18+ 7").
        if await_credits is not None:
            cm = CRED_CONT.match(line)
            if cm:
                await_credits["nqf_credits"] = int(cm.group("credits"))
                if cm.group("plus"):
                    await_credits["is_minimum"] = True
                if cm.group("level") and not await_credits["nqf_level"]:
                    await_credits["nqf_level"] = int(cm.group("level"))
                await_credits = None
                continue
            await_credits = None

        if OR_LINE.match(line):
            pending_or, pending_and = True, False
            continue
        if AND_LINE.match(line):
            pending_and, pending_or = True, False
            continue
        if PLUS_LINE.match(line) or DOTS_ONLY.match(line):
            continue

        m = OPTION_HEADER.match(line)
        if m and study_year:
            if pending_or and option_set:
                option_set["member"] += 1     # the alternative Option block
                pending_or = False
            else:
                group_n += 1
                option_set = {"group": f"Y{study_year}G{group_n}", "member": 1,
                              "name": m.group("name")}
            menu = None
            continue

        m = MENU_HEADER.match(line)
        if m and study_year:
            group_n += 1
            n = m.group("n").lower()
            pick = WORD_N.get(n) if n in WORD_N else (int(n) if n.isdigit() else 1)
            menu = {"group": f"Y{study_year}G{group_n}", "member": 0, "pick": pick}
            option_set = None
            continue

        if CORE_LABEL.match(line) and study_year:
            menu, option_set = None, None
            continue
        if ELECTIVES_LABEL.match(line) and study_year:
            group_n += 1
            # Pick count defaults to 1 until an instruction line updates it.
            menu = {"group": f"Y{study_year}G{group_n}", "member": 0, "pick": 1}
            option_set = None
            continue

        m = COURSE_ROW.match(line)
        if m and study_year:
            seq += 1
            title = re.sub(r"[\s.…]+$", "", m.group("title"))
            title = re.sub(r"\s+", " ", title)
            row_or = row_and = False
            if re.search(r"\bOR$", title):
                title, row_or = title[:-2].rstrip(), True
            if re.search(r"\bAND$", title):
                title, row_and = title[:-3].rstrip(), True
            if title.endswith(" and"):
                title = title[:-4]

            req, group, member, pick_n, note = "core", "", "", "", ""
            if menu:
                menu["member"] += 1
                req, group, member, pick_n = ("option", menu["group"],
                                              menu["member"], menu["pick"])
                note = f"pick {menu['pick']} from menu"
            elif option_set:
                req, group, member, pick_n = ("option", option_set["group"],
                                              option_set["member"], 1)
                note = option_set["name"]
            elif prog["plan_code"].startswith("CU") and advdip_req:
                req, note = advdip_req
                if req == "option":
                    group_n = max(group_n, 1)
                    group, pick_n = "ADVDIP-EL", 2
                    member = 1 + sum(1 for r in curriculum
                                     if r["plan_code"] == prog["plan_code"]
                                     and r["choice_group"] == "ADVDIP-EL")
            elif pending_and and curriculum and curriculum[-1]["plan_code"] == prog["plan_code"]:
                prev = curriculum[-1]
                req, group, member, pick_n = (prev["requirement"], prev["choice_group"],
                                              prev["choice_member"], prev["choice_pick_n"])
            elif pending_or:
                prev = curriculum[-1]
                if not prev["choice_group"]:
                    group_n += 1
                    prev["choice_group"] = f"Y{study_year}G{group_n}"
                    prev["choice_member"], prev["choice_pick_n"] = 1, 1
                    prev["requirement"] = "option"
                req, group = "option", prev["choice_group"]
                member = int(prev["choice_member"]) + 1
                pick_n = prev["choice_pick_n"]

            emit({
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": table_index, "seq": seq,
                "course_code_raw": m.group("code"),
                "course_code": resolve_course_code(m.group("code")),
                "course_title": title,
                "nqf_credits": int(m.group("credits")), "nqf_level": int(m.group("level")),
                "requirement": req, "choice_group": group, "choice_member": member,
                "choice_pick_n": pick_n, "choice_note": note,
                "is_minimum": False, "source_page": page_no,
            })
            pending_or, pending_and = row_or, row_and
            continue

        # A non-course line ends any open pick-n menu — unless the menu has no
        # rows yet, in which case it may be the instruction preamble that sets
        # the pick count ("... required to take two options ...").
        if menu:
            if menu["member"] == 0:
                pm = PICK_INSTRUCTION.search(line)
                if pm:
                    n = pm.group("n").lower()
                    menu["pick"] = WORD_N.get(n) if n in WORD_N else int(n)
                    continue
            else:
                menu = None

        def emit_elective(desc, credits, level, is_min):
            nonlocal seq
            seq += 1
            row = {
                "year": year, "faculty": FACULTY, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": table_index, "seq": seq,
                "course_code_raw": "", "course_code": "",
                "course_title": re.sub(r"\s+", " ", desc),
                "nqf_credits": credits, "nqf_level": level,
                "requirement": "elective", "choice_group": "", "choice_member": "",
                "choice_pick_n": "", "choice_note": "",
                "is_minimum": is_min, "source_page": page_no,
            }
            emit(row)
            return row

        def level_from(desc):
            dm = re.search(r"NQF [Ll]evel (\d)|(\d)(?:st|nd|rd|th) year level", desc)
            lvl = next((g for g in dm.groups() if g), "") if dm else ""
            return int(lvl) if lvl else ""

        m = ELECTIVE_ROW.match(line)
        if m and study_year:
            desc = re.sub(r"[\s.…]+$", "", m.group("desc"))
            lvl = int(m.group("level")) if m.group("level") else level_from(desc)
            emit_elective(desc, int(m.group("credits")), lvl, bool(m.group("plus")))
            pending_or = pending_and = False
            continue

        if elective_open:
            m = ELECTIVE_MIN.search(line)
            if m:
                emit_elective(elective_open, int(m.group("credits")),
                              level_from(elective_open), True)
                elective_open = None
                continue
            elective_open = None
        m = ELECTIVE_OPEN.match(line)
        if m and study_year:
            elective_open = m.group("desc")
            continue

        m = ELECTIVE_NOCRED.match(line)
        if m and study_year:
            desc = re.sub(r"[\s.…]+$", "", m.group("desc"))
            # Credits may follow on a continuation line; else inferred downstream.
            await_credits = emit_elective(desc, "", level_from(desc), False)
            pending_or = pending_and = False
            continue

        # Anything else inside a block is a note/footnote.
        prog["notes"].append(line)
        title_buf.append(line)

    for p in programmes:
        p["notes"] = " | ".join(p["notes"])
    return programmes, curriculum, sorted(totals.values(),
                                          key=lambda t: (t["plan_code"], t["study_year"])), unparsed


# ---------------------------------------------------------------------------
# Course-catalogue parser
# ---------------------------------------------------------------------------

def parse_catalogue(dump_path: Path, sections: dict, year: int):
    courses, unparsed = [], []
    lines = collect_section_lines(dump_path, sections, "catalogue")

    course = None
    field = None
    i = 0
    while i < len(lines):
        page_no, line = lines[i]
        m = COURSE_HEADING.match(line)
        if m:
            title = m.group("title").strip()
            letters = [c for c in title if c.isalpha()]
            caps = letters and sum(c.isupper() for c in letters) / len(letters) >= 0.6
            if caps:
                # Confirm with a credits line within the next 4 lines.
                for j in range(i + 1, min(i + 5, len(lines))):
                    cm = CREDITS_LINE.match(lines[j][1])
                    if cm:
                        course = {
                            "year": year, "faculty_book": FACULTY,
                            "dept": DEPT_BY_PREFIX.get(m.group("code")[:3], m.group("code")[:3]),
                            "course_code": m.group("code"), "title": title,
                            "nqf_credits": int(cm.group("credits")),
                            "nqf_level": int(cm.group("level")),
                            "convener": "", "entry_requirements": "", "outline": "",
                            "lecture_times": "", "dp_requirements": "", "assessment": "",
                            "pre_notes": " ".join(lines[k][1] for k in range(i + 1, j)),
                            "source_page": page_no,
                        }
                        courses.append(course)
                        field = None
                        i = j + 1
                        break
                else:
                    i += 1
                    continue
                continue
        if course is not None:
            fm = FIELD_LINE.match(line)
            if fm:
                key = fm.group(1).lower()
                field = {"convener": "convener", "course convener": "convener",
                         "co-convener": "convener",
                         "course entry requirements": "entry_requirements",
                         "course co-requisites": "entry_requirements",
                         "course outline": "outline", "lecture times": "lecture_times",
                         "dp requirements": "dp_requirements",
                         "assessment": "assessment"}[key]
                course[field] = (course[field] + " " + fm.group(2)).strip()
            elif field:
                course[field] = (course[field] + " " + line).strip()
        i += 1

    return courses, unparsed


# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print(f"WARNING: no rows for {path.name}")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true")
    args = ap.parse_args()

    pdf = ROOT / "faculty-handbooks-undergraduate" / f"{args.year}-com-ug.pdf"
    dump = ROOT / "data" / "interim" / f"{args.year}-com-ug.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(ROOT)}")

    sections, hints = classify_pages(dump)
    n_prog = sum(1 for v in sections.values() if v == "programmes")
    n_cat = sum(1 for v in sections.values() if v == "catalogue")
    print(f"programme pages: {n_prog}, catalogue pages: {n_cat}")

    programmes, curriculum, totals, unp1 = parse_programmes(dump, sections, hints, args.year)
    courses, unp2 = parse_catalogue(dump, sections, args.year)

    write_year_rows(ROOT / "data" / "processed" / "specialisations.csv",
                    programmes, args.year)
    write_year_rows(ROOT / "data" / "processed" / "curriculum.csv",
                    curriculum, args.year)
    write_year_rows(ROOT / "data" / "processed" / "curriculum_totals.csv",
                    totals, args.year)
    write_year_rows(ROOT / "data" / "processed" / "courses.csv",
                    courses, args.year)
    if unp1 or unp2:
        write_csv(ROOT / "validation" / f"com_unparsed_{args.year}.csv", unp1 + unp2)

    print(f"specialisations: {len(programmes)}  curriculum rows: {len(curriculum)}  "
          f"totals: {len(totals)}  courses: {len(courses)}")


if __name__ == "__main__":
    main()
