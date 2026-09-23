"""
Drawing primitives for carrier forms.

A declarations page is not a document that flows - it is a printed form. Fixed
rules, a party box with vertical dividers, black section bars, dashed row
separators, a signature panel pinned to the bottom of page one. Platypus wants
to reflow all of that, and the whole point of a synthetic corpus is that the
page looks like the page an extractor will actually meet.

So these wrap a bare canvas. Coordinates are points from the bottom-left, as
PDF counts them.

    def draw(sheet):
        sheet.rule(707)
        sheet.text(sheet.left, 694, "New Policy", BOLD_ITALIC, 8.6)
        table = Table(sheet, [Column(46, 435), Column(435, 500, "right"),
                              Column(500, 568, "right")])
        y = table.bar(340, ["Section I", "COVERAGE LIMIT", "PREMIUM"])
        y = table.row(y, ["Coverage A - Residence", "$198,000", "$742.00"])

    pages = render("out.pdf", draw)

``render`` calls ``draw`` twice: a page cannot say "Page 1 of 2" until the
document has been laid out once and the 2 is known.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _canvas

REGULAR = "Helvetica"
BOLD = "Helvetica-Bold"
ITALIC = "Helvetica-Oblique"
BOLD_ITALIC = "Helvetica-BoldOblique"
SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"
MONO = "Courier"


class Sheet:
    """One document being drawn, across however many pages it takes."""

    def __init__(self, target, pagesize=letter, left=46.0, right=568.0,
                 total_pages=0, **meta):
        self.canvas = _canvas.Canvas(
            target if isinstance(target, io.IOBase) else str(target),
            pagesize=pagesize)
        self.width, self.height = pagesize
        self.left, self.right = left, right
        self.page = 1
        self.total_pages = total_pages
        for key, value in meta.items():
            setter = getattr(self.canvas, "set" + key.capitalize(), None)
            if setter:
                setter(value)

    # ── text ────────────────────────────────────────────────────────────────

    def text(self, x, y, string, font=REGULAR, size=9):
        self.canvas.setFont(font, size)
        self.canvas.drawString(x, y, string)
        return x + self.canvas.stringWidth(string, font, size)

    def right_text(self, x, y, string, font=REGULAR, size=9):
        self.canvas.setFont(font, size)
        self.canvas.drawRightString(x, y, string)
        return x - self.canvas.stringWidth(string, font, size)

    def centre_text(self, x, y, string, font=REGULAR, size=9):
        self.canvas.setFont(font, size)
        self.canvas.drawCentredString(x, y, string)

    def run(self, x, y, parts):
        """A line made of differently-styled runs.

        ``parts`` is ``[(text, font, size), ...]``. This is how a form prints
        "Policy ID: 10-2026-14207" - the label bold, the value not - and
        doing it by hand every time is where drift creeps in.
        """
        for string, font, size in parts:
            x = self.text(x, y, string, font, size)
        return x

    def measure(self, string, font=REGULAR, size=9):
        return self.canvas.stringWidth(string, font, size)

    def wrap(self, string, width, font=REGULAR, size=9):
        """Break text to a column width. Returns the lines."""
        lines, current = [], ""
        for word in string.split():
            trial = (current + " " + word).strip()
            if self.measure(trial, font, size) <= width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def paragraph(self, x, y, string, width, font=REGULAR, size=8,
                  leading=10.4):
        for line in self.wrap(string, width, font, size):
            self.text(x, y, line, font, size)
            y -= leading
        return y

    # ── lines and boxes ─────────────────────────────────────────────────────

    def rule(self, y, width=0.9, x0=None, x1=None, gray=0):
        c = self.canvas
        c.saveState()
        c.setLineWidth(width)
        c.setStrokeGray(gray)
        c.line(self.left if x0 is None else x0, y,
               self.right if x1 is None else x1, y)
        c.restoreState()

    def dashed(self, y, x0=None, x1=None, gray=0.35):
        c = self.canvas
        c.saveState()
        c.setDash(1.2, 1.6)
        c.setLineWidth(0.4)
        c.setStrokeGray(gray)
        c.line(self.left if x0 is None else x0, y,
               self.right if x1 is None else x1, y)
        c.restoreState()

    def vline(self, x, y0, y1, width=0.7, gray=0):
        c = self.canvas
        c.saveState()
        c.setLineWidth(width)
        c.setStrokeGray(gray)
        c.line(x, y0, x, y1)
        c.restoreState()

    def box(self, x0, y0, x1, y1, width=0.9, fill=None):
        c = self.canvas
        c.saveState()
        c.setLineWidth(width)
        if fill is not None:
            c.setFillGray(fill)
        c.rect(x0, y0, x1 - x0, y1 - y0, fill=fill is not None)
        c.restoreState()

    def swatch(self, x, y, size=4.2, gray=0):
        """The small filled square a form uses as a bullet."""
        c = self.canvas
        c.saveState()
        c.setFillGray(gray)
        c.rect(x, y, size, size, fill=1, stroke=0)
        c.restoreState()

    # ── composite blocks ────────────────────────────────────────────────────

    def column_box(self, y_top, columns, xs, dividers=(), leading=10.2,
                   caption_font=BOLD, body_font=REGULAR, size=8.4, pad=4.0):
        """The captioned multi-column party box: Mail To / Insured / Agency.

        ``columns`` is ``[(caption, [line, ...]), ...]``. Returns the y of the
        rule that closes the box, so the caller can carry on beneath it.
        """
        self.rule(y_top, 1.0)
        y_caption = y_top - 12
        tallest = max(len(body) for _, body in columns)
        y_bottom = y_caption - leading * (tallest + 1) - pad

        for (caption, body), x in zip(columns, xs):
            self.text(x, y_caption, caption, caption_font, size)
            y = y_caption - leading
            for line in body:
                self.text(x, y, line, body_font, size)
                y -= leading

        for x in dividers:
            self.vline(x, y_bottom, y_caption + 8)
        self.rule(y_bottom, 0.8)
        return y_bottom

    def footer(self, y, left=None, centre=None, right=None, size=7.8,
               rule_above=12):
        """The repeated strip at the foot of every page."""
        if rule_above:
            self.rule(y + rule_above, 0.8)
        if left:
            self.text(self.left, y, left, BOLD, size)
        if centre:
            width = sum(self.measure(s, f, size) for s, f in centre)
            x = (self.width - width) / 2.0
            for string, font in centre:
                x = self.text(x, y, string, font, size)
        if right:
            self.right_text(self.right, y + 1, right, SERIF_BOLD, size + 1.4)

    def scrawl(self, x, y, width=82, height=18):
        """A signature. It signs nothing - it is ink in the shape of ink."""
        c = self.canvas
        c.saveState()
        c.setLineWidth(0.9)
        p = c.beginPath()
        p.moveTo(x, y)
        step = width / 4.0
        for i in range(4):
            p.curveTo(x + step * i + step * 0.3, y + height * (0.9 if i % 2 else 0.3),
                      x + step * i + step * 0.6, y - height * (0.2 if i % 2 else 0.0),
                      x + step * (i + 1), y + height * (0.1 if i % 2 else 0.6))
        c.drawPath(p)
        c.line(x + width, y + 2, x + width + 56, y + 2)
        c.restoreState()

    # ── paging ──────────────────────────────────────────────────────────────

    def new_page(self, y_top):
        self.canvas.showPage()
        self.page += 1
        return y_top

    def save(self):
        self.canvas.showPage()
        self.canvas.save()
        return self.page


# ── tables ──────────────────────────────────────────────────────────────────

@dataclass
class Column:
    x0: float
    x1: float
    align: str = "left"     # left | right | centre
    pad: float = 8.0


class Table:
    """A bordered schedule with black section bars and dashed row rules.

    The shape almost every carrier's declarations schedule takes, whatever
    the line: a bar naming the section and the column headings, then rows.
    """

    def __init__(self, sheet, columns, row_height=18.0, bar_height=10.5,
                 font=(REGULAR, 9), bar_font=(BOLD, 5.4),
                 note_font=(ITALIC, 8.4)):
        self.sheet = sheet
        self.columns = list(columns)
        self.row_height = row_height
        self.bar_height = bar_height
        self.font, self.bar_font = font, bar_font
        self.note_font = note_font

    @property
    def x0(self):
        return self.columns[0].x0

    @property
    def x1(self):
        return self.columns[-1].x1

    def _place(self, column, y, string, font, size):
        if not string:
            return
        if column.align == "right":
            self.sheet.right_text(column.x1 - column.pad, y, string, font, size)
        elif column.align == "centre":
            self.sheet.centre_text((column.x0 + column.x1) / 2.0, y, string,
                                   font, size)
        else:
            self.sheet.text(column.x0 + column.pad, y, string, font, size)

    def bar(self, y, labels):
        """A black section bar. Returns the y beneath it."""
        c = self.sheet.canvas
        c.saveState()
        c.setFillGray(0)
        c.rect(self.x0, y - self.bar_height, self.x1 - self.x0,
               self.bar_height, fill=1, stroke=0)
        c.setFillGray(1)
        font, size = self.bar_font
        baseline = y - self.bar_height + 3.4
        for column, label in zip(self.columns, labels):
            if not label:
                continue
            c.setFont(font, size)
            if column.align == "left" and column is self.columns[0]:
                c.drawString(column.x0 + 6, baseline, label)
            else:
                c.drawCentredString((column.x0 + column.x1) / 2.0, baseline,
                                    label)
        c.restoreState()
        return y - self.bar_height

    def row(self, y, values, note=None, note_column=0, rule_above=False):
        """One schedule row. Returns the y beneath it.

        ``note`` is the right-aligned italic qualifier a form tucks into the
        description cell - "(Each Occurrence)", "(Each Person)".
        """
        top, bottom = y, y - self.row_height
        if rule_above:
            self.sheet.dashed(top, self.x0, self.x1)
        for x in [self.x0] + [c.x1 for c in self.columns]:
            self.sheet.vline(x, bottom, top)

        baseline = bottom + 5.6
        font, size = self.font
        for column, value in zip(self.columns, values):
            self._place(column, baseline, value, font, size)
        if note:
            column = self.columns[note_column]
            nfont, nsize = self.note_font
            self.sheet.right_text(column.x1 - column.pad, baseline, note,
                                  nfont, nsize)
        return bottom

    def close(self, y, width=0.9):
        self.sheet.rule(y, width, self.x0, self.x1)
        return y


# ── two-pass rendering ──────────────────────────────────────────────────────

def render(path, draw, pagesize=letter, left=46.0, right=568.0, **meta):
    """Draw a document and return its page count.

    ``draw(sheet)`` is called twice. The first pass goes to a throwaway
    buffer purely to learn how many pages the content takes; the second
    writes the file with ``sheet.total_pages`` set, so a footer can say
    "Page 1 of 2" truthfully. Any footer that reads ``total_pages`` sees 0 on
    the first pass, which is why it should fall back to the current page.
    """
    probe = Sheet(io.BytesIO(), pagesize, left, right, total_pages=0)
    draw(probe)
    pages = probe.save()

    sheet = Sheet(path, pagesize, left, right, total_pages=pages, **meta)
    draw(sheet)
    sheet.save()
    return pages
