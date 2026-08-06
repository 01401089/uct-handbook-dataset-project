"""Degree-level rules extraction — the "rules layer".

The faculty handbooks print, in their rules sections, degree-level facts the
curriculum tables do not carry: minimum total credits for the degree,
level-specific credit requirements, durations, and (LAW) whole-stream credit
totals. These record the credit re-think directly (e.g. COM FBB2: BBusSc
minimum 623 credits through 2024, 528 from the 2025 edition; EBE FB3.2:
4-year degrees 576 -> 560 in 2026; LAW: undergraduate LLB stream total
660 -> 637 in 2026) and provide a whole-degree validation anchor.

Output: data/processed/degree_rules.csv, one row per printed rule statement,
merged by year and faculty like every other shared table. Rule codes are
provenance only — COM re-assigned its rule-code families wholesale between
the 2023 and 2024 editions (FBE/FBF/FBG each name different degrees in
different years), so rows are keyed by the degree heading text
(`degree_scope`), never by `rule_ref`.

Parsing notes (see docs/REPLICATION.md, rules-layer section):
- COM minimum-credit sentences wrap mid-clause in 5 of 6 editions and have
  three surface forms ("of which"/"with a minimum of", "will be"/"must be",
  NQF/HEQSF, and a missing space in 2024's "120NQF") — lines are joined and
  whitespace-collapsed before matching.
- EBE per-programme minima use five wording templates, including the
  Mechanical family's "to a value of at least" and, from 2025,
  cohort-dependent statements ("A candidate who registers in 2025 ... 560
  ... registered before 2025 ... 576") -> one row per cohort.
- LAW prints whole-stream grand totals ("Total credits for the graduate LLB
  stream ... 504") -> rows with is_stream_total=True; the five-year legacy
  stream (LB003) prints one in every edition it appears, although its year
  tables print no totals.
- FHS professional degrees are duration-ruled, not credit-ruled; the only
  credit rule is FBC3.1 (intercalated BSc(Med), >= 360 credits).
"""
import re
from pathlib import Path

from common.pdf_text import iter_pages

WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _row(year, faculty, **kw):
    base = {
        "year": year, "faculty": faculty, "degree_scope": "",
        "plan_code_hint": "", "rule_ref": "", "min_total_credits": "",
        "min_level_credits": "", "min_level": "", "max_total_credits": "",
        "duration_years": "", "cohort": "", "is_stream_total": False,
        "source_page": "", "quote": "",
    }
    base.update(kw)
    return base


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _pages(dump_path: Path):
    """(page_no, [stripped lines], collapsed_page_text) per page."""
    for page_no, text in iter_pages(dump_path):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        yield page_no, lines, _collapse(text)


def _window(lines, i, n=3):
    """Line i joined with its next n-1 lines, whitespace-collapsed —
    rule sentences wrap mid-clause in most editions."""
    return _collapse(" ".join(lines[i:i + n]))


def _dur_value(word_expr: str):
    """'four' -> 4; 'four or five' -> '4-5'; 'six' -> 6."""
    words = re.findall(r"[a-z]+|\d+", word_expr.lower())
    nums = [WORD_NUM.get(w) or (int(w) if w.isdigit() else None) for w in words]
    nums = [n for n in nums if n]
    if not nums:
        return ""
    return nums[0] if len(nums) == 1 else f"{min(nums)}-{max(nums)}"


# --- COM -------------------------------------------------------------------

COM_HEADING = re.compile(
    r"^(?:Rules for |DEGREE )?(?P<deg>Bachelor of (?:Business Science|Commerce)"
    r"(?: in Actuarial Science)?(?: Academic Development)?)\s*"
    r"(?:\[[^\]]*\]?)?\s*$", re.I)
COM_ADVDIP_HEADING = re.compile(
    r"^(?P<deg>Advanced Diploma in [A-Za-z][A-Za-z ]{2,60})\s*"
    r"(?:\[[^\]]*\]?)?\s*$", re.I)
