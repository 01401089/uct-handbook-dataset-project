"""Explicit, reviewable corrections applied after parsing the fees book.

Never hand-edit data/processed outputs — record the correction here with the
reason, keyed by handbook year, and re-run the extractor.
"""

# Rows the parser cannot recover from the PDF text layer.
COURSE_FEE_ADDITIONS = {
    2024: [
        # p.79 of 2024-_fees.pdf: two printed rows overlap in the PDF text
        # layer and extract as one character-interleaved line
        # ("CCSSCC33000023FS CCOOMMPPUUTTEERR SSCCIIEENNCCEE 33000023
        # 1199,003300"). De-interleaving the even/odd character streams
        # recovers both rows; fee 19,030 each.
        {"course_code": "CSC3002F", "fees_title": "COMPUTER SCIENCE 3002",
         "fee_zar": 19030, "standard_code": True, "source_page": 79},
        {"course_code": "CSC3003S", "fees_title": "COMPUTER SCIENCE 3003",
         "fee_zar": 19030, "standard_code": True, "source_page": 79},
    ],
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
