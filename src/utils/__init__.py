"""Utilities module - Helper functions and cross-platform utilities."""

from .paths import (
    get_default_locations,
    normalize_path,
    get_app_data_dir,
    get_database_path,
)
from .fuzzy_match import fuzzy_match_projects, calculate_similarity

__all__ = [
    "get_default_locations",
    "normalize_path",
    "get_app_data_dir",
    "get_database_path",
    "fuzzy_match_projects",
    "calculate_similarity",
]
