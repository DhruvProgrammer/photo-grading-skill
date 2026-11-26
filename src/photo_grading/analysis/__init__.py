"""Analysis helpers for measurement and reverse engineering.

This package is imported by `critic.py` and by the `PHOTO_ANALYZE` report path. NumPy is
imported lazily inside `colorspace._np`, so importing the package (and the core image
operations) still works without the optional `[analysis]` extra.

Phase 1: `colorspace.py`, `lutio.py`, `descriptors.py`. Phase 2: `fit_params.py` (the
PHOTO_GRADING wheel model and its deterministic fit) and `probe_lut.py` (Mode C LUT probing).
"""