COM_MIN = re.compile(
    r"(?P<ref>FB[A-Z]\d+(?:\.\d+)?)\s+The curriculum for this degree shall "
    r"consist of a minimum of\s+(?P<total>\d{3})\s*NQF credits\s+"
    r"(?:of which|with)\s+(?:a\s+minimum\s+of\s+)?(?P<lvlcr>\d{2,3})\s*"
    r"(?:NQF\s*)?credits\s+(?:will be\s+|must be\s+)?at\s+(?:NQF|HEQSF)\s+"
    r"[Ll]evel\s+(?P<lvl>\d)", re.I)
COM_DUR = re.compile(
    r"(?P<ref>FB[A-Z]\d+(?:\.\d+)?)\s+The curriculum(?: for the degree)? "
    r"shall extend over (?:a minimum of )?"
    r"(?P<dur>[a-z]+(?: or [a-z]+)?) (?:academic )?years?", re.I)
COM_ACCREDITED = re.compile(
    r"is accredited with (?P<total>\d{2,3}) NQF credits", re.I)


def _com_rules(year, dump_path):
    rows, seen = [], set()
    scope = ""
    for page_no, lines, _page_text in _pages(dump_path):
        for i, line in enumerate(lines):
            m = COM_HEADING.match(line)
            # 2026 wraps the heading mid-phrase ("... in Actuarial" /
            # "Science [CB003BUS01, CB003BUS09]") — retry on a 2-line join.
            if not m and re.match(r"^(?:Rules for |DEGREE )?Bachelor of\b",
                                  line, re.I):
                m = COM_HEADING.match(_window(lines, i, 2))
            if not m:
                am = COM_ADVDIP_HEADING.match(line)
                # AdvDip headings must be followed by their plan-code bracket
                # within 2 lines — the qualifications-register table wraps the
                # same names without one.
                if am and any("[" in nxt for nxt in lines[i:i + 3]):
                    m = am
            if m:
                scope = _collapse(m.group("deg"))
                # normalise ALL-CAPS headings ("BACHELOR OF COMMERCE")
                if scope.isupper() or " In " in scope.title():
                    scope = scope.title()
                scope = scope.replace(" Of ", " of ").replace(" In ", " in ")
                continue
            win = _window(lines, i)
            m = COM_MIN.search(win)
            if m and (scope, m.group("ref"), "min") not in seen:
                seen.add((scope, m.group("ref"), "min"))
                rows.append(_row(year, "COM", degree_scope=scope,
                                 rule_ref=m.group("ref"),
                                 min_total_credits=int(m.group("total")),
                                 min_level_credits=int(m.group("lvlcr")),
                                 min_level=int(m.group("lvl")),
                                 source_page=page_no, quote=m.group(0)))
                continue
            m = COM_DUR.search(win)
            if m and m.start() == 0 and (scope, m.group("ref"), "dur") not in seen:
                seen.add((scope, m.group("ref"), "dur"))
                rows.append(_row(year, "COM", degree_scope=scope,
                                 rule_ref=m.group("ref"),
                                 duration_years=_dur_value(m.group("dur")),
                                 source_page=page_no, quote=m.group(0)))
                continue
            m = COM_ACCREDITED.search(win)
            if m and scope.startswith("Advanced Diploma") and \
                    (scope, "accredited") not in seen:
                seen.add((scope, "accredited"))
                rows.append(_row(year, "COM", degree_scope=scope,
                                 min_total_credits=int(m.group("total")),
                                 source_page=page_no, quote=m.group(0)))
    return rows


# --- EBE -------------------------------------------------------------------

EBE_FB32 = re.compile(
    r"FB3\.2\s+Candidates must complete approved courses of not less than\s+"
    r"(?P<c4>\d{3})\s+credits in the case of the degrees which have a minimum "
    r"duration of 4 years and not less than\s+(?P<c3>\d{3})\s+credits in the "
    r"case of degrees which have a minimum duration of 3 years", re.I)
EBE_DUR = re.compile(
    r"FB2\.(?P<sub>[12])\s+The curriculum shall extend over not less than\s+"
    r"(?P<n>\d)\s+academic years", re.I)
