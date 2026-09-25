"""
Page layout and in-place value replacement for any source PDF.

Source documents come in two kinds. Some have a real text layer; most of the
corpus is a scan with an invisible OCR layer laid over the image. Rewriting an
OCR layer changes nothing anyone can see, so a replacement here always:

  1. removes the old value's characters from the text layer
  2. paints a white box over where the page *shows* the value
  3. writes the new value there as real, visible text

Where the page shows it is measured from ink, not assumed from the text layer:
the value's box is rendered and the dark pixels give the glyphs' true extent,
which fixes the new text's size and baseline and how much to cover.

Some OCR layers are not in the page's own coordinates - a printed web page can
carry its text flipped and scaled against what is drawn. :func:`calibrate`
finds the matrix that puts the text layer back on the ink, so every position
below is in visible page coordinates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import fitz
import numpy as np

WHITE = (1, 1, 1)
FILL = set("_.…·")   # characters a form draws its fill-in lines with
ZOOM = 3.0          # ink measurement resolution, pixels per point
INK = 150           # grey level below which a pixel is ink


# ── ink ─────────────────────────────────────────────────────────────────────

class Ink:
    """A page rendered to a boolean ink mask, with an integral image for
    fast "is there ink in this rectangle" questions."""

    def __init__(self, page, zoom=ZOOM):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY,
                              annots=False)
        grey = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
        self.mask = grey[:, :pix.width] < INK
        self.zoom = zoom
        self.integral = np.pad(self.mask.cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def _px(self, rect):
        z, (h, w) = self.zoom, self.mask.shape
        x0, y0 = int(max(0, min(w, rect.x0 * z))), int(max(0, min(h, rect.y0 * z)))
        x1, y1 = int(max(0, min(w, rect.x1 * z))), int(max(0, min(h, rect.y1 * z)))
        return x0, y0, x1, y1

    def bbox(self, rect) -> Optional[fitz.Rect]:
        """Extent of the glyph ink inside ``rect``, ignoring rule lines."""
        x0, y0, x1, y1 = self._px(rect)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return None
        region = self.mask[y0:y1, x0:x1].copy()
        # a table rule or box edge crossing the region is not part of the value
        region[region.mean(1) > 0.8, :] = False
        region[:, region.mean(0) > 0.8] = False
        ys, xs = np.nonzero(region)
        if len(xs) < 4:
            return None
        z = self.zoom
        return fitz.Rect((x0 + xs.min()) / z, (y0 + ys.min()) / z,
                         (x0 + xs.max() + 1) / z, (y0 + ys.max() + 1) / z)

    def cols(self, y0, y1):
        """Which pixel columns hold glyph ink between ``y0`` and ``y1`` -
        table rules and box edges excluded, since they belong to no value."""
        z, (h, w) = self.zoom, self.mask.shape
        py0, py1 = int(max(0, y0 * z)), int(min(h, y1 * z))
        if py1 - py0 < 2:
            return np.zeros(w, bool)
        key = (py0, py1)
        cache = self.__dict__.setdefault("_profiles", {})
        if key not in cache:
            band = self.mask[py0:py1]
            band = band[band.mean(1) < 0.5]          # drop horizontal rules
            cols = band.any(0) if len(band) else np.zeros(w, bool)
            # drop vertical rules: ink that runs well above and below the row
            ext = max(2, (py1 - py0) // 2)
            tall = self.mask[max(0, py0 - ext):min(h, py1 + ext)]
            line = tall.mean(0) > 0.75
            line[1:] |= line[:-1].copy()             # anti-aliased edges
            line[:-1] |= line[1:].copy()
            cache[key] = cols & ~line
        return cache[key]

    def run(self, y0, y1, x0, x1, limit, gap, glued=False):
        """Horizontal extent of the printed text that starts at ``x0``.

        Never reaches left of ``x0`` by more than a point - a label printed
        against the value (``HIN:327939``) must survive. Rightwards it follows
        the ink until a blank run of ``gap`` points or ``limit``, because an
        OCR box is often narrower than the print it describes.
        """
        z = self.zoom
        cols = self.cols(y0, y1)
        w = len(cols)
        a, b = int(max(0, (x0 - 1) * z)), int(min(w, x1 * z))
        if glued:                           # never start left of the value's own box
            a = int(max(a, (x0 + 0.5) * z))
        if a > 0 and cols[a] and (cols[a - 1] or glued):
            # the box starts inside the previous word's ink (a label run up
            # against the value): skip to the first blank, then the value
            k = a
            while k < a + 0.4 * (b - a) and cols[k]:
                k += 1
            if k < a + 0.4 * (b - a):
                a = k
        inked = np.nonzero(cols[a:b])[0]
        if not len(inked):
            return x0, x1
        left, right = a + inked[0], a + inked[-1]
        stop, blank = int(min(w, limit * z)), 0
        x = right + 1
        while x < stop:
            if cols[x]:
                right, blank = x, 0
            else:
                blank += 1
                if blank >= gap * z:
                    break
            x += 1
        return left / z, (right + 1) / z

    def line_extent(self, x0, x1, yc, ymin, ymax):
        """Top and bottom of the printed line through ``yc`` between ``x0``
        and ``x1`` - just that line, not the rows above and below it, which
        in a tight table sit closer than a line height."""
        z, (h, w) = self.zoom, self.mask.shape
        a, b = int(max(0, x0 * z)), int(min(w, x1 * z))
        p0, p1 = int(max(0, ymin * z)), int(min(h, ymax * z))
        if b - a < 2 or p1 - p0 < 3:
            return None
        region = self.mask[p0:p1, a:b]
        rows = region.mean(1)
        rows[rows > 0.8] = 0                      # a rule under the value
        inked = rows > 0
        c = int(max(0, min(len(inked) - 1, yc * z - p0)))
        if not inked[c]:                          # nearest inked row to the centre
            idx = np.nonzero(inked)[0]
            if not len(idx):
                return None
            c = idx[np.argmin(abs(idx - c))]
        top = bottom = c
        while top > 0 and inked[top - 1]:
            top -= 1
        while bottom < len(inked) - 1 and inked[bottom + 1]:
            bottom += 1
        return (p0 + top) / z, (p0 + bottom + 1) / z

    def next_ink(self, y0, y1, x, limit):
        """Where the next printed word right of ``x`` begins - the first ink
        after a blank - or None before ``limit``."""
        z = self.zoom
        cols = self.cols(y0, y1)
        p, stop = int(max(0, x * z)), int(min(len(cols), limit * z))
        while p < stop and cols[p]:
            p += 1
        while p < stop and not cols[p]:
            p += 1
        return p / z if p < stop else None

    def word_start(self, y0, y1, x, gap):
        """Where the printed word under ``x`` begins: back over ink and over
        blanks narrower than ``gap``."""
        z = self.zoom
        cols = self.cols(y0, y1)
        p = int(max(0, min(len(cols) - 1, x * z)))
        if not cols[p]:
            return x
        blank = 0
        start = p
        while p > 0:
            p -= 1
            if cols[p]:
                start, blank = p, 0
            else:
                blank += 1
                if blank >= gap * z:
                    break
        return start / z

    def blank(self, y0, y1, x):
        """Width in points of the blank run printed immediately left of ``x``
        (where a character starts) - 0 when ink touches it.

        Measured leftwards from the next character's start because an OCR
        layer places each word where it starts but often draws it narrower
        than the print, so the gap between two text-layer boxes can sit on
        the tail of the previous printed word.

        The text layer's own spacing cannot be trusted for this: an OCR layer
        is often narrower than the print, and its space characters are
        erratic. The ink is what the reader sees.
        """
        z = self.zoom
        cols = self.cols(y0, y1)
        w = len(cols)
        s = int(max(1, min(w - 1, x * z)))
        # the character's first ink, allowing its box to start a little early
        p = s
        while p < min(w - 1, s + 2 * z) and not cols[p]:
            p += 1
        if not cols[p]:
            p = s
        q = p - 1
        while q >= 0 and not cols[q]:
            q -= 1
        return (p - 1 - q) / z


def invisible_text(page) -> bool:
    """Is most of this page's text an invisible (OCR) layer?"""
    kinds = {}
    for trace in page.get_texttrace():
        kinds[trace["type"]] = kinds.get(trace["type"], 0) + len(trace["chars"])
    total = sum(kinds.values())
    return bool(total) and kinds.get(3, 0) > total / 2


