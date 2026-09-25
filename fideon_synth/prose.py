"""
Printed prose, carried into the gold as text sections.

Keyed fields hold the values a page prints; the paragraphs around them - a
deductible condition, a navigation restriction, a renewal notice, a
disclaimer - have no field, yet they are printed and an extractor reads
them. Each paragraph becomes a ``TextSection`` (see the canonical schema),
titled by the heading printed over it.

Read from the finished document, so the words are the replaced ones. A page
with a real text layer is read from it, where bold type tells a heading from
a paragraph; a scanned page is read by OCR from its image, because a scan's
own text layer is often garbled ("Nicdical cack") and prose copied from it
would claim words the page does not show. Without an OCR engine a scanned
page contributes no sections, rather than wrong ones.
"""

from __future__ import annotations

import re

import fitz

from . import overlay, recover

_FORM_NO = re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,6}[- ]?\d{1,5}[A-Z]?(?: [A-Z]{2})?\s?\(\d{1,2}[-/]\d{2,4}\)")
WHITE = 0xFFFFFF
OCR_DPI = 300
#: a form or product code: "MAM5192-0417", "PL-50776"
_CODE = re.compile(r"\b[A-Z]{2,}-?\d{3,}")


#: a bullet printed before a list item; a font's symbol bullet often
#: arrives as U+F0B7 or as the replacement character
_BULLET = set("•●▪◦·�*-")
#: "Watercraft and Auxiliary Equipment Value: $196,245" - a label and its value
_LABEL_ROW = re.compile(r"^[^:]{2,60}:\s*(.*)$")


class Line:
    def __init__(self, centre, height, x0, text, gap, bold, cells):
        self.centre, self.height, self.x0 = centre, height, x0
        self.text, self.gap, self.bold = text, gap, bold
        self.cells = cells                   # [(x0, text)] split at column gaps

    @property
    def words(self):
        return len(self.text.split())

    def prose(self):
        ink = self.text.replace(" ", "")
        label = _LABEL_ROW.match(self.text)
        text = self.text.strip()
        # a short sentence is prose too: "Enclosed are your policy documents."
        sentence = self.words >= 4 and re.match(r"[A-Z*\"'(]", text) and re.search(r"[.!?]$", text) \
            and re.search(r"[a-z]{3}", text)
        if self.text.count(":") >= 2:
            return False                                     # "Year: 2026 Make: Yamaha ..." is a row
        if re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?$", text):
            return False                                     # "... Hartford, CT 06183" is an address
        return ((self.words >= 6 or sentence) and not self.gap
                and not (self.bold and self.words < 10)      # a bold heading, not a bold paragraph
                and not (label and len(label.group(1).split()) <= 4)
                and len(_CODE.findall(self.text)) < 2        # a list of forms is not prose
                and not _CODE.match(self.text)               # nor one line of it
                and sum(c.isalpha() for c in ink) > 0.6 * len(ink))

    def heading(self):
        """A title over a paragraph: short bold type where the type is
        known, else a short line with no figures that is not a sentence."""
        if self.gap or self.words > 12 or not re.search(r"[A-Za-z]{3}", self.text):
            return False
        if self.bold is not None:
            return self.bold and self.words < 10
        return not re.search(r"\d", self.text) and not self.text.rstrip().endswith(".")

    def items(self):
        """The list items on this line - "• Pay a bill    • Update your
        policy" - or None when it is not a line of a bulleted list."""
        out, k = [], 0
        while k < len(self.cells):
            text = self.cells[k][1].strip()
            if text in _BULLET and k + 1 < len(self.cells):
                out.append(self.cells[k + 1][1].strip())
                k += 2
            elif len(text) > 2 and text[0] in _BULLET and text[1] == " ":
                out.append(text[2:].strip())
                k += 1
            else:
                return None
        return out or None


