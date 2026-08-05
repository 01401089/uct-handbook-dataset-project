"""Per-page text extraction shared by all faculty extractors.

Interim dumps carry ``===== PAGE n / total =====`` markers so that every parsed
value can keep a ``source_page`` provenance column.
"""
from pathlib import Path

import pdfplumber

PAGE_MARKER = "===== PAGE {page} / {total} ====="


def dump_pages(pdf_path: str | Path, out_path: str | Path) -> int:
    """Write one text file with page markers for *pdf_path*; return page count."""
    pdf_path, out_path = Path(pdf_path), Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        with open(out_path, "w", encoding="utf-8") as f:
            for i, page in enumerate(pdf.pages, start=1):
                f.write("\n" + PAGE_MARKER.format(page=i, total=total) + "\n")
                f.write(page.extract_text() or "")
    return total


def iter_pages(dump_path: str | Path):
    """Yield ``(page_number, text)`` tuples from a dump produced by dump_pages."""
    current_page, buf = None, []
    with open(dump_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("===== PAGE "):
                if current_page is not None:
                    yield current_page, "".join(buf)
                current_page = int(line.split()[2])
                buf = []
            else:
                buf.append(line)
    if current_page is not None:
        yield current_page, "".join(buf)
