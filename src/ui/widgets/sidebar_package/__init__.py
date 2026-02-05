"""Sidebar widget package.

Note: This package is for future refactoring. Currently, the old sidebar.py
file is still being used. The section modules are stubs for future implementation.
"""

# Don't import Sidebar here to avoid conflicts with sidebar.py
# from .sidebar import Sidebar

# Section modules are available but not required for current functionality
try:
    from .backups_section import BackupsSection
    from .collections_section import CollectionsSection
    from .live_section import LiveSection
    from .locations_section import LocationsSection
    from .navigation_section import NavigationSection
    from .tags_section import TagsSection
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
