"""
Text a scan's own OCR layer left out, read back from the page image.

A scanned source carries an invisible OCR text layer, and everything
downstream reads that layer. When the scanner's OCR skipped something - a
form number, a date stamp, a whole page - that text does not exist for the
generator: it is neither replaced nor put in the gold, though every reader of
the page can see it. A pure image scan with no text layer at all has nothing
to read.

So each scanned page is read again with an OCR engine and reconciled with
the layer it already has:

* **missing** - printed text where the layer has no characters is added, as
  characters positioned across the OCR line's box;
* **garbled** - where the layer holds characters but the engine reads a
  clean value (a date, an amount, a phone number, an e-mail, a FEIN) that
  the layer's text there does not form, the engine's reading replaces them:
  "112912026" under a printed "7/29/2026".

What is added is written back into the page as invisible text before the
gold is checked, so a value read this way is verified against the page like
any other. The engine is optional: without it pages are read as before.
"""

from __future__ import annotations

import difflib
import os
import re
from typing import List, Optional, Tuple

import fitz
import numpy as np

DPI = 200
MIN_CONFIDENCE = 0.85
_engine = None
_tried = False


def engine():
    """The OCR engine, loaded once; None when it is not installed or
    FIDEON_NO_OCR is set."""
    global _engine, _tried
    if not _tried:
        _tried = True
        if not os.environ.get("FIDEON_NO_OCR"):
            try:
                from rapidocr_onnxruntime import RapidOCR
                _engine = RapidOCR()
            except Exception:                    # not installed, or no model
                _engine = None
    return _engine


def is_scanned(page, invisible) -> bool:
    """A page whose text is an invisible OCR layer, or that has no text at
    all but an image covering most of it."""
    if invisible:
        return True
    if page.get_text("text").strip():
        return False
    area = page.rect.width * page.rect.height
    return any(fitz.Rect(i["bbox"]).get_area() > 0.5 * area for i in page.get_image_info())


def read_page(page, dpi=DPI, min_conf=None) -> List[Tuple[str, fitz.Rect, float]]:
    """(text, rect in page points, confidence) for every line the engine reads
    at ``min_conf`` or better (default :data:`MIN_CONFIDENCE`)."""
    ocr = engine()
    if ocr is None:
        return []
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    result, _ = ocr(np.ascontiguousarray(img))
    scale = 72.0 / dpi
    lines = []
    for box, text, conf in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        rect = fitz.Rect(min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale)
        if conf >= (MIN_CONFIDENCE if min_conf is None else min_conf) and text.strip():
            if len(text.split()) <= 5:
                # the engine reads a registered mark after a name as "?":
                # "Sign & Glide?", "Propulsion Plus?"
                text = re.sub(r"(?<=[A-Za-z])\?(?=\s|$)", "®", text)
            lines.append((text, rect, float(conf)))
    return lines


def _chars_of(text, rect):
    """The line's characters spread across its box in proportion - the
    engine gives a box per line, not per glyph."""
    n = max(len(text), 1)
    step = rect.width / n
    return [(c, fitz.Rect(rect.x0 + k * step, rect.y0, rect.x0 + (k + 1) * step, rect.y1))
            for k, c in enumerate(text)]


def _covered(box, layer):
    """Is this position already held by a character of the text layer?"""
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    for b in layer:
        if b.x0 - 0.6 * box.width <= cx <= b.x1 + 0.6 * box.width and b.y0 <= cy <= b.y1:
            return True
    return False


def _clean_value(text):
    """Is this a whole value of a kind the generator replaces?"""
    from .generic import PATTERNS
    for kind, rx in PATTERNS:
        if kind in ("date", "money", "phone", "email", "fein") and rx.fullmatch(text):
            return True
    return False


def _trim(run):
    """A run's text and box without the edge characters that belong to the
    neighbouring word: the line's characters are placed in proportion, so a
    run can take a letter of the word it runs into ("MAM5011-0410-D")."""
    text = "".join(c for c, _ in run)
    head = re.match(r"^[A-Za-z]{1,2}(?=[-\s])", text)
    tail = re.search(r"(?<=[-\s])[A-Za-z]{1,2}$", text)
    a = head.end() if head else 0
    b = tail.start() if tail else len(text)
    while a < b and text[a] in " -:;,.":
        a += 1
    while b > a and text[b - 1] in " -:;,.":
        b -= 1
    if a >= b:
        return "", None
    span = fitz.Rect(run[a][1])
    for _, box in run[a:b]:
        span |= box
    return text[a:b], span


def _key(text):
    """Letters and digits only, lower case, with where each came from."""
    keep = [(k, c.lower()) for k, c in enumerate(text) if c.isalnum()]
    return "".join(c for _, c in keep), [k for k, _ in keep]


