"""
Page references, measured rather than asserted.

The generator knows which page it drew a value on, so it could simply write
that down. It should not. A page reference the generator asserts is a claim
about its own intentions; one read back out of the finished PDF is a claim
about the document, and only the second kind catches the case where the
layout moved and the gold did not.

So: render first, then search each page's text for each value.

The search is token-bounded on purpose. A bare substring test finds the state
``NY`` inside ``Company`` and the language code ``en`` inside ``Residence``.
Both resolve to a page, neither means anything, and a page reference that is
accidentally right is worse than one that is missing - nobody can spot it.
"""

from __future__ import annotations

import re

from .fields import NO_EVIDENCE, is_field, walk_indexed


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def on_page(needle, page_text):
    """Is ``needle`` present as a whole token, not inside a longer word?"""
    if not needle:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])",
                     page_text) is not None


def page_texts(pdf_path):
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(str(pdf_path))
    texts = [_norm(page.get_text()) for page in doc]
    doc.close()
    return texts


def column_texts(pdf_path):
    """Per page, the text of each column read down it: lines that start at
    the same place, top to bottom. A value wrapped onto the next line of its
    column ("Thornfield INSURANCE GROUP" | "BROKERAGE INC") is whole here,
    where the page's own text order can put the other column in between."""
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(str(pdf_path))
    out = []
    for page in doc:
        pieces = sorted(((list(l["bbox"]), " ".join(s["text"] for s in l["spans"]))
                         for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])),
                        key=lambda bt: (round(bt[0][1]), bt[0][0]))
        lines = []                       # pieces printed apart along one row
        for box, text in pieces:
            last = lines[-1] if lines else None
            # words set wide apart still make one line: "BROKERAGE    INC"
            # (up to three and a half line heights, as a justified print spaces them)
            if last and abs(last[0][1] - box[1]) <= 2 and \
                    0 <= box[0] - last[0][2] < max(25, 3.5 * (box[3] - box[1])):
                last[0][2], last[1] = box[2], last[1] + " " + text
            else:
                lines.append([box, text])
        columns = []
        for box, text in lines:
            col = next((c for c in columns if abs(c[0] - box[0]) <= 3), None)
            if col is None:
                columns.append([box[0], [text]])
            else:
                col[1].append(text)
        out.append(" | ".join(_norm(" ".join(c[1])) for c in columns))
    doc.close()
    return out


def attach(doc, pdf_path):
    """Fill every ``page_ref`` from the rendered PDF.

    Returns ``(resolved, misses)`` where ``misses`` lists the dotted paths of
    values that claim to be on the page and are not. A miss is a bug report,
    not a rounding error: it means the gold file and the document disagree,
    and one of them is wrong.

    Values marked :data:`~fideon_synth.fields.NO_EVIDENCE` - a source
    filename, say - get an empty list and are not counted as misses, because
    they never claimed to be printed anywhere.
    """
    texts = page_texts(pdf_path)
    columns = None
    resolved, misses = 0, []

    for path, field in walk_indexed(doc):
        evidence = field.pop("_evidence", field["raw"])
        if evidence is NO_EVIDENCE:
            field["page_ref"] = []
            continue
        needle = _norm(str(evidence)) if evidence is not None else ""
        field["page_ref"] = [i + 1 for i, text in enumerate(texts)
                             if on_page(needle, text)]
        squeezed = re.sub(r"\s+", "", needle)
        if not field["page_ref"] and len(squeezed) >= 8:
            # an OCR layer spaces words its own way ("Liabilit Tyo"); the
            # same characters in the same order are the same printed text
            field["page_ref"] = [i + 1 for i, text in enumerate(texts)
                                 if squeezed in re.sub(r"\s+", "", text)]
        if not field["page_ref"] and " " in needle:
            # wrapped onto the next line of its column
            columns = columns if columns is not None else column_texts(pdf_path)
            field["page_ref"] = [i + 1 for i, text in enumerate(columns) if on_page(needle, text)]
        if field["page_ref"]:
            resolved += 1
        elif evidence is not None:
            misses.append((path, field["raw"]))
    return resolved, misses


def carry_over(doc, source_name):
    """Keep page references that were measured on a different rendering.

    A scanned page has no text to search, so its references come from the
    text-layer twin whose layout is identical by construction. Strips the
    private evidence keys and records where the numbers came from, so a
    reader is not left to assume they were read off the image.
    """
    for _, field in walk_indexed(doc):
        field.pop("_evidence", None)
    doc.setdefault("fideon:provenance", {})["page_refs_measured_on"] = \
        source_name
    return doc


def stated_paths(doc):
    """Dotted paths, list indices collapsed, of every leaf this gold asserts."""
    from .fields import walk
    return {path for path, _ in walk(doc)}
