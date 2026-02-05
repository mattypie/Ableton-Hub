"""Main sidebar widget - container for all sidebar sections."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from ...theme import AbletonTheme


class Sidebar(QWidget):
    """Main sidebar with navigation and filters."""

    # Signals (delegated from sections)
    navigation_changed = pyqtSignal(str)  # View name
    location_selected = pyqtSignal(int)  # Location ID
    location_delete_requested = pyqtSignal(int)  # Location ID
    cleanup_orphaned_projects_requested = pyqtSignal()
    auto_detect_live_versions_requested = pyqtSignal()
    add_manual_installation_requested = pyqtSignal()
    set_favorite_installation_requested = pyqtSignal(int)  # Installation ID
    remove_installation_requested = pyqtSignal(int)  # Installation ID
    collection_selected = pyqtSignal(int)  # Collection ID
    collection_edit_requested = pyqtSignal(int)  # Collection ID
    collection_delete_requested = pyqtSignal(int)  # Collection ID
    tag_selected = pyqtSignal(int)  # Tag ID

    def __init__(self, parent: QWidget | None = None):
        """Initialize the sidebar.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the sidebar UI."""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {AbletonTheme.COLORS['background_alt']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 12, 8, 12)
        content_layout.setSpacing(16)

        # Initialize sections (will be implemented in separate modules)
        # For now, delegate to the original implementation
        # This allows incremental migration

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        """Refresh all sidebar sections."""
        # Will delegate to section refresh methods
        pass

    def clear_selection(self) -> None:
        """Clear current selection."""
        pass
