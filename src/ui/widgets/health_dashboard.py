"""Project health dashboard widget."""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ...services.health_calculator import HealthCalculator
from ...services.duplicate_detector import DuplicateDetector
from ...database import get_session, Project
from ..theme import AbletonTheme


class HealthDashboard(QWidget):
    """Dashboard showing project health metrics and issues."""
    
    project_selected = pyqtSignal(int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()
    
    def _setup_ui(self) -> None:
        """Set up the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Project Health Dashboard")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold;")
        header.addWidget(title)
        
        header.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Summary cards
        self.summary_layout = QHBoxLayout()
        layout.addLayout(self.summary_layout)
        
        # Health distribution
        health_section = QVBoxLayout()
        health_label = QLabel("Health Distribution")
        health_label.setStyleSheet(f"font-size: 16px; font-weight: bold;")
        health_section.addWidget(health_label)
        
        self.excellent_bar = QProgressBar()
        self.excellent_bar.setFormat("Excellent: %p%")
        self.excellent_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {AbletonTheme.COLORS['success']}; }}")
        health_section.addWidget(self.excellent_bar)
        
        self.good_bar = QProgressBar()
        self.good_bar.setFormat("Good: %p%")
        self.good_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {AbletonTheme.COLORS['accent']}; }}")
        health_section.addWidget(self.good_bar)
        
        self.fair_bar = QProgressBar()
        self.fair_bar.setFormat("Fair: %p%")
        self.fair_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {AbletonTheme.COLORS['warning']}; }}")
        health_section.addWidget(self.fair_bar)
        
        self.poor_bar = QProgressBar()
        self.poor_bar.setFormat("Poor: %p%")
        self.poor_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {AbletonTheme.COLORS['error']}; }}")
        health_section.addWidget(self.poor_bar)
        
        layout.addLayout(health_section)
        
        # Issues table
        issues_label = QLabel("Projects with Issues")
        issues_label.setStyleSheet(f"font-size: 16px; font-weight: bold;")
        layout.addWidget(issues_label)
        
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(4)
        self.issues_table.setHorizontalHeaderLabels([
            "Project", "Health Score", "Issues", "Actions"
        ])
        self.issues_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.issues_table.setAlternatingRowColors(True)
        self.issues_table.setShowGrid(False)
        self.issues_table.verticalHeader().setVisible(False)
        
        header = self.issues_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.issues_table.cellDoubleClicked.connect(self._on_project_double_click)
        
        layout.addWidget(self.issues_table)
        
        # Duplicates section
        duplicates_label = QLabel("Duplicate Detection")
        duplicates_label.setStyleSheet(f"font-size: 16px; font-weight: bold;")
        layout.addWidget(duplicates_label)
        
        self.duplicates_table = QTableWidget()
        self.duplicates_table.setColumnCount(3)
        self.duplicates_table.setHorizontalHeaderLabels([
            "Type", "Projects", "Actions"
        ])
        self.duplicates_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.duplicates_table.setAlternatingRowColors(True)
        self.duplicates_table.setShowGrid(False)
        self.duplicates_table.verticalHeader().setVisible(False)
        
        header = self.duplicates_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.duplicates_table)
    
    def refresh(self) -> None:
        """Refresh the dashboard data."""
        self._update_summary()
        self._update_issues_table()
        self._update_duplicates_table()
    
    def _update_summary(self) -> None:
        """Update summary statistics."""
        summary = HealthCalculator.get_health_summary()
        
        self.excellent_bar.setMaximum(100)
        self.excellent_bar.setValue(int(summary.get('excellent_percent', 0)))
        
        self.good_bar.setMaximum(100)
        self.good_bar.setValue(int(summary.get('good_percent', 0)))
        
        self.fair_bar.setMaximum(100)
        self.fair_bar.setValue(int(summary.get('fair_percent', 0)))
        
        self.poor_bar.setMaximum(100)
        self.poor_bar.setValue(int(summary.get('poor_percent', 0)))
    
    def _update_issues_table(self) -> None:
        """Update the issues table with problematic projects."""
        # Get projects with health issues (score < 60)
        session = get_session()
        try:
            projects = session.query(Project).all()
            
            issues = []
            for project in projects:
                health = HealthCalculator.calculate_health_score(project.id)
                if health['score'] < 60 or health['issues']:
                    issues.append((project, health))
            
            # Sort by health score (lowest first)
            issues.sort(key=lambda x: x[1]['score'])
            
            self.issues_table.setRowCount(len(issues))
            
            for row, (project, health) in enumerate(issues):
                # Project name
                name_item = QTableWidgetItem(project.name)
                name_item.setData(Qt.ItemDataRole.UserRole, project.id)
                self.issues_table.setItem(row, 0, name_item)
                
                # Health score
                score_item = QTableWidgetItem(f"{health['score']}/100")
                score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if health['score'] < 40:
                    score_item.setForeground(QColor(255, 100, 100))
                elif health['score'] < 60:
                    score_item.setForeground(QColor(255, 200, 100))
                self.issues_table.setItem(row, 1, score_item)
                
                # Issues
                all_issues = health['issues'] + health['warnings']
                issues_text = ", ".join(all_issues[:3])  # Show first 3
                if len(all_issues) > 3:
                    issues_text += f" (+{len(all_issues) - 3} more)"
                self.issues_table.setItem(row, 2, QTableWidgetItem(issues_text))
                
                # Actions
                view_btn = QPushButton("View")
                view_btn.clicked.connect(lambda checked, pid=project.id: self.project_selected.emit(pid))
                self.issues_table.setCellWidget(row, 3, view_btn)
        finally:
            session.close()
    
    def _update_duplicates_table(self) -> None:
        """Update the duplicates table."""
        duplicates = DuplicateDetector.get_all_duplicates()
        
        rows = []
        
        # Exact duplicates
        for file_hash, project_ids in duplicates['exact']:
            rows.append(("Exact Duplicate", project_ids, file_hash))
        
        # Similar names
        for pid1, pid2, similarity in duplicates['similar_names'][:10]:  # Top 10
            rows.append(("Similar Name", [pid1, pid2], f"{similarity:.0%}"))
        
        # Location duplicates
        for name, project_ids in duplicates['location_duplicates'][:10]:  # Top 10
            rows.append(("Same Name (Different Locations)", project_ids, name))
        
        self.duplicates_table.setRowCount(len(rows))
        
        for row, (dup_type, project_ids, info) in enumerate(rows):
            self.duplicates_table.setItem(row, 0, QTableWidgetItem(dup_type))
            
            # Project names
            session = get_session()
            try:
                project_names = []
                for pid in project_ids[:3]:  # Show first 3
                    project = session.query(Project).get(pid)
                    if project:
                        project_names.append(project.name)
                if len(project_ids) > 3:
                    project_names.append(f" (+{len(project_ids) - 3} more)")
                names_text = ", ".join(project_names)
            finally:
                session.close()
            
            self.duplicates_table.setItem(row, 1, QTableWidgetItem(names_text))
            
            # Actions
            resolve_btn = QPushButton("Resolve")
            resolve_btn.clicked.connect(
                lambda checked, pids=project_ids: self._resolve_duplicates(pids)
            )
            self.duplicates_table.setCellWidget(row, 2, resolve_btn)
    
    def _on_project_double_click(self, row: int, col: int) -> None:
        """Handle project double click."""
        item = self.issues_table.item(row, 0)
        if item:
            project_id = item.data(Qt.ItemDataRole.UserRole)
            self.project_selected.emit(project_id)
    
    def _resolve_duplicates(self, project_ids: list) -> None:
        """Show dialog to resolve duplicates."""
        QMessageBox.information(
            self,
            "Resolve Duplicates",
            f"Found {len(project_ids)} duplicate projects.\n\n"
            "This feature will allow you to:\n"
            "- Keep one project and archive others\n"
            "- Merge metadata\n"
            "- Mark as intentional copies\n\n"
            "Full resolution wizard coming soon!"
        )
