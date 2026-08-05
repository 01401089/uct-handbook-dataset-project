"""Fees handbook extractor.

Reads faculty-handbooks-undergraduate/{year}-_fees.pdf and writes:

- data/processed/course_fees.csv            (fees book section 12, one row per course code)
- data/processed/programme_fees_published.csv (fees book section 11, one row per
                                             programme label x year-of-study)
- validation/fees_unparsed_{year}.csv       (lines inside the fee sections that
                                             did not match any known pattern)

Run from the repo root:
    python -m extractors.fees.extract --year 2025 [--skip-dump]
"""
import argparse
import csv
import re
from pathlib import Path

from common.csv_io import write_year_rows
from common.pdf_text import dump_pages, iter_pages
from extractors.fees.overrides import COURSE_FEE_ADDITIONS

ROOT = Path(__file__).resolve().parents[2]

# --- Section 12 (course fee table) -----------------------------------------

# Permissive course-code shape; standard shape is 3 letters + 4 digits + suffix,
# but the fees book contains some variants. Non-standard shapes get flagged.
FEE_ROW = re.compile(r"^([A-Z]{2,4}\d{3,4}[A-Z]{0,2})\s+(.+?)\s+([\d,]+)$")
STANDARD_CODE = re.compile(r"^[A-Z]{3}\d{4}[A-Z]$")

SEC12_HEADER = re.compile(
    r"^(?:\d+\s+UCT ACADEMIC COURSES|UCT ACADEMIC COURSES\s+\d+"
    r"|COURSE CODE DESCRIPTION TUITION FEE)$"
)

# --- Section 11 (published programme fees) ---------------------------------

FACULTY_HEADING = re.compile(r"^11\.\d+\s+(?:FACULTY OF\s+)?(.+?)\s*$")
# "1st Year…………R 91 190" possibly with margin-note text before/after.
YEAR_FEE = re.compile(
    r"(?P<pre>.*?)(?P<year>\d)(?:st|nd|rd|th)\s+Year[\s.…]*"
    r"R?\s*(?P<amount>\d{1,3}(?:[\s ]?\d{3})*)(?P<post>.*)$"
)
DOTTED_FEE = re.compile(  # "Undergraduate LLB ......... R 76 810"
    r"^(?P<label>[^.…]{4,}?)[\s.…]{3,}R\s*(?P<amount>\d{1,3}(?:[\s ]?\d{3})*)\s*$"
)


def parse_rand(text: str) -> int:
    return int(re.sub(r"[\s ]", "", text))


def find_section_pages(dump_path: Path) -> dict:
    """Return {section: (first_page, last_page)} for fee sections 11 and 12."""
    s11 = s12 = s13 = None
    for page_no, text in iter_pages(dump_path):
        # Full-line matches only, so the dotted TOC entries don't trigger.
        if s11 is None and re.search(r"^11\. UCT ACADEMIC FEES\s*$", text, re.M):
            s11 = page_no
        if s12 is None and re.search(r"^12\. UCT ACADEMIC COURSES\s*$", text, re.M):
            s12 = page_no
        if s13 is None and re.search(r"^13\. RESIDENCES\s*$", text, re.M):
            s13 = page_no
    if not all([s11, s12, s13]):
        raise SystemExit(f"Could not locate section boundaries: 11={s11} 12={s12} 13={s13}")
    return {"11": (s11, s12 - 1), "12": (s12, s13 - 1)}


def parse_section12(dump_path: Path, pages: tuple, year: int):
    rows, unparsed = [], []
    first, last = pages
    started = False
    for page_no, text in iter_pages(dump_path):
        if page_no < first or page_no > last:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or SEC12_HEADER.match(line):
                continue
            if not started:
                # Skip the section preamble until the column header has passed.
                if line == "COURSE CODE DESCRIPTION TUITION FEE" or FEE_ROW.match(line):
                    started = True
                else:
                    continue
            m = FEE_ROW.match(line)
            if m:
                code, title, fee = m.groups()
                rows.append({
                    "year": year,
                    "course_code": code,
                    "fees_title": title.strip(),
                    "fee_zar": int(fee.replace(",", "")),
                    "standard_code": bool(STANDARD_CODE.match(code)),
                    "source_page": page_no,
                })
            else:
                unparsed.append({"year": year, "section": "12",
                                 "source_page": page_no, "line": line})
    return rows, unparsed


DEGREE_KEYWORD = re.compile(
    r"\b(Bachelor|BCom|BBusSc|BSc|BAS|BA\b|LLB|MBChB|BSocSc|BMus|BSW|Diploma)"
)


