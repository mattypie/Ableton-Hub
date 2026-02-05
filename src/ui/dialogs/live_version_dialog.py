"""Dialog for selecting Ableton Live version to open a project."""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...services.live_detector import LiveVersion
from ...services.live_launcher import LiveLauncher
from ..theme import AbletonTheme


class LiveVersionDialog(QDialog):
    """Dialog to select which Live version to use for opening a project."""

    def __init__(self, project_name: str, parent=None):
        super().__init__(parent)

        self.project_name = project_name
        self.selected_version: LiveVersion | None = None
        self._launcher = LiveLauncher()

        self._setup_ui()
        self._load_versions()
        # Set dialog to be modal
        self.setModal(True)
        self._parent = parent

    def showEvent(self, event):
        """Override showEvent to center dialog on parent window."""
        super().showEvent(event)
        if self._parent:
            # Ensure dialog is properly sized
            self.adjustSize()
            # Center on parent window
            parent_geometry = self._parent.geometry()
            dialog_geometry = self.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2
            self.move(x, y)

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Open with Ableton Live")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel(f"Open '{self.project_name}' with:")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {AbletonTheme.COLORS['text_primary']};"
        )
        layout.addWidget(title)

        # Version selection
        version_layout = QVBoxLayout()
        version_layout.setSpacing(8)

        version_label = QLabel("Select Ableton Live version:")
        version_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        version_layout.addWidget(version_label)

        self.version_combo = QComboBox()
        self.version_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AbletonTheme.COLORS['surface']};
                color: {AbletonTheme.COLORS['text_primary']};
                border: 1px solid {AbletonTheme.COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {AbletonTheme.COLORS['border_light']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {AbletonTheme.COLORS['surface']};
                color: {AbletonTheme.COLORS['text_primary']};
                selection-background-color: {AbletonTheme.COLORS['accent']};
                selection-color: {AbletonTheme.COLORS['text_on_accent']};
            }}
        """)
        version_layout.addWidget(self.version_combo)

        layout.addLayout(version_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AbletonTheme.COLORS['surface']};
                color: {AbletonTheme.COLORS['text_primary']};
                border: 1px solid {AbletonTheme.COLORS['border']};
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {AbletonTheme.COLORS['surface_hover']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        open_btn = QPushButton("Open")
        open_btn.setObjectName("primary")
        open_btn.setStyleSheet(f"""
            QPushButton#primary {{
                background-color: {AbletonTheme.COLORS['accent']};
                color: {AbletonTheme.COLORS['text_on_accent']};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton#primary:hover {{
                background-color: {AbletonTheme.COLORS['accent_hover']};
            }}
        """)
        open_btn.clicked.connect(self._on_open)
        button_layout.addWidget(open_btn)

        layout.addLayout(button_layout)

    def _load_versions(self) -> None:
        """Load available Live versions into the combo box."""
        versions = self._launcher.get_available_versions()

        if not versions:
            QMessageBox.warning(
                self,
                "No Live Versions Found",
                "No Ableton Live installations were detected.\n\n"
                "Please ensure Ableton Live is installed and try again.",
            )
            self.reject()
            return

        for version in versions:
            display_text = str(version)
            if version.path:
                # Add path hint for clarity
                path_str = str(version.path.parent)
                if len(path_str) > 50:
                    path_str = "..." + path_str[-47:]
                display_text += f" ({path_str})"

            self.version_combo.addItem(display_text, version)

        # Select first (newest) version by default
        if self.version_combo.count() > 0:
            self.version_combo.setCurrentIndex(0)

    def _on_open(self) -> None:
        """Handle Open button click."""
        if self.version_combo.count() == 0:
            return

        self.selected_version = self.version_combo.currentData()
        if self.selected_version:
            self.accept()

    def get_selected_version(self) -> LiveVersion | None:
        """Get the selected Live version."""
        return self.selected_version
