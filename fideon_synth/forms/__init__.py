"""Carrier form templates.

Every template registered here is reachable from the command line by its
``key``. Adding one is two lines: import it, and add it to ``TEMPLATES``.
"""

from .leatherstocking_dwelling_fire import LeatherstockingDwellingFire

TEMPLATES = [LeatherstockingDwellingFire]


def by_key(key):
    """Look a template up by name, listing the alternatives when it is wrong."""
    for template in TEMPLATES:
        if template.key == key:
            return template()
    raise KeyError("No form template %r. Available: %s"
                   % (key, ", ".join(t.key for t in TEMPLATES)))


def catalogue():
    return [(t.key, t.lob, t.description) for t in TEMPLATES]


__all__ = ["TEMPLATES", "by_key", "catalogue", "LeatherstockingDwellingFire"]
