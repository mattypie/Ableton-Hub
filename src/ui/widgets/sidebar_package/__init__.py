"""Sidebar widget package.

Note: This package is for future refactoring. Currently, the old sidebar.py
file is still being used. The section modules are stubs for future implementation.
"""

# Don't import Sidebar here to avoid conflicts with sidebar.py
# from .sidebar import Sidebar

# Section modules are available but not required for current functionality
try:
    from .navigation_section import NavigationSection
    from .locations_section import LocationsSection
    from .collections_section import CollectionsSection
    from .tags_section import TagsSection
    from .live_section import LiveSection
    from .backups_section import BackupsSection
except ImportError:
    # If sections don't exist yet, that's okay
    NavigationSection = None
    LocationsSection = None
    CollectionsSection = None
    TagsSection = None
    LiveSection = None
    BackupsSection = None

__all__ = [
    # "Sidebar",  # Not exported to avoid conflict
    "NavigationSection",
    "LocationsSection",
    "CollectionsSection",
    "TagsSection",
    "LiveSection",
    "BackupsSection",
]
