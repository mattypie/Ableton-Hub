"""Add/Edit location dialog."""

from typing import Optional
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QFileDialog,
    QDialogButtonBox, QMessageBox, QColorDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap

from ...database import get_session, Location, LocationType
from ...utils.paths import get_default_locations
from ..theme import AbletonTheme


class AddLocationDialog(QDialog):
    """Dialog for adding or editing a location."""
    
    def __init__(self, parent=None, location_id: Optional[int] = None):
        super().__init__(parent)
        
        self.location_id = location_id
        self._color = AbletonTheme.COLORS['accent']
        
        self.setWindowTitle("Edit Location" if location_id else "Add Location")
        self.setMinimumWidth(500)
        
        self._setup_ui()
        
        if location_id:
            self._load_location()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Form
        form = QFormLayout()
        form.setSpacing(12)
        
        # Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My Projects Folder")
        form.addRow("Name:", self.name_input)
        
        # Path
        path_row = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("C:\\Users\\...\\Ableton Projects")
        path_row.addWidget(self.path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        path_row.addWidget(browse_btn)
        
        form.addRow("Path:", path_row)
        
        # Type
        self.type_combo = QComboBox()
        self.type_combo.addItems([t.value.title() for t in LocationType])
        form.addRow("Type:", self.type_combo)
        
        # Color
        color_row = QHBoxLayout()
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(24, 24)
        self._update_color_preview()
        color_row.addWidget(self.color_preview)
        
        color_btn = QPushButton("Choose Color...")
        color_btn.clicked.connect(self._choose_color)
        color_row.addWidget(color_btn)
        
        color_row.addStretch()
        
        form.addRow("Color:", color_row)
        
        # Options
        self.active_checkbox = QCheckBox("Active (scan this location)")
        self.active_checkbox.setChecked(True)
        form.addRow("", self.active_checkbox)
        
        self.favorite_checkbox = QCheckBox("Add to favorites")
        form.addRow("", self.favorite_checkbox)
        
        layout.addLayout(form)
        
        # Suggested locations (only for new)
        if not self.location_id:
            suggestions = get_default_locations()
            if suggestions:
                layout.addWidget(QLabel("Suggested locations:"))
                
                for path in suggestions[:5]:  # Show max 5
                    suggest_btn = QPushButton(str(path))
                    suggest_btn.setFlat(True)
                    suggest_btn.setStyleSheet(f"""
                        QPushButton {{
                            text-align: left;
                            padding: 8px;
                            color: {AbletonTheme.COLORS['accent']};
                        }}
                        QPushButton:hover {{
                            text-decoration: underline;
                        }}
                    """)
                    suggest_btn.clicked.connect(
                        lambda checked, p=path: self._use_suggestion(p)
                    )
                    layout.addWidget(suggest_btn)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_location(self) -> None:
        """Load existing location data."""
        session = get_session()
        try:
            location = session.query(Location).get(self.location_id)
            if location:
                self.name_input.setText(location.name)
                self.path_input.setText(location.path)
                
                type_idx = [t.value for t in LocationType].index(location.location_type.value)
                self.type_combo.setCurrentIndex(type_idx)
                
                if location.color:
                    self._color = location.color
                    self._update_color_preview()
                
                self.active_checkbox.setChecked(location.is_active)
                self.favorite_checkbox.setChecked(location.is_favorite)
        finally:
            session.close()
    
    def _browse_folder(self) -> None:
        """Show folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Location Folder",
            self.path_input.text() or str(Path.home())
        )
        if folder:
            self.path_input.setText(folder)
            
            # Auto-fill name if empty
            if not self.name_input.text():
                self.name_input.setText(Path(folder).name)
    
    def _choose_color(self) -> None:
        """Show color picker dialog."""
        color = QColorDialog.getColor(QColor(self._color), self)
        if color.isValid():
            self._color = color.name()
            self._update_color_preview()
    
    def _update_color_preview(self) -> None:
        """Update the color preview widget."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(self._color))
        self.color_preview.setPixmap(pixmap)
    
    def _use_suggestion(self, path: Path) -> None:
        """Use a suggested path."""
        self.path_input.setText(str(path))
        self.name_input.setText(path.name)
    
    def _on_accept(self) -> None:
        """Handle accept button."""
        name = self.name_input.text().strip()
        path = self.path_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a name.")
            return
        
        if not path:
            QMessageBox.warning(self, "Error", "Please select a folder path.")
            return
        
        # Validate path exists
        if not Path(path).exists():
            result = QMessageBox.question(
                self,
                "Path Not Found",
                f"The path '{path}' does not exist. Add anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        
        # Get type
        type_value = self.type_combo.currentText().lower()
        loc_type = LocationType(type_value)
        
        session = get_session()
        try:
            if self.location_id:
                # Update existing
                location = session.query(Location).get(self.location_id)
                if location:
                    location.name = name
                    location.path = path
                    location.location_type = loc_type
                    location.color = self._color
                    location.is_active = self.active_checkbox.isChecked()
                    location.is_favorite = self.favorite_checkbox.isChecked()
            else:
                # Check for duplicate path
                existing = session.query(Location).filter(Location.path == path).first()
                if existing:
                    QMessageBox.warning(
                        self, "Error",
                        f"A location with this path already exists: '{existing.name}'"
                    )
                    return
                
                # Create new
                location = Location(
                    name=name,
                    path=path,
                    location_type=loc_type,
                    color=self._color,
                    is_active=self.active_checkbox.isChecked(),
                    is_favorite=self.favorite_checkbox.isChecked()
                )
                session.add(location)
            
            session.commit()
            self.location_id = location.id if not self.location_id else self.location_id
            self.accept()
        finally:
            session.close()
