"""Shared handbook-parsing engine.

Originally built for the Commerce handbooks and promoted to common/ once the
grammar proved general across faculties (COM 2021-2026, then EBE 2021-2026 —
same publisher template). Faculty-specific behaviour lives in a
FacultyConfig supplied by each extractors/<fac>/extract.py; the engine's
logic paths are shared so hazard fixes propagate to every faculty.

The engine parses two section families per handbook:
- programme sections -> specialisations, curriculum rows, stated totals;
- department/catalogue sections -> the course catalogue.

See docs/REPLICATION.md for the layout contracts and hazard catalogue.
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Pattern

from common.pdf_text import iter_pages

ORDINALS = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5}
WORD_N = {"one": 1, "two": 2, "three": 3, "four": 4}

# --- grammar shared verbatim across faculties ------------------------------

COLUMN_HEADER = re.compile(r"^Code Course NQF Credits NQF( Level)?\s*$|^Level\s*$")
CODE_TOKEN = r"[A-Z]{3}\d{4}[A-Z]{0,2}(?:/(?:[A-Z]|\d{4}[A-Z]?))?"
COURSE_ROW = re.compile(
    rf"^(?P<code>{CODE_TOKEN})\s+(?P<title>.+?)[\s.…]*(?P<credits>\d{{1,3}})\s+(?P<level>\d)\s*$")
OR_LINE = re.compile(r"^OR\b[\s.…]*$", re.I)
AND_LINE = re.compile(r"^AND\b[\s.…]*$", re.I)
PLUS_LINE = re.compile(r"^(?:PLUS|Plus)\b[\s.…]*$")
DOTS_ONLY = re.compile(r"^[\s.…]+$")
OPTION_HEADER = re.compile(r"^(?P<name>[A-Z][\w\s&,-]{2,40} Option)\s*:[\s.…]*$")
MENU_HEADER = re.compile(
    r"^Plus (?P<n>one|two|three|four|\d+) courses? from\s*:?[\s.…]*$", re.I)
CORE_LABEL = re.compile(r"^(?:Core|Compulsory) courses.*:[\s.…]*$", re.I)
ELECTIVES_LABEL = re.compile(r"^Elective courses\s*:?[\s.…]*$", re.I)
PICK_INSTRUCTION = re.compile(
    r"\b(?:take|choose|select)\s+(?P<n>one|two|three|four|\d+)\s+(?:option|course|elective)", re.I)
CRED_CONT = re.compile(r"^[\s.…]*(?P<credits>\d{1,3})(?P<plus>\+)?(?:\s+(?P<level>\d))?[\s.…]*$")
ELECTIVE_ROW = re.compile(
    r"^(?P<desc>(?:Plus\s+)?(?:One|Two|Three|Four|Five|Six|\d+|Any|An?)\b[^.]*?"
    r"(?:elective|course)[^.]*?)[\s.…]*\s(?P<credits>\d{1,3})(?P<plus>\+)?"
    r"(?:\s+(?P<level>\d))?\s*$", re.I)
ELECTIVE_NOCRED = re.compile(
    r"^(?P<desc>Plus\b.*(?:course|elective).*?"
    r"|(?:One|Two|Three|Four|Five|Six|\d+|An?)\b[^.]*?electives?\b[^.]*?)[\s.…]*$", re.I)
ELECTIVE_OPEN = re.compile(r"^(?P<desc>Any\b.*electives?\b.*)$", re.I)
ELECTIVE_MIN = re.compile(r"minimum of (?P<credits>\d{1,3}) credits", re.I)
# Stated totals; EBE prints ranges ("108-156") — max group optional.
TOTAL_LINE = re.compile(
    r"^Total(?: credits)?(?: (?:per|for the|for) year)?[\s.…]*"
    r"(?P<gte>>=|\+)?\s*(?P<credits>\d{2,3})(?:\s*-\s*(?P<max>\d{2,3}))?(?P<plus>\+)?\s*$")
TOTAL_PROSE = re.compile(
    r"^The total credits for year (?P<year>\d) equals (?P<credits>\d{2,3})\.?\s*$")
CREDITS_LINE = re.compile(
    r"^(?P<credits>\d{1,3})\s+NQF credits at (?:NQF|HEQSF) level (?P<level>\d{1,2})\b")
COURSE_HEADING = re.compile(r"^(?P<code>[A-Z]{3}\d{4}[A-Z])\s+(?P<title>\S.{2,90})$")
FIELD_LINE = re.compile(
    r"^(Convener|Course convener|Co-convener|Course entry requirements|Course outline"
    r"|Lecture times|DP requirements|Assessment|Course co-requisites)s?\s*:\s*(.*)$", re.I)


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


@dataclass
class FacultyConfig:
    faculty: str                      # "COM", "EBE", ...
    slug: str                         # pdf name part: "com" -> YYYY-com-ug.pdf
    plan_code_any: Pattern            # line-level plan-code heading matcher
    normalise_plan_code: Callable[[str], str]
    parse_degree: Callable[[str], tuple]   # title -> (degree, abbrev, spec)
    title_start: Pattern
    prog_page: Pattern                # running-header -> programme section
    cat_page: Pattern                 # running-header -> catalogue section
    page_header: Pattern              # in-body page-header filter
    year_heading: Pattern             # "(Ordinal) Year Core (Modules|Courses)"
    dept_by_prefix: dict
    umbrella: Optional[Pattern] = None
    variant_by_progcode: dict = field(default_factory=dict)
    variant_from_code: Optional[Callable[[str], Optional[str]]] = None
    advdip_prefix: Optional[str] = None    # plan-code prefix using AdvDip labels
    advdip_labels: list = field(default_factory=list)
    pool_marker: Optional[Pattern] = None  # "ELECTIVE COURSES" pool sections
    extra_elective: Optional[Pattern] = None  # e.g. EBE "Approved elective courses 0-48"
    suppress_duplicate_blocks: bool = False
    total_line: Optional[Pattern] = None   # faculty-specific stated-total grammar
                                           # (LAW: "Total credits for Preliminary
                                           # Level ... 144"); must expose a
                                           # `credits` group; `max`/`gte`/`plus`
                                           # groups optional
    extra_elective_nocred: Optional[Pattern] = None  # slot desc line whose credits
                                           # arrive on a continuation line
    content_reclassify: bool = False       # flip catalogue-classified pages whose
                                           # body shows programme signatures (LAW
                                           # 2026 mislabels the rules section's
                                           # running header)


def classify_pages(cfg: FacultyConfig, dump_path: Path) -> tuple[dict, dict]:
    """Map each page to a section based on its running header line.

    Returns (sections, variant_hints): variant_hints carries the programme
    variant when the page header itself states it (2026-style per-degree
    headers), else None.
    """
    sections, hints = {}, {}
    texts = {}
    for page_no, text in iter_pages(dump_path):
        texts[page_no] = text
        head = ""
        for line in text.splitlines():
            line = line.strip()
            if line:
                head = line
                break
        if cfg.prog_page.match(head):
            sections[page_no] = "programmes"
            if re.search(r"BACHELOR OF", head, re.I):
                low = head.lower()
                hints[page_no] = ("augmented" if "augmented" in low
                                  else "extended" if "extended" in low
                                  else "regular")
        elif cfg.cat_page.match(head):
            sections[page_no] = "catalogue"

    # Fallback for editions that omit the running header on some pages (2023
    # EBE prints only a bare page number there). Applies ONLY to bare-number
    # pages, so fully-headed editions are untouched: first classify such
    # pages by strong content signatures, then let bare-number pages
    # sandwiched between two same-section pages inherit that section.
    bare = set()
    for page_no, text in texts.items():
        if page_no in sections:
            continue
        head = next((l.strip() for l in text.splitlines() if l.strip()), "")
        if not re.fullmatch(r"\d{1,4}", head):
            continue
        bare.add(page_no)
        body = [l.strip() for l in text.splitlines()]
        if any(CREDITS_LINE.match(l) for l in body):
            sections[page_no] = "catalogue"
        elif any(cfg.year_heading.match(l)
                 or (cfg.plan_code_any.match(l) and ".." not in l) for l in body):
            sections[page_no] = "programmes"
    classified = sorted(sections)
    for i, page_no in enumerate(classified[:-1]):
        nxt = classified[i + 1]
        if sections[page_no] == sections[nxt]:
            for p in range(page_no + 1, nxt):
                if p in bare:
                    sections.setdefault(p, sections[page_no])

    if cfg.content_reclassify:
        for page_no, text in texts.items():
            if sections.get(page_no) != "catalogue":
                continue
            body = [l.strip() for l in text.splitlines()]
            if any(cfg.year_heading.match(l)
                   or (cfg.plan_code_any.match(l) and ".." not in l)
                   or (cfg.total_line and cfg.total_line.match(l)) for l in body):
                sections[page_no] = "programmes"
    return sections, hints


def collect_section_lines(cfg: FacultyConfig, dump_path: Path, sections: dict, which: str):
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
            if not cfg.page_header.match(line) and not COLUMN_HEADER.match(line):
                lines.append((page_no, line))
    return lines


def parse_programmes(cfg: FacultyConfig, dump_path: Path, sections: dict,
                     hints: dict, year: int):
    programmes, curriculum, totals, unparsed = [], [], {}, []
    lines = collect_section_lines(cfg, dump_path, sections, "programmes")

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
    advdip_req = None      # (requirement, note) context inside AdvDip blocks
    elective_open = None   # buffered "Any ... electives" line
    await_credits = None   # elective row waiting for a credits continuation line
    pool_mode = False      # inside an alternatives pool ("ELECTIVE COURSES")
    suppressed = False     # duplicate plan-code block whose rows are skipped
    seen_codes = set()

    def reset_table_state():
        nonlocal seq, group_n, pending_or, pending_and, option_set, menu, \
            elective_open, await_credits, pool_mode
        seq, group_n = 0, 0
        pending_or, pending_and = False, False
        option_set, menu, elective_open, await_credits = None, None, None, None
        pool_mode = False

    def start_programme(plan_raw: str, title: str, page_no: int):
        nonlocal prog, study_year, table_index, advdip_req, suppressed
        code = cfg.normalise_plan_code(plan_raw)
        if prog and code == prog["plan_code"] and not suppressed:
            return  # AdvDips repeat their code above the curriculum table
        deg, abbrev, spec = cfg.parse_degree(title)
        v = (hints.get(page_no)
             or cfg.variant_by_progcode.get(code[:5])
             or (cfg.variant_from_code(code) if cfg.variant_from_code else None)
             or variant)
        prog = {
            "year": year, "faculty": cfg.faculty, "plan_code": code,
            "plan_code_raw": plan_raw if plan_raw != code else "",
            "programme_code": code[:5], "dept_code": code[5:],
            "degree_name": deg, "degree_abbrev": abbrev, "specialisation": spec,
            "variant": v, "source_page": page_no, "notes": [],
        }
        suppressed = False
        if code in seen_codes:
            prog["notes"].append(f"DUPLICATE plan code block on p{page_no}")
            if cfg.suppress_duplicate_blocks:
                prog["notes"].append(
                    "rows of this repeat block are suppressed (variant/access "
                    "route sharing the plan code — see DEV-TODO)")
                suppressed = True
        seen_codes.add(code)
        programmes.append(prog)
        study_year, table_index, advdip_req = 0, 0, None
        reset_table_state()
        if cfg.advdip_prefix and code.startswith(cfg.advdip_prefix):
            # Advanced Diplomas have no year headings: their single table is
            # year 1, table 1 (table_index must be 1 or the assembly layer
            # treats every AdvDip row as a secondary table).
            study_year, table_index = 1, 1

    def emit(row):
        if not suppressed:
            curriculum.append(row)

    title_buf = []  # trailing non-matching lines, newest last (for headings)
    for page_no, line in lines:
        # -- programme boundaries ------------------------------------------
        m = cfg.plan_code_any.match(line)
        if m and ".." not in line:  # dotted TOC entries are not headings
            pre = m.group("pre").strip()
            if cfg.title_start.match(pre):
                title = pre
            else:
                # Walk back through buffered lines to the title start; `pre`
                # (a wrapped title tail like "Finance") stays last.
                parts = [pre] if pre else []
                for prev in reversed(title_buf[-3:]):
                    parts.insert(0, prev)
                    if cfg.title_start.match(prev):
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

        if cfg.umbrella and cfg.umbrella.match(line) and not any(c.isdigit() for c in line):
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
        m = cfg.year_heading.match(line)
        if m:
            new_year = ORDINALS[m.group(1)]
            table_index = table_index + 1 if new_year == study_year else 1
            study_year = new_year
            reset_table_state()
            continue

        if cfg.pool_marker and cfg.pool_marker.match(line):
            pool_mode = True
            continue

        if cfg.advdip_prefix and prog["plan_code"].startswith(cfg.advdip_prefix):
            for pat, (req, note) in cfg.advdip_labels:
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
            if not suppressed:
                totals.setdefault((prog["plan_code"], int(m.group("year")), 1), {
                    "year": year, "faculty": cfg.faculty,
                    "plan_code": prog["plan_code"],
                    "study_year": int(m.group("year")), "table_index": 1,
                    "stated_total_credits": int(m.group("credits")),
                    "stated_total_max": "",
                    "is_minimum": False, "source_page": page_no,
                })
            continue
        m = (cfg.total_line or TOTAL_LINE).match(line)
        if m and study_year:
            gd = m.groupdict()
            if not suppressed:
                totals[(prog["plan_code"], study_year, table_index)] = {
                    "year": year, "faculty": cfg.faculty,
                    "plan_code": prog["plan_code"],
                    "study_year": study_year, "table_index": table_index,
                    "stated_total_credits": int(gd["credits"]),
                    "stated_total_max": int(gd["max"]) if gd.get("max") else "",
                    # a range total is a minimum-anchored statement
                    "is_minimum": bool(gd.get("gte") or gd.get("plus")
                                       or gd.get("max")),
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
            # Wrapped desc whose tail carries the credits ("... offered in" /
            # "another faculty .... 48 6"): merge into the pending slot.
            if cfg.extra_elective:
                em = cfg.extra_elective.match(line)
                if em:
                    gd = em.groupdict()
                    await_credits["course_title"] += " " + em.group("desc").rstrip(" .")
                    await_credits["nqf_credits"] = int(gd["credits"])
                    if gd.get("level"):
                        await_credits["nqf_level"] = int(gd["level"])
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
            if pool_mode:
                req, note = "alternative", "elective pool"
            elif menu:
                menu["member"] += 1
                req, group, member, pick_n = ("option", menu["group"],
                                              menu["member"], menu["pick"])
                note = f"pick {menu['pick']} from menu"
            elif option_set:
                req, group, member, pick_n = ("option", option_set["group"],
                                              option_set["member"], 1)
                note = option_set["name"]
            elif (cfg.advdip_prefix and prog["plan_code"].startswith(cfg.advdip_prefix)
                  and advdip_req):
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
                "year": year, "faculty": cfg.faculty, "plan_code": prog["plan_code"],
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

        def emit_elective(desc, credits, level, is_min, note=""):
            nonlocal seq
            seq += 1
            row = {
                "year": year, "faculty": cfg.faculty, "plan_code": prog["plan_code"],
                "study_year": study_year, "table_index": table_index, "seq": seq,
                "course_code_raw": "", "course_code": "",
                "course_title": re.sub(r"\s+", " ", desc),
                "nqf_credits": credits, "nqf_level": level,
                "requirement": "elective", "choice_group": "", "choice_member": "",
                "choice_pick_n": "", "choice_note": note,
                "is_minimum": is_min, "source_page": page_no,
            }
            emit(row)
            return row

        def level_from(desc):
            dm = re.search(r"NQF [Ll]evel (\d)|(\d)(?:st|nd|rd|th) year level", desc)
            lvl = next((g for g in dm.groups() if g), "") if dm else ""
            return int(lvl) if lvl else ""

        if cfg.extra_elective:
            m = cfg.extra_elective.match(line)
            if m and study_year:
                gd = m.groupdict()
                lo = int(gd["credits"])
                hi = int(gd["max"]) if gd.get("max") else ""
                lvl = int(gd["level"]) if gd.get("level") else ""
                emit_elective(m.group("desc").rstrip(" ."), lo, lvl,
                              is_min=hi != "",  # a range is minimum-anchored
                              note=f"range {lo}-{hi}" if hi != "" else "")
                pending_or = pending_and = False
                continue

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
        if not (m and study_year) and cfg.extra_elective_nocred and study_year:
            m = cfg.extra_elective_nocred.match(line)
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


def parse_catalogue(cfg: FacultyConfig, dump_path: Path, sections: dict, year: int):
    courses, unparsed = [], []
    lines = collect_section_lines(cfg, dump_path, sections, "catalogue")

    course = None
    field_name = None
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
                            "year": year, "faculty_book": cfg.faculty,
                            "dept": cfg.dept_by_prefix.get(m.group("code")[:3],
                                                           m.group("code")[:3]),
                            "course_code": m.group("code"), "title": title,
                            "nqf_credits": int(cm.group("credits")),
                            "nqf_level": int(cm.group("level")),
                            "convener": "", "entry_requirements": "", "outline": "",
                            "lecture_times": "", "dp_requirements": "", "assessment": "",
                            "pre_notes": " ".join(lines[k][1] for k in range(i + 1, j)),
                            "source_page": page_no,
                        }
                        courses.append(course)
                        field_name = None
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
                field_name = {"convener": "convener", "course convener": "convener",
                              "co-convener": "convener",
                              "course entry requirements": "entry_requirements",
                              "course co-requisites": "entry_requirements",
                              "course outline": "outline", "lecture times": "lecture_times",
                              "dp requirements": "dp_requirements",
                              "assessment": "assessment"}[key]
                course[field_name] = (course[field_name] + " " + fm.group(2)).strip()
            elif field_name:
                course[field_name] = (course[field_name] + " " + line).strip()
        i += 1

    return courses, unparsed


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print(f"WARNING: no rows for {path.name}")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run_extractor(cfg: FacultyConfig, args, root: Path):
    """Standard main() body shared by faculty extractors."""
    from common.csv_io import write_year_rows
    from common.pdf_text import dump_pages

    pdf = root / "faculty-handbooks-undergraduate" / f"{args.year}-{cfg.slug}-ug.pdf"
    dump = root / "data" / "interim" / f"{args.year}-{cfg.slug}-ug.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(root)}")

    sections, hints = classify_pages(cfg, dump)
    n_prog = sum(1 for v in sections.values() if v == "programmes")
    n_cat = sum(1 for v in sections.values() if v == "catalogue")
    print(f"programme pages: {n_prog}, catalogue pages: {n_cat}")

    programmes, curriculum, totals, unp1 = parse_programmes(cfg, dump, sections,
                                                            hints, args.year)
    courses, unp2 = parse_catalogue(cfg, dump, sections, args.year)

    # Merge-by-faculty-within-year: these tables hold several faculties per
    # year, so replace only this faculty's rows for the year. Legacy rows
    # without a faculty column (pre-multi-faculty schema) are treated as
    # owned by the writing faculty and therefore replaced.
    def merge(path, rows):
        write_year_rows(
            path, rows, args.year,
            keep=lambda r: (r.get("faculty") or r.get("faculty_book") or "")
            not in ("", cfg.faculty))

    merge(root / "data" / "processed" / "specialisations.csv", programmes)
    merge(root / "data" / "processed" / "curriculum.csv", curriculum)
    merge(root / "data" / "processed" / "curriculum_totals.csv", totals)
    merge(root / "data" / "processed" / "courses.csv", courses)
    if unp1 or unp2:
        write_csv(root / "validation" / f"{cfg.slug}_unparsed_{args.year}.csv",
                  unp1 + unp2)

    print(f"specialisations: {len(programmes)}  curriculum rows: {len(curriculum)}  "
          f"totals: {len(totals)}  courses: {len(courses)}")