EBE_PLAN = re.compile(r"\[(?P<code>E[BM]\d{3}[A-Z]{2,3}\d{2})[#*\s]*\]")
# Per-programme minima: the five wording templates, cohort-split sentences,
# and Civil's parenthetical alternative.
EBE_MIN = re.compile(
    r"(?P<cohort>A candidate who (?:first )?register(?:s|ed)"
    r" (?:in|before) \d{4}|A candidate|Students are required to complete"
    r"|students on the three-year transferee programme are required to"
    r" complete)"
    r"(?: shall complete)? approved courses"
    r"(?: of a value not less than| of not less than| to a value of at least"
    r"| of a value of at least)?\s+"
    r"(?P<total>\d{3})\s*credits"
    r"(?:\s*\(or (?P<alt>\d{3}) credits if admitted[^)]{0,120}\))?", re.I)
# Transferee/access-route wording ("students on the three-year transferee
# programme are required to complete 464 credits") — no "approved courses".
EBE_MIN_TRANSFEREE = re.compile(
    r"(?:transferee|conversion|Technology|access)[^.]{0,80}?"
    r"required to complete\s+(?P<total>\d{3})\s+credits", re.I)
EBE_TITLE = re.compile(r"^(?:Bachelor of |Programme for University of Technology)")


def _ebe_rules(year, dump_path):
    rows = []
    seen_fb32 = seen_dur = False
    seen_sent = set()

    # Flatten to a global line stream so plan codes can bind in either
    # direction: some programmes print their minimum-credit sentence ABOVE
    # the plan-code bracket (Civil), most below it.
    stream = []          # (page_no, line)
    brackets = []        # (stream_index, plan_code); title lines break scope
    page_texts = []
    for page_no, lines, page_text in _pages(dump_path):
        page_texts.append((page_no, page_text))
        for line in lines:
            idx = len(stream)
            stream.append((page_no, line))
            if EBE_TITLE.match(line):
                brackets.append((idx, ""))   # scope break
            pm = EBE_PLAN.search(line)
            if pm and ".." not in line:      # dotted TOC lines aren't headings
                brackets.append((idx, pm.group("code")))

    def hint_for(idx):
        """Nearest bracket before idx (a title line breaks that scope);
        else the first bracket after idx within 60 lines (skipping title
        breaks — a sentence printed above its own programme's bracket, like
        Civil's, has its title between the sentence and the code)."""
        best = ""
        for b_idx, code in brackets:
            if b_idx <= idx:
                best = code if idx - b_idx <= 60 else ""
                continue
            if best:
                break
            if b_idx - idx > 60:
                break
            if code:
                return code
        return best

    for page_no, page_text in page_texts:
        m = EBE_FB32.search(page_text)
        if m and not seen_fb32:
            seen_fb32 = True
            for scope, total in (("4-year degrees (faculty rule FB3.2)",
                                  int(m.group("c4"))),
                                 ("3-year degrees (faculty rule FB3.2)",
                                  int(m.group("c3")))):
                rows.append(_row(year, "EBE", degree_scope=scope,
                                 rule_ref="FB3.2", min_total_credits=total,
                                 source_page=page_no,
                                 quote=_collapse(m.group(0))[:300]))
        for m in ([] if seen_dur else EBE_DUR.finditer(page_text)):
            scope = ("BAS, BSc(ConstStudies), BSc(PropStudies)"
                     if m.group("sub") == "1"
                     else "BSc(Eng), BSc(Geomatics)")
            rows.append(_row(year, "EBE", degree_scope=scope,
                             rule_ref=f"FB2.{m.group('sub')}",
                             duration_years=int(m.group("n")),
                             source_page=page_no, quote=m.group(0)))
        if any(r["rule_ref"] == "FB2.2" for r in rows):
            seen_dur = True

    all_lines = [l for _, l in stream]
    for i, (page_no, line) in enumerate(stream):
        win = _window(all_lines, i)
        m = EBE_MIN.search(win)
        # Anchor to the sentence's own first line (m.start() == 0), else the
        # same sentence re-matches in earlier overlapping windows and binds
        # the previous block's plan code.
        if m and m.start() == 0 and \
                m.group(0).lower().startswith(("a candidate", "students")):
            hint = hint_for(i)
            key = (hint, m.group("total"), m.group("cohort")[:40])
            if key in seen_sent:
                continue
            seen_sent.add(key)
            cohort = ""
            cm = re.search(
                r"who (?:first )?register(?:s|ed) (in|before) (\d{4})",
                m.group("cohort"), re.I)
            if cm:
                cohort = f"registered {cm.group(1)} {cm.group(2)}"
            rows.append(_row(year, "EBE", degree_scope=hint or "(umbrella)",
                             plan_code_hint=hint, cohort=cohort,
                             min_total_credits=int(m.group("total")),
                             source_page=page_no, quote=m.group(0)[:300]))
            if m.group("alt"):
                ym = re.search(r"from (\d{4})", m.group(0))
                rows.append(_row(
                    year, "EBE", degree_scope=hint or "(umbrella)",
                    plan_code_hint=hint,
                    cohort=(f"registered in {ym.group(1)}" if ym
                            else "admitted to the new curriculum"),
                    min_total_credits=int(m.group("alt")),
                    source_page=page_no, quote=m.group(0)[:300]))
            continue
        m = EBE_MIN_TRANSFEREE.search(win)
        if m:
            hint = hint_for(i)
            key = (hint, m.group("total"), "transferee")
            if key in seen_sent:
                continue
            seen_sent.add(key)
            rows.append(_row(year, "EBE",
                             degree_scope=(hint or "(umbrella)")
                             + " transferee/access route",
                             plan_code_hint=hint, cohort="",
                             min_total_credits=int(m.group("total")),
                             source_page=page_no, quote=m.group(0)[:300]))
    return rows