def calibrate(page, ink: Ink) -> fitz.Matrix:
    """Matrix from text-layer to visible coordinates.

    Identity when the words sit on ink, which is nearly always. Otherwise
    search scale, flip and offset for the placement that puts the most words
    on ink - a text layer that landed somewhere else entirely would otherwise
    have every replacement drawn over empty paper.
    """
    words = [fitz.Rect(w[:4]) for w in page.get_text("words")]
    if len(words) < 8:
        return fitz.Identity
    boxes = np.array([[r.x0, r.y0, r.x1, r.y1] for r in words])
    I, z = ink.integral, ink.zoom
    H, W = ink.mask.shape

    def score(sx, sy, dx, dy):
        xs = np.sort(np.stack([boxes[:, 0] * sx + dx, boxes[:, 2] * sx + dx]), 0) * z
        ys = np.sort(np.stack([boxes[:, 1] * sy + dy, boxes[:, 3] * sy + dy]), 0) * z
        x0, x1 = np.clip(xs[0], 0, W).astype(int), np.clip(xs[1], 0, W).astype(int)
        y0, y1 = np.clip(ys[0], 0, H).astype(int), np.clip(ys[1], 0, H).astype(int)
        hits = I[y1, x1] - I[y0, x1] - I[y1, x0] + I[y0, x0]
        return float(np.mean(hits >= 3))

    if score(1, 1, 0, 0) >= 0.7:
        return fitz.Identity

    best = (0.0, 1, 1, 0, 0)
    height = page.rect.height
    for flip in (1, -1):
        for s in np.arange(0.6, 1.61, 0.01):
            lo, hi = (-height, height) if flip == 1 else (0, 2.2 * height)
            for dy in np.arange(lo, hi, 3):
                sc = score(s, flip * s, 0, dy)
                if sc > best[0]:
                    best = (sc, s, flip * s, 0, dy)
    _, sx, sy, dx, dy = best
    for ddx in np.arange(-30, 31, 1.0):          # then refine the offsets
        for ddy in np.arange(-4, 4.1, 0.5):
            sc = score(sx, sy, ddx, dy + ddy)
            if sc > best[0]:
                best = (sc, sx, sy, ddx, dy + ddy)
    if best[0] < 0.5:
        return fitz.Identity
    _, sx, sy, dx, dy = best
    return fitz.Matrix(sx, 0, 0, sy, dx, dy)


