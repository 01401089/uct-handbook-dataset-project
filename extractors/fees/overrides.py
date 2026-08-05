"""Explicit, reviewable corrections applied after parsing the fees book.

Never hand-edit data/processed outputs — record the correction here with the
reason, keyed by handbook year, and re-run the extractor.
"""

# Rows the parser cannot recover from the PDF text layer.
COURSE_FEE_ADDITIONS = {
    2025: [
        # p.82 of 2025-_fees.pdf: two printed rows overlap in the PDF text
        # layer and extract as one character-interleaved line
        # ("CCMMLL44450013HF ICNODPEYPREINGDHETN ..."). De-interleaving the
        # even/odd character streams recovers both rows; fee 4,960 each.
        {"course_code": "CML4401H", "fees_title": "INDEPENDENT RESEARCH OPTION",
         "fee_zar": 4960, "standard_code": True, "source_page": 82},
        {"course_code": "CML4503F", "fees_title": "COPYRIGHT & PATENTS",
         "fee_zar": 4960, "standard_code": True, "source_page": 82},
    ],
}