def _rows(pieces, column=0.9, tight=True):
    """(top, bottom, x0, x1, text, bold) pieces -> visual lines, top to bottom.
    A space wider than ``column`` line heights separates columns - unless the
    line is justified, its words all set that far apart; with ``tight``,
    pieces set against each other are joined without a space."""
    pieces = sorted(pieces, key=lambda p: ((p[0] + p[1]) / 2, p[2]))
    rows, current = [], []
    for p in pieces:
        centre, height = (p[0] + p[1]) / 2, max(p[1] - p[0], 4.0)
        if current and abs(centre - current[-1][0]) > 0.55 * height:
            rows.append(current)
            current = []
        current.append((centre, height, p))
    if current:
        rows.append(current)
    out = []
    for row in rows:
        row.sort(key=lambda r: r[2][2])
        spaces = [cur[2] - prev[3] for (_, _, prev), (_, _, cur) in zip(row, row[1:])]
        # a line's usual space is its lower quartile: a table row's own
        # column gaps must not pass for its ordinary spacing
        usual = sorted(spaces)[len(spaces) // 4] if len(spaces) >= 3 else 0.0
        parts, gap = [row[0][2][4]], False
        cells = [[row[0][2][2], row[0][2][4]]]
        for space, (_, height, prev), (_, _, cur) in zip(spaces, row, row[1:]):
            wide = space > column * height and space > 2.5 * usual
            gap = gap or wide
            glued = tight and space <= 0.12 * height
            parts.append(("  " if wide else "" if glued else " ") + cur[4])
            if wide:
                cells.append([cur[2], cur[4]])
            else:
                cells[-1][1] += ("" if glued else " ") + cur[4]
        flags = [r[2][5] for r in row]
        bold = None if None in flags else all(flags)
        out.append(Line(row[0][0], row[0][1], row[0][2][2], "".join(parts), gap, bold,
                        [tuple(c) for c in cells]))
    return out


def _layer_lines(page):
    """Lines of a page's visible text layer; white text (hidden print codes) left out."""
    # the words and their spacing come from the word list; a span only says
    # whether its type is bold or white - spans often carry no spaces at all
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                font = span.get("font", "").lower()
                bold = bool(span.get("flags", 0) & 16) or any(
                    w in font for w in ("bold", "black", "heavy", "semibold"))
                spans.append((fitz.Rect(span["bbox"]), bold, span.get("color") == WHITE))
    pieces = []
    for w in page.get_text("words"):
        if not str(w[4]).strip():
            continue
        r = fitz.Rect(w[:4])
        mid = fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        bold, white = next(((b, h) for s, b, h in spans if s.contains(mid)), (False, False))
        if not white:
            pieces.append((r.y0, r.y1, r.x0, r.x1, w[4], bold))
    return _rows(pieces, tight=False)


def _repair(text, values):
    """A value the generator drew, as OCR read it with its spaces dropped
    ("February25,2026"), printed as it was drawn. Only exact characters are
    restored; a misread letter is left as read."""
    for v in sorted(values, key=len, reverse=True):
        if len(v) >= 6 and " " in v:
            rx = r"\s*".join(re.escape(c) for c in v.replace(" ", ""))
            text = re.sub(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % rx, lambda m: v, text)
    return text


def _ocr_lines(page):
    # read finer than for layout: small print loses its spaces at 200 dpi
    # ("insurancepolicy.Pleasereferto"); and the engine splits a line at the
    # double space after a full stop, so only a wide space is a column
    return _rows([(r.y0, r.y1, r.x0, r.x1, text.strip(), None)
                  for text, r, _ in recover.read_page(page, dpi=OCR_DPI)], column=2.5)


def _section(out, n, title, text, kind="prose"):
    text = re.sub(r"\s+", " ", text).strip()
    form = _FORM_NO.search(text)
    sid = "page%d_s%d" % (n, len(out) + 1)
    out[sid] = {"section_id": sid, "section_title": title, "section_type": kind,
                "raw_text": text, "page_range": [n],
                "form_number": form.group(0) if form else None}


def _title_over(lines, i):
    above = lines[i - 1] if i > 0 else None
    if above is None or not above.heading() \
            or lines[i].centre - above.centre > 2.4 * above.height:
        return None
    # a heading set on two lines: "On-Water Towing and Assistance with No"
    # over "Out-of-Pocket Expenses1."
    title, k = [above.text], i - 2
    while k >= 0 and len(title) < 3 and lines[k].heading() and lines[k].bold == above.bold \
            and not re.search(r"[.!?:]$", lines[k].text.rstrip()) \
            and lines[k + 1].centre - lines[k].centre <= 1.6 * lines[k].height:
        title.insert(0, lines[k].text)
        k -= 1
    return re.sub(r"\s+", " ", " ".join(title)).strip()


def _sections(lines, n):
    out = {}
    # where the type is unknown (a scan read by OCR), a heading is told by the
    # paragraph set indented under it: "Deductibles" over "All physical ..."
    for a, b in zip(lines, lines[1:]):
        if a.bold is None and b.x0 - a.x0 > 1.5 * a.height and a.words <= 12 \
                and not re.search(r"[.,;:]$", a.text.rstrip()) \
                and b.centre - a.centre <= 2.4 * a.height:
            a.bold = True
    i = 0
    while i < len(lines):
        items = lines[i].items()
        if items:
            # a bulleted list, however many columns it is set in, is one section
            j = i
            while j + 1 < len(lines) and lines[j + 1].items() \
                    and lines[j + 1].centre - lines[j].centre <= 2.2 * lines[j].height:
                j += 1
                items += lines[j].items()
            above = lines[i - 1] if i > 0 else None
            title = None
            if above is not None and above.text.rstrip().endswith(":") \
                    and lines[i].centre - above.centre <= 2.4 * above.height:
                title = re.sub(r"\s+", " ", above.text).strip()
            _section(out, n, title, "; ".join(items), "other")
            i = j + 1
            continue
        if not lines[i].prose():
            i += 1
            continue
        parts, j = [lines[i].text], i
        while j + 1 < len(lines):
            nxt, cur = lines[j + 1], lines[j]
            ends = re.search(r"[.!?:]$", cur.text.rstrip())
            # a line that carries on an unfinished sentence is the paragraph's,
            # bold or not: "... Policy Coverages, Forms and" | "Endorsements ..."
            if nxt.centre - cur.centre > 1.8 * cur.height or nxt.items() \
                    or (nxt.heading() and ends):
                break
            if nxt.gap:
                # another column beside the paragraph's next line: "Make check"
                # | "payable to Progressive ...  Pay initial installment: $71.00"
                if not ends and abs(nxt.cells[0][0] - lines[i].x0) < 3:
                    parts.append(nxt.cells[0][1])
                    j += 1
                break
            # a paragraph's last line can be a word or two: "deductible." - but
            # not an address set under a name line ("..., Hartford, CT 06183")
            if not nxt.prose() and (ends or re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?$",
                                                      nxt.text.strip())):
                break
            parts.append(nxt.text)
            j += 1
            if not nxt.prose():
                break
        _section(out, n, _title_over(lines, i), " ".join(parts))
        i = j + 1
    return out


def text_sections(pdf_path, values=()):
    """Every paragraph of printed prose in the PDF, as gold text sections.
    ``values`` are the replacements drawn on it, restored where OCR ran
    their words together."""
    doc = fitz.open(str(pdf_path))
    sections = {}
    try:
        for page in doc:
            scanned = recover.is_scanned(page, overlay.invisible_text(page))
            if scanned:
                if recover.engine() is None:
                    continue
                lines = _ocr_lines(page)
            else:
                lines = _layer_lines(page)
            found = _sections(lines, page.number + 1)
            if scanned:
                for s in found.values():
                    s["raw_text"] = _repair(s["raw_text"], values)
            sections.update(found)
    finally:
        doc.close()
    return sections