# ── layout ──────────────────────────────────────────────────────────────────

@dataclass
class Char:
    c: str
    box: fitz.Rect          # visible coordinates
    ocr: fitz.Rect          # text-layer coordinates, for removal
    font: str
    size: float
    color: int
    space_before: bool = False    # the text layer put a space before this char
    leader: bool = False          # one dot of a line drawn as a row of dots


@dataclass
class Cell:
    """A run of text on one row with no wide gap in it - a label, a value,
    or a label and its value when they are printed close together."""
    text: str
    chars: List[Optional[Char]]     # aligned with text; None for spaces
    row: int
    page: int

    @property
    def rect(self):
        if self.__dict__.get("_rect") is None:
            r = None
            for ch in self.chars:
                if ch is not None:
                    r = fitz.Rect(ch.box) if r is None else r | ch.box
            self.__dict__["_rect"] = r
        return fitz.Rect(self.__dict__["_rect"])

    def span_rect(self, start, end, ocr=False):
        r = None
        for ch in self.chars[start:end]:
            if ch is not None:
                b = ch.ocr if ocr else ch.box
                r = fitz.Rect(b) if r is None else r | b
        return r


def layer_chars(page, matrix=fitz.Identity):
    """The text layer's characters, in visible page coordinates."""
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    if ch["c"].strip() and ch["c"] != "\ufffd":
                        ocr = fitz.Rect(ch["bbox"])
                        chars.append(Char(ch["c"], ocr * matrix, ocr, span["font"],
                                          span["size"], span.get("color", 0)))
    return chars