# --- LAW -------------------------------------------------------------------

LAW_STREAM_TOTAL = re.compile(
    r"^Total credits for the (?P<stream>[\w\- ]*?LLB[\w\- ]*?stream)"
    r"[\s.…]*(?P<total>\d{3})\s*$")
LAW_DUR = re.compile(
    r"the curriculum for the (?P<stream>[\w\- ]+?(?:curriculum )?stream) of "
    r"the Basic Legal Education programme will extend over (?P<n>\w+) years?"
    r"|the curriculum for the (?P<stream2>five-year undergraduate curriculum "
    r"stream) will extend over (?P<n2>\w+) years?", re.I)
LAW_ELECTIVE_MIN = re.compile(
    r"must choose elective courses totalling a minimum of (?P<n>\d{2}) NQF "
    r"credits", re.I)
LAW_ELECTIVE_MAX = re.compile(
    r"The maximum number of credits for elective courses in the Final Level "
    r"is (?P<n>\d{2})", re.I)

# Order matters: "undergraduate" contains the substring "graduate", and
# "five-year undergraduate" contains both.
LAW_STREAM_CODES = (("five-year", "LB003"), ("undergraduate", "LB002"),
                    ("graduate", "LP001"))


def _law_stream_code(stream: str) -> str:
    s = stream.lower()
    for key, code in LAW_STREAM_CODES:
        if key in s:
            return code
    return ""


