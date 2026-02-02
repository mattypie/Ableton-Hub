"""Dialog for browsing and selecting exports to link to a project."""

from typing import List, Optional
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QFileDialog,
    QAbstractItemView, QSplitter
)
from PyQt6.QtCore import Qt

from ...database import get_session, Project, Export
from ...services.export_tracker import ExportTracker
from ..theme import AbletonTheme

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.aiff', '.aif', '.ogg', '.m4a'}


class SelectExportsDialog(QDialog):
    """Dialog for browsing and selecting exports to link to a project."""
    
    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        
        self.project_id = project_id
        self.selected_export_ids: List[int] = []
        self._tracker = ExportTracker()
        
        self.setWindowTitle("Select Exports")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._load_existing_exports()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Info label
        info_label = QLabel(
            "Browse and select one or multiple export files to link to this project.\n"
            "You can select existing exports from the database or browse for new files."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']}; padding: 8px;")
        layout.addWidget(info_label)
        
        # Splitter for two-column layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Existing exports from database
        existing_group = QGroupBox("Existing Exports")
        existing_group.setStyleSheet(self._group_box_style())
        existing_layout = QVBoxLayout(existing_group)
        
        existing_info = QLabel("Exports already in database (may be unlinked):")
        existing_info.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        existing_layout.addWidget(existing_info)
        
        self.existing_list = QListWidget()
        self.existing_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.existing_list.setAlternatingRowColors(True)
        existing_layout.addWidget(self.existing_list)
        
        existing_buttons = QHBoxLayout()
        link_selected_btn = QPushButton("Link Selected")
        link_selected_btn.clicked.connect(self._link_selected_existing)
        existing_buttons.addWidget(link_selected_btn)
        existing_buttons.addStretch()
        existing_layout.addLayout(existing_buttons)
        
        splitter.addWidget(existing_group)
        
        # Right: Browse for new files
        browse_group = QGroupBox("Browse for Files")
        browse_group.setStyleSheet(self._group_box_style())
        browse_layout = QVBoxLayout(browse_group)
        
        browse_info = QLabel("Select audio files from your file system:")
        browse_info.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        browse_layout.addWidget(browse_info)
        
        self.browsed_list = QListWidget()
        self.browsed_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.browsed_list.setAlternatingRowColors(True)
        browse_layout.addWidget(self.browsed_list)
        
        browse_buttons = QHBoxLayout()
        browse_files_btn = QPushButton("Browse Files...")
        browse_files_btn.clicked.connect(self._browse_files)
        browse_buttons.addWidget(browse_files_btn)
        browse_buttons.addStretch()
        browse_layout.addLayout(browse_buttons)
        
        splitter.addWidget(browse_group)
        
        # Set splitter sizes (equal)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # Selected exports summary
        summary_group = QGroupBox("Selected Exports")
        summary_group.setStyleSheet(self._group_box_style())
        summary_layout = QVBoxLayout(summary_group)
        
        self.selected_list = QListWidget()
        self.selected_list.setMaximumHeight(120)
        self.selected_list.setAlternatingRowColors(True)
        summary_layout.addWidget(self.selected_list)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        summary_layout.addWidget(remove_btn)
        
        layout.addWidget(summary_group)
        
        # Buttons
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Link Exports")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_accept)
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
    
    def _group_box_style(self) -> str:
        """Return consistent group box styling."""
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {AbletonTheme.COLORS['border']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: {AbletonTheme.COLORS['surface']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: {AbletonTheme.COLORS['text_primary']};
            }}
        """
    
    def _load_existing_exports(self) -> None:
        """Load existing exports from database."""
        session = get_session()
        try:
            # Get all exports, prioritizing unlinked ones
            all_exports = session.query(Export).order_by(
                Export.project_id.is_(None).desc(),  # Unlinked first
                Export.export_date.desc()
            ).all()
            
            self.existing_list.clear()
            
            for export in all_exports:
                # Check if file still exists
                if not Path(export.export_path).exists():
                    continue
                
                # Format display text
                linked_status = ""
                if export.project_id:
                    if export.project_id == self.project_id:
                        linked_status = " (already linked)"
                    else:
                        project = session.query(Project).get(export.project_id)
                        if project:
                            linked_status = f" (linked to: {project.name})"
                
                date_str = ""
                if export.export_date:
                    date_str = export.export_date.strftime("%Y-%m-%d")
                
                size_str = ""
                if export.file_size:
                    size_mb = export.file_size / (1024 * 1024)
                    if size_mb < 1:
                        size_str = f" ({size_mb * 1024:.0f} KB)"
                    else:
                        size_str = f" ({size_mb:.2f} MB)"
                
                item_text = f"{export.export_name}{linked_status}"
                if date_str:
                    item_text += f" - {date_str}"
                item_text += size_str
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, export.id)
                item.setToolTip(export.export_path)
                
                # Disable if already linked to this project
                if export.project_id == self.project_id:
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setForeground(Qt.GlobalColor.gray)
                
                self.existing_list.addItem(item)
            
            if self.existing_list.count() == 0:
                item = QListWidgetItem("No exports found in database")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.existing_list.addItem(item)
                
        finally:
            session.close()
    
    def _browse_files(self) -> None:
        """Browse for audio files."""
        # Get project path for initial directory
        session = get_session()
        initial_dir = ""
        try:
            project = session.query(Project).get(self.project_id)
            if project:
                initial_dir = str(Path(project.file_path).parent)
        finally:
            session.close()
        
        # Open file dialog for multiple files
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Export Files",
            initial_dir,
            "Audio Files (*.wav *.mp3 *.flac *.aiff *.aif *.ogg *.m4a);;All Files (*.*)"
        )
        
        if not file_paths:
            return
        
        # Add to browsed list
        for file_path in file_paths:
            path = Path(file_path)
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            
            # Check if already in list
            already_added = False
            for i in range(self.browsed_list.count()):
                item = self.browsed_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == str(file_path):
                    already_added = True
                    break
            
            if not already_added:
                stat = path.stat()
                date_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                size_mb = stat.st_size / (1024 * 1024)
                if size_mb < 1:
                    size_str = f"{size_mb * 1024:.0f} KB"
                else:
                    size_str = f"{size_mb:.2f} MB"
                
                item_text = f"{path.stem} - {date_str} ({size_str})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, str(file_path))
                item.setToolTip(str(file_path))
                self.browsed_list.addItem(item)
    
    def _link_selected_existing(self) -> None:
        """Link selected existing exports to the project."""
        selected_items = self.existing_list.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self, "No Selection",
                "Please select one or more exports from the list."
            )
            return
        
        session = get_session()
        try:
            linked_count = 0
            for item in selected_items:
                export_id = item.data(Qt.ItemDataRole.UserRole)
                if export_id:
                    export = session.query(Export).get(export_id)
                    if export:
                        # Only link if not already linked to this project
                        if export.project_id != self.project_id:
                            export.project_id = self.project_id
                            linked_count += 1
                        # Add to selected list if not already there
                        if export_id not in self.selected_export_ids:
                            self.selected_export_ids.append(export_id)
                            self._add_to_selected_list(export)
            
            if linked_count > 0:
                session.commit()
                QMessageBox.information(
                    self, "Exports Linked",
                    f"Linked {linked_count} export(s) to this project."
                )
                self._load_existing_exports()
                self._update_selected_list()
            else:
                # Still update selected list even if already linked
                self._update_selected_list()
                QMessageBox.information(
                    self, "Exports Selected",
                    "Selected exports are already linked to this project."
                )
        finally:
            session.close()
    
    def _add_to_selected_list(self, export: Export) -> None:
        """Add an export to the selected list."""
        date_str = export.export_date.strftime("%Y-%m-%d") if export.export_date else ""
        size_str = ""
        if export.file_size:
            size_mb = export.file_size / (1024 * 1024)
            if size_mb < 1:
                size_str = f" ({size_mb * 1024:.0f} KB)"
            else:
                size_str = f" ({size_mb:.2f} MB)"
        
        item_text = f"{export.export_name}"
        if date_str:
            item_text += f" - {date_str}"
        item_text += size_str
        
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, export.id)
        item.setToolTip(export.export_path)
        self.selected_list.addItem(item)
    
    def _update_selected_list(self) -> None:
        """Update the selected exports list from selected_export_ids."""
        self.selected_list.clear()
        
        session = get_session()
        try:
            for export_id in self.selected_export_ids:
                export = session.query(Export).get(export_id)
                if export:
                    self._add_to_selected_list(export)
        finally:
            session.close()
    
    def _remove_selected(self) -> None:
        """Remove selected items from the selected list."""
        selected_items = self.selected_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            export_id = item.data(Qt.ItemDataRole.UserRole)
            if export_id and export_id in self.selected_export_ids:
                self.selected_export_ids.remove(export_id)
            row = self.selected_list.row(item)
            self.selected_list.takeItem(row)
    
    def _on_accept(self) -> None:
        """Handle accept - link browsed files and selected exports."""
        session = get_session()
        try:
            linked_count = 0
            
            # Link browsed files
            browsed_items = self.browsed_list.selectedItems()
            for item in browsed_items:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path:
                    # Add export to database and link to project
                    export_id = self._tracker.add_export(file_path, self.project_id)
                    if export_id and export_id not in self.selected_export_ids:
                        self.selected_export_ids.append(export_id)
                        linked_count += 1
            
            # Link selected existing exports
            existing_items = self.existing_list.selectedItems()
            for item in existing_items:
                export_id = item.data(Qt.ItemDataRole.UserRole)
                if export_id:
                    export = session.query(Export).get(export_id)
                    if export and export.project_id != self.project_id:
                        export.project_id = self.project_id
                        if export_id not in self.selected_export_ids:
                            self.selected_export_ids.append(export_id)
                        linked_count += 1
            
            if linked_count > 0:
                session.commit()
                QMessageBox.information(
                    self, "Exports Linked",
                    f"Successfully linked {linked_count} export(s) to this project."
                )
                self.accept()
            else:
                # Check if we have items in selected list
                if self.selected_list.count() > 0:
                    QMessageBox.information(
                        self, "Already Linked",
                        "Selected exports are already linked to this project."
                    )
                    self.accept()
                else:
                    QMessageBox.information(
                        self, "No Selection",
                        "Please select exports to link or browse for files."
                    )
        finally:
            session.close()