def cells(page, matrix=fitz.Identity, ink: Optional[Ink] = None,
          extra=None, drop=None) -> List[Cell]:
    """Every cell on the page, top to bottom, left to right.

    Words and columns are told apart by the blank space printed between
    characters (see :meth:`Ink.blank`); without ``ink`` the text-layer boxes
    are used instead. ``extra`` adds characters read from the page image
    that the layer lacks, and ``drop`` removes the layer's characters inside
    the given rects (see :mod:`recover`)."""
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            space = False
            # a text line that is all dots is a rule drawn under a row, not text
            glyphs = [ch["c"] for span in line["spans"] for ch in span["chars"] if ch["c"].strip()]
            leader = len(glyphs) >= 3 and sum(c in FILL for c in glyphs) >= 0.8 * len(glyphs)
            for span in line["spans"]:
                for ch in span["chars"]:
                    if not ch["c"].strip():
                        space = True
                        continue
                    if ch["c"] == "�":        # a glyph with no text behind it
                        continue
                    ocr = fitz.Rect(ch["bbox"])
                    chars.append(Char(ch["c"], ocr * matrix, ocr, span["font"],
                                      span["size"], span.get("color", 0), space,
                                      leader and ch["c"] in FILL))
                    space = False
    if drop:
        chars = [ch for ch in chars if not any(
            r.contains(fitz.Point((ch.box.x0 + ch.box.x1) / 2, (ch.box.y0 + ch.box.y1) / 2))
            for r in drop)]
    chars += list(extra or [])
    chars.sort(key=lambda ch: (ch.box.y1, ch.box.x0))
    # text printed twice a hair apart (a poor man's bold) is one text
    kept, recent = [], []
    for ch in chars:
        if any(o.c == ch.c and abs(o.box.x0 - ch.box.x0) < 0.4 * max(ch.box.width, 1)
               and abs(o.box.y1 - ch.box.y1) < 0.4 * max(ch.box.height, 1) for o in recent):
            continue
        kept.append(ch)
        recent = [o for o in recent[-40:] if abs(o.box.y1 - ch.box.y1) < ch.box.height] + [ch]
    chars = kept

    # a row is one baseline: each character is compared with the row's own
    # baseline, not the previous character, so lines of different sizes set close together
    # (a heading beside a small label) cannot chain into one interleaved row
    rows: List[List[Char]] = []
    for ch in chars:
        if rows:
            row = rows[-1]
            base = float(np.median([c.box.y1 for c in row[-12:]]))
            tol = 0.45 * min(row[0].box.height, ch.box.height)
            if abs(base - ch.box.y1) <= tol:
                row.append(ch)
                continue
        rows.append([ch])

    out = []
    for r, row in enumerate(rows):
        row.sort(key=lambda ch: ch.box.x0)
        # a form's fill-in line (underscores, dot leaders) runs under the typed
        # value; interleaved with it the value would read _b_w_in_s_l_o_w_
        typed = [ch.box for ch in row if ch.c not in FILL]
        row[:] = [ch for ch in row if ch.c not in FILL or not any(
            min(ch.box.x1, b.x1) - max(ch.box.x0, b.x0) > 0.3 * ch.box.width for b in typed)]
        # a dot of a rule set a little under the row falls in the spaces of
        # the text over it: "Jul 23,. 2026", "$71..00"
        typed = [ch for ch in row if ch.c not in FILL]
        def inside(ch):
            left = [b for b in typed if b.box.x1 <= ch.box.x0 + 0.5 * ch.box.width]
            right = [b for b in typed if b.box.x0 >= ch.box.x1 - 0.5 * ch.box.width]
            if not left or not right:
                return False
            a = max(left, key=lambda b: b.box.x1)
            b = min(right, key=lambda b: b.box.x0)
            return b.box.x0 - a.box.x1 < 1.1 * max(a.box.height, b.box.height)
        row[:] = [ch for ch in row if not ch.leader or not inside(ch)]
        # a leader between columns ("Uninsured Boater ....... $300,000") is
        # layout, not text: drop it and break the cell where it stood. A lone
        # full stop is punctuation; a run of three, or any ellipsis glyph, is a
        # leader
        breaks, kept, k = set(), [], 0
        while k < len(row):
            if row[k].c in FILL:
                run = k
                while run < len(row) and row[run].c in FILL:
                    run += 1
                if run - k >= 3 or any(ch.c == "\u2026" for ch in row[k:run]):
                    # a break only where the leader spans a gap: a stray leader
                    # glyph drawn inside a word ("Nautica...l") joins it back
                    if run < len(row) and k > 0 and \
                            row[run].box.x0 - row[k - 1].box.x1 > 0.5 * row[run].box.height:
                        breaks.add(id(row[run]))
                    k = run
                    continue
                kept.extend(row[k:run])
                k = run
                continue
            kept.append(row[k])
            k += 1
        row[:] = kept
        if not row:
            continue
        height = float(np.median([ch.box.height for ch in row]))
        text, members = [], []
        prev = None
        top = min(ch.box.y0 for ch in row) + 0.15 * height
        bottom = max(ch.box.y1 for ch in row) - 0.1 * height
        for ch in row:
            if prev is not None:
                gap = ch.box.x0 - prev.box.x1
                column = gap > 1.1 * height or id(ch) in breaks
                # a compressed OCR layer leaves wide gaps between words that
                # are printed a normal space apart; the ink says which
                if column and id(ch) not in breaks and ink is not None \
                        and ink.blank(top, bottom, ch.box.x0) < 0.9 * height:
                    column = False
                if column:
                    out.append(Cell("".join(text), members, r, page.number))
                    text, members = [], []
                elif ch.space_before or gap > max(0.8, 0.3 * height):
                    text.append(" ")
                    members.append(None)
            text.append(ch.c)
            members.append(ch)
            prev = ch
        out.append(Cell("".join(text), members, r, page.number))
    return out


