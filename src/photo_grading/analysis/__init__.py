"""Analysis helpers for the reverse-engineering work (Phase 1).

This package is imported by `critic.py` and by the `PHOTO_ANALYZE` report path. NumPy is
imported lazily inside `colorspace._np`, so importing the package (and the core image
operations) still works without the optional `[analysis]` extra.
"""
