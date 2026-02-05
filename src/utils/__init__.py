"""Utilities module - Helper functions and cross-platform utilities."""

from .fuzzy_match import calculate_similarity, fuzzy_match_projects
from .paths import (
    get_app_data_dir,
    get_database_path,
    get_default_locations,
    normalize_path,
)

__all__ = [
    "get_default_locations",
    "normalize_path",
    "get_app_data_dir",
    "get_database_path",
    "fuzzy_match_projects",
    "calculate_similarity",
]
