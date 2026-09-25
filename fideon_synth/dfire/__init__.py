"""
Dwelling-fire synthetic documents built from the real source PDFs.

Each source PDF under ``Data/original data/<carrier>/dwelling_fire/`` has one
profile in ``profiles/``. A profile says which printed values in that PDF are
variable, how to draw new ones, and how the whole document maps onto the
canonical ``dwelling_fire`` schema. :mod:`fideon_synth.dfire.engine` does the
rest: rewrites the PDF, builds and checks the gold, scans it.
"""
