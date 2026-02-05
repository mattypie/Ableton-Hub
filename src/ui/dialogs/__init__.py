"""UI Dialogs module - Modal dialog windows."""

from .add_live_installation import AddLiveInstallationDialog
from .add_location import AddLocationDialog
from .create_collection import CreateCollectionDialog
from .live_version_dialog import LiveVersionDialog
from .project_details import ProjectDetailsDialog
from .select_exports_dialog import SelectExportsDialog
from .similar_projects_dialog import SimilarProjectsDialog
from .smart_collection import SmartCollectionDialog

__all__ = [
    "AddLocationDialog",
    "CreateCollectionDialog",
    "ProjectDetailsDialog",
    "SmartCollectionDialog",
    "LiveVersionDialog",
    "AddLiveInstallationDialog",
    "SimilarProjectsDialog",
    "SelectExportsDialog",
]
