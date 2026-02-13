"""Training data and utilities for seeding Vanna agent memory.

This package contains:
- Schema documentation templates
- Sample query library with training pairs
- Seed script for populating agent memory
"""

from .sample_query_library import TRAINING_PAIRS, get_training_pairs, get_pairs_by_category

__all__ = [
    "TRAINING_PAIRS",
    "get_training_pairs",
    "get_pairs_by_category",
]
