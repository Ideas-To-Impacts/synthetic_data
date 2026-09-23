"""
What a form template has to provide.

Everything else in this package - schema loading, page references, the absent
list, scanning, the checks, the CLI - works against this interface. Implement
four methods and a new carrier form joins the corpus with all of that already
attached.

    from fideon_synth import Template, draw

    class MyCarrierAuto(Template):
        key = "mycarrier_personal_auto"
        lob = "personal_auto"

        def variants(self, count=None, seed=0):
            ...         # list of plain dicts, whatever shape suits you
        def render(self, variant, path):
            ...         # draw the PDF, return the page count
        def gold(self, variant, pdf_name, pages):
            ...         # the canonical dict, FieldValue leaves, no page refs

The variant dict is yours. Nothing outside your template reads it, so there
is no schema to satisfy and no base class to inherit from - only the four
methods below.

``gold`` should not fill ``page_ref``. Those are measured off the rendered
PDF afterwards, which is what catches the case where the layout moved and the
gold did not.
"""

from __future__ import annotations

from .fields import as_number


class Template:
    """Base class for a carrier form. Subclass and override."""

    #: Stable identifier, used for filenames and on the command line.
    key = None
    #: Line of business, naming the canonical schema file to validate against.
    lob = None
    #: Document type folder under the canonical schema root.
    doc_type = "policy_check"
    #: Shown by ``fideon-synth --list``.
    description = ""

    # ── the four things a template must do ──────────────────────────────────

    def variants(self, count=None, seed=0):
        """The documents to build, as plain dicts.

        With ``count=None`` return the hand-written set. With a count, return
        that many - falling back to generated ones past the end of the
        hand-written set, so a team can start with five careful documents and
        grow to two hundred without rewriting anything.
        """
        raise NotImplementedError

    def render(self, variant, path):
        """Draw the PDF at ``path``. Return the page count."""
        raise NotImplementedError

    def gold(self, variant, pdf_name, pages):
        """The canonical document, leaves built with
        :mod:`fideon_synth.fields`. Leave ``page_ref`` empty."""
        raise NotImplementedError

    # ── things a template may do ────────────────────────────────────────────

    def name_for(self, variant):
        """The filename stem. Defaults to the variant's own ``key``."""
        return variant.get("key") or variant.get("policy_number")

    def audit(self, doc):
        """Extra arithmetic the document should satisfy, as error strings.

        The default is the rule every ``policy_check`` schema declares:
        the coverage premiums, plus any fees, come to the stated total. A
        line with no premium schedule should override this to return ``[]``.
        """
        coverages = doc.get("coverages") or []
        total_field = (doc.get("premium") or {}).get("total_policy_premium")
        if not coverages or not total_field:
            return []

        premiums = sum(as_number(c["premium"]["raw"])
                       for c in coverages
                       if c.get("premium")
                       and as_number(c["premium"]["raw"]) is not None)
        fees = sum(as_number(f["amount"]["raw"]) or 0.0
                   for f in (doc["premium"].get("taxes_and_fees") or []))
        total = as_number(total_field["raw"])
        if total is None:
            return ["premium.total_policy_premium is not a number: %r"
                    % total_field["raw"]]
        if abs((premiums + fees) - total) >= 0.01:
            return ["coverage premiums %.2f + fees %.2f != stated total %.2f"
                    % (premiums, fees, total)]
        return []

    def provenance(self, variant):
        """Extra keys folded into the gold file's ``fideon:provenance``."""
        return {}

    def __repr__(self):
        return "<%s %s -> %s>" % (type(self).__name__, self.key, self.lob)
