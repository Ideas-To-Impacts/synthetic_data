"""
The canonical schema, loaded the way the pipeline loads it.

Gold data built against a *copy* of a schema drifts the moment the real one
changes, and nothing tells you: the copy still validates, against the wrong
thing. So this reads the live files and merges ``_common.json`` into the
line-specific file the way SchemaRegistry does at load time.

    schema = CanonicalSchema.load("dwelling_fire")
    schema.version          # '1.4.0'
    len(schema.leaves)      # 364
    schema.validate(gold)   # [] when it conforms

Where the schema lives is resolved in this order, so a teammate on another
machine does not have to edit code:

  1. the ``schema_dir`` argument
  2. the ``FIDEON_CANONICAL_SCHEMA`` environment variable
  3. the known install locations below
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DOC_TYPE = "policy_check"

#: Where the canonical schemas are checked out, in order of preference.
CANDIDATES = [
    Path(__file__).resolve().parent.parent / "config",
    Path(r"E:\fideon-synth\config"),
    Path(r"E:\SML\SLM L1\config\canonical_schema"),
    Path(r"C:\SML\SLM L1\config\canonical_schema"),
    Path.home() / "SLM L1" / "config" / "canonical_schema",
]

_NOT_FOUND = """Could not find the canonical schema directory.

Looked in:
{tried}

Point at it with one of:
    CanonicalSchema.load("{lob}", schema_dir=r"<path>\\canonical_schema")
    set FIDEON_CANONICAL_SCHEMA=<path>\\canonical_schema

It is the folder containing {doc_type}/, which in turn holds _common.json
and one file per line of business."""


def resolve_dir(schema_dir=None, doc_type=DOC_TYPE, lob="<lob>"):
    """Find the canonical schema root, or say clearly what to set."""
    tried = []
    for candidate in ([Path(schema_dir)] if schema_dir else []) + \
            ([Path(os.environ["FIDEON_CANONICAL_SCHEMA"])]
             if os.environ.get("FIDEON_CANONICAL_SCHEMA") else []) + CANDIDATES:
        tried.append(str(candidate))
        if (candidate / doc_type).is_dir():
            return candidate
        # tolerate being given the doc_type folder itself
        if candidate.name == doc_type and candidate.is_dir():
            return candidate.parent
    raise FileNotFoundError(_NOT_FOUND.format(
        tried="\n".join("  " + t for t in tried), lob=lob, doc_type=doc_type))


def available(schema_dir=None, doc_type=DOC_TYPE):
    """Every line of business with a schema, alphabetically."""
    root = resolve_dir(schema_dir, doc_type) / doc_type
    return sorted(p.stem for p in root.glob("*.json")
                  if not p.stem.startswith("_"))


class CanonicalSchema:
    """One line of business, merged with the common core."""

    def __init__(self, lob, merged, path):
        self.lob = lob
        self.merged = merged
        self.path = path
        self._validator = None

    # ── loading ─────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, lob, schema_dir=None, doc_type=DOC_TYPE):
        root = resolve_dir(schema_dir, doc_type, lob) / doc_type
        line_path = root / f"{lob}.json"
        if not line_path.exists():
            raise FileNotFoundError(
                "No schema for line of business %r in %s.\nAvailable: %s"
                % (lob, root, ", ".join(available(schema_dir, doc_type))))

        common = json.loads((root / "_common.json").read_text("utf-8"))
        line = json.loads(line_path.read_text("utf-8"))

        merged = dict(common)
        merged.update({k: v for k, v in line.items() if k != "properties"})
        props = dict(common.get("properties", {}))
        props.update(line.get("properties", {}))
        merged["properties"] = props
        defs = dict(common.get("$defs", {}))
        defs.update(line.get("$defs", {}))
        merged["$defs"] = defs
        return cls(lob, merged, line_path)

    # ── description ─────────────────────────────────────────────────────────

    @property
    def version(self):
        return self.merged.get("fideon:source", {}).get("version", "?")

    @property
    def mandatory(self):
        return list(self.merged.get("fideon:mandatory_fields", []))

    @property
    def audit_rules(self):
        return dict(self.merged.get("fideon:audit_rules", {}))

    def __repr__(self):
        return "<CanonicalSchema %s v%s, %d leaves>" % (
            self.lob, self.version, len(self.leaves))

    # ── structure ───────────────────────────────────────────────────────────

    @property
    def leaves(self):
        """Every addressable leaf, dotted, with list indices as ``[]``."""
        if not hasattr(self, "_leaves"):
            self._leaves = frozenset(self._walk())
        return self._leaves

    def _walk(self):
        out = []

        def visit(node, path):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                if name == "FieldValue":
                    out.append(path)
                else:
                    visit(self.merged["$defs"][name], path)
                return
            kind = node.get("type")
            if kind == "object":
                props = node.get("properties") or {}
                if not props:
                    out.append(path)
                for key, sub in props.items():
                    visit(sub, f"{path}.{key}" if path else key)
            elif kind == "array":
                visit(node.get("items") or {}, path + "[]")
            else:
                out.append(path)

        for key, node in self.merged["properties"].items():
            visit(node, key)
        return out

    def absent_from(self, stated, ignore=("text_sections",)):
        """Schema leaves this document does not state.

        A gold file that simply omits them cannot tell a harness the
        difference between "the document is silent" and "nobody looked", and
        a hallucinated value has nothing to be scored against. Naming them
        once costs a list; writing 300 nulls costs the file's readability.
        """
        return sorted(p for p in self.leaves
                      if p not in stated
                      and not any(p.startswith(i) for i in ignore))

    # ── validation ──────────────────────────────────────────────────────────

    def validate(self, doc):
        """Schema errors as readable strings; empty when the document
        conforms. Returns a single explanatory entry if jsonschema is not
        installed, rather than silently passing."""
        if self._validator is None:
            try:
                from jsonschema import Draft7Validator
            except ImportError:
                return ["jsonschema is not installed - validation skipped "
                        "(pip install jsonschema)"]
            self._validator = Draft7Validator(self.merged)
        return ["%s at %s" % (e.message,
                              "/".join(str(x) for x in e.path) or "(root)")
                for e in sorted(self._validator.iter_errors(doc),
                                key=lambda e: list(e.path))]