# ── drawing ─────────────────────────────────────────────────────────────────

_BASE14 = {("serif", False): "tiro", ("serif", True): "tibo",
           ("sans", False): "helv", ("sans", True): "hebo"}
_DESCENDERS = set("gjpqy,;()[]{}Q@")


def base14(font_name, visible):
    """The base-14 face nearest a source font. An OCR layer's font says
    nothing about the printed face, so invisible text gets Helvetica."""
    if not visible:
        return "helv"
    name = font_name.split("+")[-1].lower()
    serif = "times" in name or "serif" in name and "sans" not in name
    bold = "bold" in name or "black" in name or "heavy" in name
    return _BASE14[("serif" if serif else "sans", bold)]


@dataclass
class Replacement:
    page: int
    old: str
    new: str
    visible_rect: fitz.Rect
    ocr_rect: fitz.Rect
    font: str = "helv"
    color: int = 0
    align: str = "left"
    room: Optional[float] = None      # x the new text must not run past
    face_known: bool = False          # font taken from a visible text layer
    glued: bool = False               # printed against a label (HIN:327939)
    follows: bool = False             # more words printed after it on its line


def _size_from_ink(text, glyphs):
    """Font size and baseline from the ink of ``text`` as printed.

    Capitals and digits stand 0.72 em on the baseline; ``$`` and ``,`` and
    lowercase descenders reach below it, so they change both the ratio and
    where the baseline sits in the ink."""
    lower_desc = bool(set(text) & set("gjpqy()[]{}@"))
    dollar = "$" in text
    comma = "," in text or ";" in text
    if lower_desc:
        size = glyphs.height / 0.93
        return size, glyphs.y1 - 0.21 * size
    if dollar:
        size = glyphs.height / 0.86
        return size, glyphs.y1 - 0.1 * size
    if comma:
        size = glyphs.height / 0.86
        return size, glyphs.y1 - 0.14 * size
    size = glyphs.height / 0.72
    return size, glyphs.y1