def parse_section11(dump_path: Path, pages: tuple, year: int):
    """State machine over the per-programme fee blocks of section 11.

    The printed layout interleaves margin notes with the fee rows, so labels
    cannot be taken from simple adjacency. Rules that hold across the section:

    - Subsection 11.1 (typical fee *ranges*) is skipped; parsing starts at the
      first faculty heading ("11.2 FACULTY OF ...").
    - Text lines accumulate in a buffer. The buffer becomes the block label
      only when a "1st Year" fee row arrives; on later-year rows any buffered
      text is margin noise and is recorded as margin_note instead.
    - Stream sub-labels without a degree keyword (e.g. "Chartered Accounting
      Stream") inherit the last degree-bearing label as context.
    - Dotted single-line fees without a year prefix keep study_year empty.
    """
    rows, unparsed = [], []
    first, last = pages
    faculty = ""
    label_buf: list[str] = []
    active_label = ""
    degree_context = ""
    last_dotted_label = ""

    for page_no, text in iter_pages(dump_path):
        if page_no < first or page_no > last:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or re.match(r"^(?:UCT ACADEMIC FEES\s+\d+|\d+\s+UCT ACADEMIC FEES)$", line):
                continue
            fh = FACULTY_HEADING.match(line)
            if fh:
                faculty = fh.group(1).title()
                label_buf, active_label, degree_context = [], "", ""
                last_dotted_label = ""
                continue
            if not faculty or faculty.startswith("Typical"):
                continue  # still in 11.1 or preamble

            m = YEAR_FEE.search(line)
            if m:
                study_year = int(m.group("year"))
                note = (m.group("pre") + " " + m.group("post")).strip(" .…")
                if study_year == 1 and not label_buf and last_dotted_label:
                    # Year rows directly after a dotted single-line fee belong
                    # to that programme (e.g. PG blocks listing "Full Time"
                    # then part-time per-year fees).
                    active_label = last_dotted_label
                elif study_year == 1 and label_buf:
                    last_dotted_label = ""
                    new_label = re.sub(r"^Degrees\s+", "", " ".join(label_buf).strip())
                    if DEGREE_KEYWORD.search(new_label):
                        # Context for stream sub-blocks = label minus its own
                        # trailing "<...> Stream" clause (max 4 words).
                        degree_context = re.sub(
                            r"\s+(?:[\w&:,()-]+\s+){0,3}Stream$", "", new_label)
                        active_label = new_label
                    else:
                        active_label = (degree_context + " | " + new_label).strip(" |")
                elif label_buf:
                    note = (" ".join(label_buf) + " " + note).strip()
                label_buf = []
                rows.append({
                    "year": year,
                    "faculty_section": faculty,
                    "programme_label": active_label,
                    "study_year": study_year,
                    "fee_zar": parse_rand(m.group("amount")),
                    "margin_note": note,
                    "source_page": page_no,
                })
                continue

            d = DOTTED_FEE.match(line)
            if d:
                label = d.group("label").strip()
                if label_buf:
                    label = (" ".join(label_buf) + " " + label).strip()
                    label_buf = []
                last_dotted_label = label
                rows.append({
                    "year": year,
                    "faculty_section": faculty,
                    "programme_label": label,
                    "study_year": "",
                    "fee_zar": parse_rand(d.group("amount")),
                    "margin_note": "",
                    "source_page": page_no,
                })
                continue

            label_buf.append(line)
    return rows, unparsed


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--skip-dump", action="store_true",
                    help="reuse the existing interim page dump")
    args = ap.parse_args()

    pdf = ROOT / "faculty-handbooks-undergraduate" / f"{args.year}-_fees.pdf"
    dump = ROOT / "data" / "interim" / f"{args.year}-fees.txt"
    if not args.skip_dump or not dump.exists():
        n = dump_pages(pdf, dump)
        print(f"dumped {n} pages -> {dump.relative_to(ROOT)}")

    sections = find_section_pages(dump)
    print(f"section 11 pages {sections['11']}, section 12 pages {sections['12']}")

    fees, unparsed12 = parse_section12(dump, sections["12"], args.year)
    prog, unparsed11 = parse_section11(dump, sections["11"], args.year)

    for extra in COURSE_FEE_ADDITIONS.get(args.year, []):
        fees.append({"year": args.year, **extra})

    # Exact duplicate rows occur in the printed table; keep one, count them.
    seen, deduped, dupes = set(), [], 0
    for r in fees:
        key = (r["course_code"], r["fees_title"], r["fee_zar"])
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        deduped.append(r)

    write_year_rows(ROOT / "data" / "processed" / "course_fees.csv", deduped, args.year)
    write_year_rows(ROOT / "data" / "processed" / "programme_fees_published.csv",
                    prog, args.year)
    write_csv(ROOT / "validation" / f"fees_unparsed_{args.year}.csv",
              unparsed12 + unparsed11)

    nonstd = sum(1 for r in deduped if not r["standard_code"])
    print(f"course_fees: {len(deduped)} rows ({dupes} exact duplicates dropped, "
          f"{nonstd} non-standard codes)")
    print(f"programme_fees_published: {len(prog)} rows")
    print(f"unparsed lines: {len(unparsed12)} in sec 12, {len(unparsed11)} in sec 11")


if __name__ == "__main__":
    main()