def reconcile(lines, layer_line, layer_near):
    """What to add and what to drop.

    Returns ``(added, dropped)``: ``added`` is ``[(text, rect)]`` runs of
    printed text the layer lacks or garbled, in page points; ``dropped`` is
    the rects whose layer characters the engine's reading replaces.
    ``layer_line(rect)`` gives the layer's text printed across a line's box;
    ``layer_near(rect)`` gives ``(text, rect)`` of the layer's whole words
    around a rect.

    What the layer lacks is found by comparing text, not positions: a scan's
    layer is often set narrower than the print, so a printed word can lie
    outside every layer box and still be in the layer."""
    added, dropped = [], []
    for text, rect, conf in lines:
        # a figure standing alone in a column - a premium "3", "81" - read
        # surely where the layer has nothing, or a different figure ("5", "EE")
        figure = text.strip()
        if conf >= 0.95 and re.fullmatch(r"\$?\d[\d,]*(?:\.\d\d)?", figure):
            under, whole = layer_near(rect)
            under = under.strip()
            if under == figure:
                continue
            if under and len(re.sub(r"\s", "", under)) > len(figure) + 3:
                continue                          # the layer's word there is something longer
            if under:
                dropped.append(whole)
            added.append((figure, rect))
            continue
        chars = _chars_of(text, rect)
        mine, where = _key(text)
        theirs, _ = _key(layer_line(rect))
        if mine and mine not in theirs:
            match = difflib.SequenceMatcher(None, theirs, mine, autojunk=False)
            held = sum(b.size for b in match.get_matching_blocks()) / len(mine)
            if held < 0.6 and len(mine) >= 6:
                # the layer's text for this line is garbled past repair
                # ("Nicdical cack" for "Medical Payments"): the engine's
                # reading of the whole line stands in for it
                dropped.append(fitz.Rect(rect.x0 - 1, rect.y0, rect.x1 + 1, rect.y1))
                added.append((text, rect))
                continue
            for tag, i1, i2, j1, j2 in match.get_opcodes():
                if tag != "insert" or j2 - j1 < 3:
                    continue                      # only what the layer has no text for
                a, b = where[j1], where[j2 - 1] + 1
                # widen to the whole printed token around it
                while a > 0 and not text[a - 1].isspace():
                    a -= 1
                while b < len(text) and not text[b].isspace():
                    b += 1
                piece, span = _trim(chars[a:b])
                if span is None:
                    continue
                # keep only the part the layer lacks: "MAM5011-0410" of
                # "MAM5011-0410-Diminishing", not the word it runs into
                missing = text[where[j1]:where[j2 - 1] + 1]
                core = re.search(re.escape(missing) + r"[\d/.,$]*", piece)
                if core:
                    k = piece.index(core.group(0))
                    lo = a + (text[a:b].index(piece) if piece in text[a:b] else 0) + k
                    piece, span = _trim(chars[lo:lo + len(core.group(0))])
                if span is not None and len(re.sub(r"[^A-Za-z0-9]", "", piece)) >= 3:
                    added.append((piece, span))
        # a clean value where the layer's characters say something else
        for m in re.finditer(r"\S+", text):
            token = m.group(0).strip(",;")
            if not _clean_value(token):
                continue
            span = fitz.Rect(chars[m.start()][1])
            for _, b in chars[m.start():m.end()]:
                span |= b
            under, whole = layer_near(span)
            digits = re.sub(r"\D", "", token)
            if not under or _clean_value(under.strip(",;")) or digits in re.sub(r"\D", "", under):
                continue                          # the layer has it, or has nothing here
            dropped.append(whole)
            added.append((token, whole))
    return added, dropped


def write_back(page, runs, skip):
    """Put recovered text into the page's text layer, invisibly, where it
    is printed - so a gold value read from it can be found on the page.
    Runs inside a replacement's cover (``skip``) are left out: the new value
    is drawn there instead."""
    for text, rect in runs:
        if any(rect.intersects(s) for s in skip):
            continue
        size = max(4.0, rect.height * 0.8)
        page.insert_text(fitz.Point(rect.x0, rect.y1 - 0.2 * rect.height), text,
                         fontname="helv", fontsize=size, render_mode=3)


def as_chars(runs, matrix):
    """Recovered runs as layout characters (see :func:`overlay.cells`)."""
    from .overlay import Char
    inverse = ~matrix
    out = []
    for text, rect in runs:
        space = False
        for c, box in _chars_of(text, rect):
            if not c.strip():
                space = True
                continue
            out.append(Char(c, box, box * inverse, "OCR", rect.height, 0, space))
            space = False
    return out