def metrics(page, ink: Ink, matrix=fitz.Identity):
    """How this page's text-layer boxes relate to its printed glyphs:
    ``(size_per_height, baseline_per_height)``.

    Measured, once per page, on words of capitals and digits - no descenders,
    so their ink runs from cap height (0.72 em) down to the baseline. The
    median over many words is steady where one word's ink is not: a single
    value in a dense table picks up its neighbours.
    """
    sizes, bases, feet = [], [], []
    for w in page.get_text("words"):
        text = w[4]
        if len(text) < 2 or not re.fullmatch(r"[A-Z0-9$#%&/.:+-]+", text):
            continue
        r = fitz.Rect(w[:4]) * matrix
        h = r.height
        if h < 2:
            continue
        line = ink.line_extent(r.x0, r.x1, (r.y0 + r.y1) / 2, r.y0 - 0.25 * h, r.y1 + 0.1 * h)
        if line is None or line[1] - line[0] < 0.3 * h:
            continue
        glyphs = ink.bbox(fitz.Rect(r.x0, line[0], r.x1, line[1]))
        if glyphs is None:
            continue
        sizes.append(glyphs.height / 0.72 / h)
        bases.append((r.y1 - glyphs.y1) / h)
        # serifs put ink along the baseline: a capital's foot is wider than
        # its waist in Times (about 1.3x) and not in Helvetica (about 1.0x)
        if re.fullmatch(r"[A-Z]{3,}", text):
            z = ink.zoom
            region = ink.mask[int(line[0] * z):int(line[1] * z), int(r.x0 * z):int(r.x1 * z)]
            n = region.shape[0]
            if n >= 6 and region.shape[1] >= 6:
                waist = region[int(n * 0.4):int(n * 0.6)].any(0).mean()
                if waist:
                    feet.append(region[int(n * 0.88):].any(0).mean() / waist)
        if len(sizes) >= 80:
            break
    face = "tiro" if feet and float(np.median(feet)) > 1.12 else "helv"
    if len(sizes) < 5:
        return 0.8, 0.16, face
    return float(np.median(sizes)), float(np.median(bases)), face


