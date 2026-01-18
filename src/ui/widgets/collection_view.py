"""Collection management view widget."""

from typing import Optional, List
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon

from ...database import get_session, Collection, CollectionType, ProjectCollection, Project
from sqlalchemy.orm import joinedload
from ..theme import AbletonTheme


class CollectionCard(QFrame):
    """Card widget for a collection in grid view."""
    
    clicked = pyqtSignal(int)  # Collection ID
    edit_requested = pyqtSignal(int)  # Collection ID
    
    def __init__(self, collection: Collection, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.collection = collection
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the card UI."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedSize(200, 240)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setStyleSheet(f"""
            CollectionCard {{
                background-color: {AbletonTheme.COLORS['surface']};
                border: 1px solid {AbletonTheme.COLORS['border']};
                border-radius: 8px;
            }}
            CollectionCard:hover {{
                background-color: {AbletonTheme.COLORS['surface_hover']};
                border-color: {AbletonTheme.COLORS['border_light']};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Artwork placeholder
        self.artwork = QLabel()
        self.artwork.setFixedSize(176, 120)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setStyleSheet(f"""
            QLabel {{
                background-color: {AbletonTheme.COLORS['surface_light']};
                border-radius: 6px;
                font-size: 48px;
            }}
        """)
        
        # Show artwork or icon
        if self.collection.artwork_path:
            pixmap = QPixmap(self.collection.artwork_path)
            if not pixmap.isNull():
                self.artwork.setPixmap(pixmap.scaled(
                    176, 120, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self._set_default_icon()
        else:
            self._set_default_icon()
        
        layout.addWidget(self.artwork)
        
        # Collection name
        name_label = QLabel(self.collection.name)
        name_label.setWordWrap(True)
        font = AbletonTheme.safe_font_modify(name_label.font(), bold=True, pixel_size=16)
        name_label.setFont(font)
        layout.addWidget(name_label)
        
        # Type and track count
        type_icon = "⚡" if self.collection.is_smart else self._get_type_icon()
        if self.collection.is_smart:
            # For smart collections, show dynamic count
            from ...services.smart_collections import SmartCollectionService
            matching_ids = SmartCollectionService.evaluate_smart_collection(self.collection.id)
            track_count = len(matching_ids) + len(self.collection.project_collections)
        else:
            track_count = len(self.collection.project_collections)
        info_label = QLabel(f"{type_icon} {self.collection.collection_type.value.title()} • {track_count} tracks")
        info_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def _set_default_icon(self) -> None:
        """Set default icon based on collection type."""
        icon_map = {
            CollectionType.ALBUM: "💿",
            CollectionType.EP: "📀",
            CollectionType.SINGLE: "🎵",
            CollectionType.COMPILATION: "📚",
            CollectionType.SESSION: "🎤",
            CollectionType.CLIENT: "💼",
            CollectionType.CUSTOM: "📁",
        }
        icon = icon_map.get(self.collection.collection_type, "📁")
        self.artwork.setText(icon)
    
    def _get_type_icon(self) -> str:
        """Get icon for collection type."""
        icon_map = {
            CollectionType.ALBUM: "💿",
            CollectionType.EP: "📀",
            CollectionType.SINGLE: "🎵",
            CollectionType.COMPILATION: "📚",
            CollectionType.SESSION: "🎤",
            CollectionType.CLIENT: "💼",
            CollectionType.CUSTOM: "📁",
        }
        return icon_map.get(self.collection.collection_type, "📁")
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.collection.id)
        super().mousePressEvent(event)
    
    def _on_context_menu(self, pos) -> None:
        """Show context menu for collection card."""
        menu = QMenu(self)
        
        edit_action = menu.addAction("Edit Collection...")
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.collection.id))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("Delete Collection")
        delete_action.triggered.connect(lambda: self._delete_collection())
        
        menu.exec(self.mapToGlobal(pos))
    
    def _delete_collection(self) -> None:
        """Delete this collection."""
        result = QMessageBox.question(
            self,
            "Delete Collection",
            f"Are you sure you want to delete '{self.collection.name}'?\n\n"
            "This will remove the collection but not the projects in it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                collection = session.query(Collection).get(self.collection.id)
                if collection:
                    session.delete(collection)
                    session.commit()
                    # Emit signal to refresh - find CollectionView parent
                    parent = self.parent()
                    while parent:
                        if hasattr(parent, 'refresh') and isinstance(parent, CollectionView):
                            parent.refresh()
                            break
                        parent = parent.parent()
            finally:
                session.close()


class CollectionDetailView(QWidget):
    """Detailed view of a single collection with track listing."""
    
    back_requested = pyqtSignal()
    project_selected = pyqtSignal(int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._collection: Optional[Collection] = None
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the detail view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header row
        header = QHBoxLayout()
        
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        header.addStretch()
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._on_edit)
        header.addWidget(edit_btn)
        
        layout.addLayout(header)
        
        # Collection info
        info_layout = QHBoxLayout()
        
        # Artwork
        self.artwork = QLabel()
        self.artwork.setFixedSize(200, 200)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setStyleSheet(f"""
            QLabel {{
                background-color: {AbletonTheme.COLORS['surface_light']};
                border-radius: 8px;
            }}
        """)
        info_layout.addWidget(self.artwork)
        
        # Details
        details = QVBoxLayout()
        
        self.name_label = QLabel()
        self.name_label.setStyleSheet(f"font-size: 24px; font-weight: bold;")
        details.addWidget(self.name_label)
        
        self.type_label = QLabel()
        self.type_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        details.addWidget(self.type_label)
        
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        details.addWidget(self.description_label)
        
        details.addStretch()
        
        self.stats_label = QLabel()
        details.addWidget(self.stats_label)
        
        info_layout.addLayout(details)
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        
        # Track list
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(6)
        self.track_table.setHorizontalHeaderLabels([
            "#", "Artwork", "Track Name", "Project File", "Export", "Actions"
        ])
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.setShowGrid(False)
        self.track_table.verticalHeader().setVisible(False)
        
        # Enable drag and drop for reordering
        self.track_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.track_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.track_table.setDragEnabled(True)
        self.track_table.setAcceptDrops(True)
        self.track_table.setDropIndicatorShown(True)
        
        # Make track name column editable
        self.track_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        
        header = self.track_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.track_table.cellDoubleClicked.connect(self._on_track_double_click)
        self.track_table.cellChanged.connect(self._on_track_name_changed)
        self.track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_table.customContextMenuRequested.connect(self._on_track_context_menu)
        
        # Handle drop event for reordering
        self.track_table.model().rowsMoved.connect(self._on_tracks_reordered)
        
        layout.addWidget(self.track_table)
    
    def set_collection(self, collection_id: int) -> None:
        """Load and display a collection."""
        session = get_session()
        try:
            # Eagerly load relationships
            self._collection = session.query(Collection).options(
                joinedload(Collection.project_collections).joinedload(ProjectCollection.project).joinedload(Project.location),
                joinedload(Collection.project_collections).joinedload(ProjectCollection.project).joinedload(Project.exports)
            ).get(collection_id)
            if self._collection:
                self._update_display()
        finally:
            session.close()
    
    def _update_display(self) -> None:
        """Update the display with collection data."""
        if not self._collection:
            # Show empty state
            self.name_label.setText("Collection not found")
            self.type_label.setText("")
            self.description_label.setText("")
            self.artwork_label.setText("📁")
            self.track_table.setRowCount(0)
            return
        
        # Name
        self.name_label.setText(self._collection.name)
        
        # Type
        self.type_label.setText(
            f"{self._collection.collection_type.value.title()}"
            + (f" • {self._collection.release_date.strftime('%Y')}" if self._collection.release_date else "")
        )
        
        # Description
        self.description_label.setText(self._collection.description or "")
        
        # Artwork
        if self._collection.artwork_path:
            pixmap = QPixmap(self._collection.artwork_path)
            if not pixmap.isNull():
                self.artwork.setPixmap(pixmap.scaled(
                    200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
        else:
            icon_map = {
                CollectionType.ALBUM: "💿",
                CollectionType.EP: "📀",
                CollectionType.SINGLE: "🎵",
            }
            self.artwork.setText(icon_map.get(self._collection.collection_type, "📁"))
            self.artwork.setStyleSheet(self.artwork.styleSheet() + "font-size: 64px;")
        
        # Stats
        track_count = len(self._collection.project_collections)
        export_count = 0
        try:
            export_count = sum(
                1 for pc in self._collection.project_collections 
                if pc.project and hasattr(pc.project, 'exports') and pc.project.exports
            )
        except Exception:
            # If relationships are detached, skip export count
            pass
        self.stats_label.setText(f"{track_count} tracks • {export_count} exported")
        
        # Track list
        self._populate_tracks()
    
    def _populate_tracks(self) -> None:
        """Populate the track list table."""
        if not self._collection:
            return
        
        # Disconnect cellChanged to prevent triggering during population
        self.track_table.cellChanged.disconnect()
        
        pcs = sorted(
            self._collection.project_collections,
            key=lambda x: (x.disc_number or 1, x.track_number or 999)
        )
        
        self.track_table.setRowCount(len(pcs))
        
        for row, pc in enumerate(pcs):
            # Track number (editable for reordering)
            track_num = str(pc.track_number) if pc.track_number else str(row + 1)
            track_num_item = QTableWidgetItem(track_num)
            track_num_item.setData(Qt.ItemDataRole.UserRole, pc.id)  # Store ProjectCollection ID
            track_num_item.setFlags(track_num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 0, track_num_item)
            
            # Artwork column
            artwork_item = QTableWidgetItem()
            if pc.track_artwork_path and Path(pc.track_artwork_path).exists():
                pixmap = QPixmap(pc.track_artwork_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    artwork_item.setIcon(icon)
            else:
                artwork_item.setText("📷")
            artwork_item.setData(Qt.ItemDataRole.UserRole, pc.id)
            artwork_item.setFlags(artwork_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.track_table.setItem(row, 1, artwork_item)
            
            # Track name (editable - uses track_name from ProjectCollection, fallback to project name)
            if pc.project:
                track_name = pc.track_name or pc.project.export_song_name or pc.project.name
                name_item = QTableWidgetItem(track_name)
                name_item.setData(Qt.ItemDataRole.UserRole, pc.id)  # Store ProjectCollection ID
                name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 2, name_item)
                
                # Project file
                project_item = QTableWidgetItem(pc.project.name)
                project_item.setData(Qt.ItemDataRole.UserRole, pc.project.id)
                project_item.setFlags(project_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 3, project_item)
                
                # Export status
                try:
                    has_export = bool(pc.project.exports) if hasattr(pc.project, 'exports') else False
                except Exception:
                    has_export = False
                export_item = QTableWidgetItem("✓" if has_export else "")
                export_item.setFlags(export_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 4, export_item)
            else:
                name_item = QTableWidgetItem("[Missing]")
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.track_table.setItem(row, 2, name_item)
                self.track_table.setItem(row, 3, QTableWidgetItem(""))
                self.track_table.setItem(row, 4, QTableWidgetItem(""))
            
            # Actions column with buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            artwork_btn = QPushButton("🖼️")
            artwork_btn.setFixedSize(24, 24)
            artwork_btn.setToolTip("Set track artwork")
            artwork_btn.clicked.connect(lambda checked, pc_id=pc.id: self._set_track_artwork(pc_id))
            actions_layout.addWidget(artwork_btn)
            
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(24, 24)
            remove_btn.setToolTip("Remove from collection")
            remove_btn.clicked.connect(lambda checked, pc_id=pc.id: self._remove_track(pc_id))
            actions_layout.addWidget(remove_btn)
            
            self.track_table.setCellWidget(row, 5, actions_widget)
        
        # Reconnect cellChanged
        self.track_table.cellChanged.connect(self._on_track_name_changed)
    
    def _on_track_double_click(self, row: int, col: int) -> None:
        """Handle track double click."""
        if col == 3:  # Project file column
            item = self.track_table.item(row, 3)
            if item:
                project_id = item.data(Qt.ItemDataRole.UserRole)
                if project_id:
                    self.project_selected.emit(project_id)
        elif col == 2:  # Track name column - start editing
            self.track_table.editItem(self.track_table.item(row, 2))
    
    def _on_track_name_changed(self, row: int, col: int) -> None:
        """Handle track name edit."""
        if col == 2:  # Track name column
            item = self.track_table.item(row, 2)
            if item:
                pc_id = item.data(Qt.ItemDataRole.UserRole)
                new_name = item.text().strip()
                
                from ...database import get_session, ProjectCollection
                session = get_session()
                try:
                    pc = session.query(ProjectCollection).get(pc_id)
                    if pc:
                        pc.track_name = new_name if new_name else None
                        session.commit()
                finally:
                    session.close()
    
    def _on_track_context_menu(self, pos) -> None:
        """Show context menu for track."""
        item = self.track_table.itemAt(pos)
        if not item:
            return
        
        row = item.row()
        pc_id_item = self.track_table.item(row, 0)
        if not pc_id_item:
            return
        
        pc_id = pc_id_item.data(Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        
        edit_name_action = menu.addAction("Edit Track Name")
        edit_name_action.triggered.connect(lambda: self.track_table.editItem(self.track_table.item(row, 2)))
        
        artwork_action = menu.addAction("Set Track Artwork...")
        artwork_action.triggered.connect(lambda: self._set_track_artwork(pc_id))
        
        remove_artwork_action = menu.addAction("Remove Track Artwork")
        remove_artwork_action.triggered.connect(lambda: self._remove_track_artwork(pc_id))
        
        menu.addSeparator()
        
        move_up_action = menu.addAction("Move Up")
        move_up_action.triggered.connect(lambda: self._move_track(pc_id, -1))
        move_up_action.setEnabled(row > 0)
        
        move_down_action = menu.addAction("Move Down")
        move_down_action.triggered.connect(lambda: self._move_track(pc_id, 1))
        move_down_action.setEnabled(row < self.track_table.rowCount() - 1)
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Remove from Collection")
        remove_action.triggered.connect(lambda: self._remove_track(pc_id))
        
        menu.exec(self.track_table.viewport().mapToGlobal(pos))
    
    def _set_track_artwork(self, pc_id: int) -> None:
        """Set artwork for a track."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Track Artwork",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if path:
            from ...database import get_session, ProjectCollection
            session = get_session()
            try:
                pc = session.query(ProjectCollection).get(pc_id)
                if pc:
                    pc.track_artwork_path = path
                    session.commit()
                    self._populate_tracks()  # Refresh to show new artwork
            finally:
                session.close()
    
    def _remove_track_artwork(self, pc_id: int) -> None:
        """Remove artwork from a track."""
        from ...database import get_session, ProjectCollection
        session = get_session()
        try:
            pc = session.query(ProjectCollection).get(pc_id)
            if pc:
                pc.track_artwork_path = None
                session.commit()
                self._populate_tracks()
        finally:
            session.close()
    
    def _move_track(self, pc_id: int, direction: int) -> None:
        """Move a track up or down in the collection."""
        from ...database import get_session, ProjectCollection
        
        session = get_session()
        try:
            pc = session.query(ProjectCollection).get(pc_id)
            if not pc or not self._collection:
                return
            
            # Get all tracks sorted
            all_pcs = sorted(
                self._collection.project_collections,
                key=lambda x: (x.disc_number or 1, x.track_number or 999)
            )
            
            current_index = next((i for i, p in enumerate(all_pcs) if p.id == pc_id), None)
            if current_index is None:
                return
            
            new_index = current_index + direction
            if new_index < 0 or new_index >= len(all_pcs):
                return
            
            # Swap track numbers
            other_pc = all_pcs[new_index]
            pc_track = pc.track_number or (current_index + 1)
            other_track = other_pc.track_number or (new_index + 1)
            
            pc.track_number = other_track
            other_pc.track_number = pc_track
            
            session.commit()
            self._populate_tracks()
            
        finally:
            session.close()
    
    def _remove_track(self, pc_id: int) -> None:
        """Remove a track from the collection."""
        from ...database import get_session, ProjectCollection
        
        result = QMessageBox.question(
            self,
            "Remove Track",
            "Are you sure you want to remove this track from the collection?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            session = get_session()
            try:
                pc = session.query(ProjectCollection).get(pc_id)
                if pc:
                    session.delete(pc)
                    session.commit()
                    self._populate_tracks()
            finally:
                session.close()
    
    def _on_tracks_reordered(self, parent, start, end, destination, row) -> None:
        """Handle track reordering via drag and drop."""
        if not self._collection:
            return
        
        from ...database import get_session, ProjectCollection
        
        session = get_session()
        try:
            # Get all ProjectCollection entries for this collection
            all_pcs = session.query(ProjectCollection).filter(
                ProjectCollection.collection_id == self._collection.id
            ).order_by(ProjectCollection.track_number).all()
            
            # Reorder track numbers based on new table order
            for row_idx in range(self.track_table.rowCount()):
                item = self.track_table.item(row_idx, 0)
                if item:
                    pc_id = item.data(Qt.ItemDataRole.UserRole)
                    pc = next((p for p in all_pcs if p.id == pc_id), None)
                    if pc:
                        pc.track_number = row_idx + 1
            
            session.commit()
            # Refresh to update display
            QTimer.singleShot(100, self._populate_tracks)
            
        finally:
            session.close()
    
    def _on_edit(self) -> None:
        """Show edit collection dialog."""
        if self._collection:
            session = get_session()
            try:
                # Reload collection to check if it's smart
                collection = session.query(Collection).get(self._collection.id)
                if collection:
                    if collection.is_smart:
                        # Edit smart collection
                        from ..dialogs.smart_collection import SmartCollectionDialog
                        dialog = SmartCollectionDialog(self, collection_id=collection.id)
                    else:
                        # Edit regular collection
                        from ..dialogs.create_collection import CreateCollectionDialog
                        dialog = CreateCollectionDialog(self, collection_id=collection.id)
                    
                    if dialog.exec():
                        self.set_collection(collection.id)
                        # Refresh parent view if available
                        if hasattr(self.parent(), 'refresh'):
                            self.parent().refresh()
            finally:
                session.close()


class CollectionView(QWidget):
    """Main collection view with grid and detail views."""
    
    collection_selected = pyqtSignal(int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._collections: List[Collection] = []
        self._cards: dict = {}
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the collection view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Stack for grid vs detail view
        self.stack = QStackedWidget()
        
        # Grid view
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(16, 16, 16, 16)
        grid_layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel("Collections")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold;")
        header.addWidget(title)
        
        header.addStretch()
        
        new_btn = QPushButton("+ New Collection")
        new_btn.setObjectName("primary")
        new_btn.clicked.connect(self._on_new_collection)
        header.addWidget(new_btn)
        
        grid_layout.addLayout(header)
        
        # Grid scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        scroll.setWidget(self.grid_container)
        grid_layout.addWidget(scroll)
        
        self.stack.addWidget(grid_widget)
        
        # Detail view
        self.detail_view = CollectionDetailView()
        self.detail_view.back_requested.connect(lambda: self.stack.setCurrentIndex(0))
        self.detail_view.project_selected.connect(self.collection_selected.emit)
        self.stack.addWidget(self.detail_view)
        
        layout.addWidget(self.stack)
    
    def set_collection(self, collection_id: int) -> None:
        """Switch to detail view and load a specific collection."""
        self.detail_view.set_collection(collection_id)
        self.stack.setCurrentIndex(1)  # Switch to detail view
    
    def refresh(self) -> None:
        """Refresh collections from database."""
        session = get_session()
        try:
            self._collections = session.query(Collection).order_by(
                Collection.sort_order, Collection.name
            ).all()
            self._populate_grid()
        finally:
            session.close()
    
    def _populate_grid(self) -> None:
        """Populate the grid with collection cards."""
        # Clear existing
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add cards
        columns = 4
        for idx, coll in enumerate(self._collections):
            card = CollectionCard(coll)
            card.clicked.connect(self._on_collection_clicked)
            
            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)
            self._cards[coll.id] = card
    
    def _on_collection_clicked(self, collection_id: int) -> None:
        """Handle collection card click."""
        self.detail_view.set_collection(collection_id)
        self.stack.setCurrentIndex(1)
    
    def _on_edit_collection(self, collection_id: int) -> None:
        """Edit a collection from context menu."""
        session = get_session()
        try:
            collection = session.query(Collection).get(collection_id)
            if collection:
                if collection.is_smart:
                    # Edit smart collection
                    from ..dialogs.smart_collection import SmartCollectionDialog
                    dialog = SmartCollectionDialog(self, collection_id=collection_id)
                else:
                    # Edit regular collection
                    from ..dialogs.create_collection import CreateCollectionDialog
                    dialog = CreateCollectionDialog(self, collection_id=collection_id)
                
                if dialog.exec():
                    self.refresh()
                    # If we're viewing this collection, refresh the detail view
                    if hasattr(self.detail_view, '_collection') and self.detail_view._collection and self.detail_view._collection.id == collection_id:
                        self.detail_view.set_collection(collection_id)
        finally:
            session.close()
    
    def _on_new_collection(self) -> None:
        """Show new collection dialog."""
        from ..dialogs.create_collection import CreateCollectionDialog
        dialog = CreateCollectionDialog(self)
        if dialog.exec():
            self.refresh()
