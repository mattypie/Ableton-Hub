"""Create/Edit collection dialog."""

from datetime import date
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...database import Collection, CollectionType, get_session
from ..theme import AbletonTheme


class CreateCollectionDialog(QDialog):
    """Dialog for creating or editing a collection."""

    def __init__(self, parent=None, collection_id: int | None = None):
        super().__init__(parent)

        self.collection_id = collection_id
        self._color = AbletonTheme.COLORS["accent"]
        self._artwork_path: str | None = None

        self.setWindowTitle("Edit Collection" if collection_id else "New Collection")
        self.setMinimumWidth(500)

        # Ensure dialog has a valid font
        font = self.font()
        if font.pointSize() <= 0:
            font.setPixelSize(12)
            self.setFont(font)

        self._setup_ui()

        if collection_id:
            self._load_collection()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Artwork and name row
        top_row = QHBoxLayout()

        # Artwork
        self.artwork_label = QLabel()
        self.artwork_label.setFixedSize(120, 120)
        self.artwork_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AbletonTheme.COLORS['surface_light']};
                border: 2px dashed {AbletonTheme.COLORS['border']};
                border-radius: 8px;
                font-size: 32px;
            }}
        """)
        self.artwork_label.setText("📁")
        self.artwork_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.artwork_label.mousePressEvent = lambda e: self._choose_artwork()
        top_row.addWidget(self.artwork_label)

        # Name and type
        name_form = QVBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Collection Name")
        self.name_input.setStyleSheet("font-size: 18px; font-weight: bold;")
        name_form.addWidget(self.name_input)

        # Type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))

        self.type_combo = QComboBox()
        for ct in CollectionType:
            icon_map = {
                CollectionType.ALBUM: "💿",
                CollectionType.EP: "📀",
                CollectionType.SINGLE: "🎵",
                CollectionType.COMPILATION: "📚",
                CollectionType.SESSION: "🎤",
                CollectionType.CLIENT: "💼",
                CollectionType.CUSTOM: "📁",
            }
            icon = icon_map.get(ct, "📁")
            self.type_combo.addItem(f"{icon} {ct.value.title()}", ct.value)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()

        name_form.addLayout(type_row)
        name_form.addStretch()

        top_row.addLayout(name_form)

        layout.addLayout(top_row)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional description...")
        self.description_input.setMaximumHeight(80)
        form.addRow("Description:", self.description_input)

        # Release date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        date_row = QHBoxLayout()
        self.date_checkbox = QCheckBox()
        self.date_checkbox.setChecked(False)
        self.date_checkbox.stateChanged.connect(
            lambda state: self.date_edit.setEnabled(state == Qt.CheckState.Checked.value)
        )
        date_row.addWidget(self.date_checkbox)
        date_row.addWidget(self.date_edit)
        date_row.addStretch()
        self.date_edit.setEnabled(False)

        form.addRow("Release Date:", date_row)

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

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_collection(self) -> None:
        """Load existing collection data."""
        session = get_session()
        try:
            collection = session.query(Collection).get(self.collection_id)
            if collection:
                self.name_input.setText(collection.name)
                self.description_input.setText(collection.description or "")

                # Type
                type_idx = [ct.value for ct in CollectionType].index(
                    collection.collection_type.value
                )
                self.type_combo.setCurrentIndex(type_idx)

                # Date
                if collection.release_date:
                    self.date_checkbox.setChecked(True)
                    self.date_edit.setDate(
                        QDate(
                            collection.release_date.year,
                            collection.release_date.month,
                            collection.release_date.day,
                        )
                    )

                # Color
                if collection.color:
                    self._color = collection.color
                    self._update_color_preview()

                # Artwork
                if collection.artwork_path:
                    self._artwork_path = collection.artwork_path
                    self._update_artwork_preview()
        finally:
            session.close()

    def _choose_artwork(self) -> None:
        """Show file dialog to choose artwork."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Artwork", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if path:
            self._artwork_path = path
            self._update_artwork_preview()

    def _update_artwork_preview(self) -> None:
        """Update the artwork preview."""
        if self._artwork_path:
            pixmap = QPixmap(self._artwork_path)
            if not pixmap.isNull():
                self.artwork_label.setPixmap(
                    pixmap.scaled(
                        120,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        # Show default icon
        self.artwork_label.setText("📁")

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

    def _on_accept(self) -> None:
        """Handle accept button."""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a collection name.")
            return

        # Get type
        type_value = self.type_combo.currentData()
        coll_type = CollectionType(type_value)

        # Get date
        release_date = None
        if self.date_checkbox.isChecked():
            qdate = self.date_edit.date()
            release_date = date(qdate.year(), qdate.month(), qdate.day())

        session = get_session()
        try:
            if self.collection_id:
                # Update existing
                collection = session.query(Collection).get(self.collection_id)
                if collection:
                    collection.name = name
                    collection.description = self.description_input.toPlainText().strip() or None
                    collection.collection_type = coll_type
                    collection.release_date = release_date
                    collection.color = self._color
                    collection.artwork_path = self._artwork_path
            else:
                # Create new
                collection = Collection(
                    name=name,
                    description=self.description_input.toPlainText().strip() or None,
                    collection_type=coll_type,
                    release_date=release_date,
                    color=self._color,
                    artwork_path=self._artwork_path,
                )
                session.add(collection)

            session.commit()
            # Flush to ensure ID is available
            session.flush()
            # Set collection_id - for new collections, this will be the new ID
            if not self.collection_id:
                self.collection_id = collection.id
            self.accept()
        finally:
            session.close()