def apply(page, replacements: List[Replacement], ink: Ink, matrix=fitz.Identity):
    """Remove, cover and redraw every replacement on one page."""
    if not replacements:
        return
    k, b, face = metrics(page, ink, matrix)
    # a text layer mapped through a fitted matrix is a point or two out;
    # there the printed word's own start is more reliable than the box
    uncertain = not matrix.is_rectilinear or tuple(matrix) != tuple(fitz.Identity)
    measured = []
    for rep in replacements:
        r = rep.visible_rect
        h = r.height
        size = k * h
        baseline = r.y1 - b * h
        x0, ok = r.x0, False
        for _ in range(2):          # the second pass uses the measured line
            band = (baseline - 0.7 * size, baseline - 0.05 * size)
            if uncertain:
                x0 = ink.word_start(*band, r.x0 + 0.3 * size, gap=0.3 * size)
            # the print is about as wide as the old text in this size, and a
            # comma or a time printed after it is not part of it
            printed = fitz.get_text_length(rep.old, fontname=rep.font, fontsize=size)
            limit = min(rep.room if rep.room is not None else page.rect.width,
                        x0 + 1.2 * printed + 0.5)
            left, right = ink.run(*band, x0, max(x0 + 1, r.x1 - (r.x0 - x0)), limit,
                                  gap=0.2 * size, glued=rep.glued)
            right = max(right, min(r.x1, limit))
            line = ink.line_extent(left, right, baseline - 0.36 * size,
                                   baseline - 1.1 * size, baseline + 0.45 * size)
            if line is None:
                break
            s, base = _size_from_ink(rep.old, fitz.Rect(left, line[0], right, line[1]))
            if not 0.45 < s / (k * h) < 1.6:
                break
            size, baseline, ok = s, base, True
        if rep.follows and ok:
            # the next word's own ink bounds the new value - on a scan the
            # text layer can sit a few points off the print
            nxt = ink.next_ink(baseline - 0.7 * size, baseline - 0.05 * size, right,
                               right + 6 * size)
            if nxt is not None:
                bound = nxt - 0.3 * size
                rep.room = bound if rep.room is None else min(rep.room, bound)
        measured.append([rep, size, baseline, left, right, ok])

    # a value whose own line could not be read takes the size the other
    # values on this page were printed at, for its box height
    ratios = [m[1] / m[0].visible_rect.height for m in measured if m[5]]
    if ratios:
        typical = float(np.median(ratios))
        for m in measured:
            if not m[5]:
                h = m[0].visible_rect.height
                m[1] = typical * h
                m[2] = m[0].visible_rect.y1 - b * h

    placed = []
    for rep, size, baseline, left, right, _ in measured:
        r = rep.visible_rect
        cover = fitz.Rect(left - 0.5, min(baseline - 0.8 * size, r.y0 + 0.1 * r.height),
                          right + 0.5, max(baseline + 0.25 * size, r.y1 - 0.1 * r.height))
        if not rep.face_known:
            rep.font = face
        placed.append((rep, size, baseline, cover, left, right))

    # only the middle of the old text's line: OCR boxes of tightly set lines
    # overlap by a point, and a redaction takes every character it touches -
    # the value on the next line would leave the text layer while it stays
    # printed on the page
    for rep, *_ in placed:
        inset = max(0.25, 0.3 * rep.ocr_rect.height)
        page.add_redact_annot(rep.ocr_rect + (0.25, inset, -0.25, -inset), fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE)

    for rep, size, baseline, cover, left, right in placed:
        page.draw_rect(cover, color=None, fill=WHITE, overlay=True)
        if rep.old[:1] in "Jjfgpqy":
            # the hook of a "J" curls back under the baseline, left of where the
            # ink above it begins: covered by the band alone it leaves a dot
            page.draw_rect(fitz.Rect(left - 0.35 * size, baseline - 0.05 * size,
                                     left + 0.5, baseline + 0.3 * size),
                           color=None, fill=WHITE, overlay=True)

    for rep, size, baseline, cover, left, right in placed:
        if not rep.new.strip():
            continue                                  # a blanked piece
        width = fitz.get_text_length(rep.new, fontname=rep.font, fontsize=size)
        if rep.align == "right":
            x = right - width
        else:
            x = left
        squeeze = 1.0
        if rep.room is not None and x + width > rep.room and rep.align != "right":
            # a longer value set where a shorter one stood - "January 24,
            # 2027" for "May 23, 2026" in a sentence - is set condensed, as
            # tight forms are, and only then smaller, so it never runs into
            # the words after it
            fit = max(0.05, (rep.room - x) / width)
            squeeze = max(0.62, fit)
            size *= max(0.8, fit / squeeze)
        c = rep.color
        morph = (fitz.Point(x, baseline), fitz.Matrix(squeeze, 1)) if squeeze < 1 else None
        page.insert_text((x, baseline), rep.new, fontname=rep.font, fontsize=size, morph=morph,
                         color=((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255))