def _law_rules(year, dump_path):
    rows, seen = [], set()
    for page_no, lines, page_text in _pages(dump_path):
        for line in lines:
            m = LAW_STREAM_TOTAL.match(line)
            if m:
                stream = _collapse(m.group("stream"))
                code = _law_stream_code(stream)
                if ("total", code, stream) in seen:
                    continue
                seen.add(("total", code, stream))
                rows.append(_row(year, "LAW", degree_scope=f"LLB {stream}",
                                 plan_code_hint=code,
                                 min_total_credits=int(m.group("total")),
                                 is_stream_total=True, source_page=page_no,
                                 quote=_collapse(line)))
        for m in LAW_DUR.finditer(page_text):
            stream = _collapse(m.group("stream") or m.group("stream2"))
            n = _dur_value(m.group("n") or m.group("n2"))
            code = _law_stream_code(stream)
            if ("dur", code, stream) in seen:
                continue
            seen.add(("dur", code, stream))
            rows.append(_row(year, "LAW", degree_scope=f"LLB {stream}",
                             plan_code_hint=code, duration_years=n,
                             rule_ref="FP1-FP3", source_page=page_no,
                             quote=_collapse(m.group(0))))
        for pat, ref, field in ((LAW_ELECTIVE_MIN, "FP4.4", "min_total_credits"),
                                (LAW_ELECTIVE_MAX, "FP4.6", "max_total_credits")):
            m = pat.search(page_text)
            if m and ("fp4", ref) not in seen:
                seen.add(("fp4", ref))
                rows.append(_row(year, "LAW",
                                 degree_scope="LLB Final Level electives",
                                 rule_ref=ref, source_page=page_no,
                                 quote=_collapse(m.group(0)),
                                 **{field: int(m.group("n"))}))
    return rows


# --- FHS -------------------------------------------------------------------

FHS_DUR = re.compile(
    r"(?P<ref>FB[A-Z]\d+(?:\.\d+)?)\s+"
    r"(?:The curriculum for the degree|The degree programme|Each curriculum"
    r"|The programme)\s+extends over\s+(?P<dur>[^.]{3,120})", re.I)
FHS_BSCMED = re.compile(
    r"(?P<ref>FBC3\.1)\s+The BSc \(Medicine\) shall have at least\s+"
    r"(?P<total>\d{3})\s+credits, of which a minimum of\s+(?P<lvlcr>\d{2,3})"
    r"\s+credits(?:\s+must be at (?:NQF|HEQSF) level (?P<lvl>\d))?", re.I)
FHS_PROGRAMME_HINT = re.compile(
    r"^(?:Bachelor of |BSc |MBChB|Intercalated )", re.I)


def _fhs_rules(year, dump_path):
    rows, seen = [], set()
    hint = ""
    for page_no, lines, _page_text in _pages(dump_path):
        for i, line in enumerate(lines):
            if FHS_PROGRAMME_HINT.match(line) and len(line) < 60 \
                    and not re.search(r"\d{3}|shall|required|whilst|extends",
                                      line):
                hint = _collapse(line)
            win = _window(lines, i)
            m = FHS_BSCMED.search(win)
            if m and ("bscmed",) not in seen:
                seen.add(("bscmed",))
                rows.append(_row(year, "FHS",
                                 degree_scope="Intercalated BSc (Medicine)",
                                 rule_ref=m.group("ref"),
                                 min_total_credits=int(m.group("total")),
                                 min_level_credits=int(m.group("lvlcr")),
                                 min_level=int(m.group("lvl") or 0) or "",
                                 source_page=page_no, quote=m.group(0)))
                continue
            m = FHS_DUR.match(_window(lines, i, 2))
            if m:
                dur_text = _collapse(m.group("dur"))
                key = (m.group("ref"), dur_text[:40])
                if key in seen:
                    continue
                seen.add(key)
                # FBA9.x are the Fundamentals-programme (intervention) rules;
                # the nearest heading is unrelated to their scope.
                scope = ("MBChB (Fundamentals of Health Sciences route)"
                         if m.group("ref").startswith("FBA9") else hint)
                dm = re.search(
                    r"(?:either )?(\w+)(?: or .*?(\w+))? (?:academic )?year",
                    dur_text, re.I)
                dur = _dur_value(" ".join(g for g in dm.groups() if g)) \
                    if dm else ""
                rows.append(_row(year, "FHS", degree_scope=scope,
                                 rule_ref=m.group("ref"), duration_years=dur,
                                 source_page=page_no,
                                 quote=_collapse(m.group(0))[:300]))
    return rows


# --- dispatch --------------------------------------------------------------

_PARSERS = {"COM": _com_rules, "EBE": _ebe_rules, "LAW": _law_rules,
            "FHS": _fhs_rules}


def extract_degree_rules(faculty: str, year: int, dump_path: Path) -> list[dict]:
    parser = _PARSERS.get(faculty)
    return parser(year, dump_path) if parser else []
