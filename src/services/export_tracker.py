"""Export file tracking and mapping service."""

from typing import Optional, List, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import os

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ..database import get_session, Project, Export
from ..utils.paths import find_export_folders
from ..utils.fuzzy_match import match_export_to_project, calculate_similarity


AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.aiff', '.aif', '.ogg', '.m4a'}


class ExportScanner(QThread):
    """Background worker for scanning export folders."""
    
    progress = pyqtSignal(str)           # Current folder
    export_found = pyqtSignal(str, str)  # Path, suggested project
    scan_complete = pyqtSignal(int)      # Total found
    
    def __init__(self, folders: List[Path], project_names: List[Tuple[int, str]]):
        """Initialize the scanner.
        
        Args:
            folders: List of folders to scan for exports.
            project_names: List of (id, name) tuples for matching.
        """
        super().__init__()
        
        self.folders = folders
        self.project_names = project_names
        self._stop_requested = False
        self._found_count = 0
    
    def run(self) -> None:
        """Execute the scan."""
        for folder in self.folders:
            if self._stop_requested:
                break
            
            self.progress.emit(str(folder))
            self._scan_folder(folder)
        
        self.scan_complete.emit(self._found_count)
    
    def _scan_folder(self, folder: Path) -> None:
        """Scan a folder for audio exports."""
        if not folder.exists():
            return
        
        try:
            for item in folder.iterdir():
                if self._stop_requested:
                    break
                
                if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
                    self._found_count += 1
                    
                    # Try to match to a project
                    names = [name for _, name in self.project_names]
                    matches = match_export_to_project(item.stem, names)
                    
                    suggested = ""
                    if matches:
                        best_match = matches[0]
                        if best_match[1] >= 70:  # 70% threshold
                            suggested = best_match[0]
                    
                    self.export_found.emit(str(item), suggested)
                    
                elif item.is_dir():
                    self._scan_folder(item)
                    
        except PermissionError:
            pass
    
    def stop(self) -> None:
        """Request stop."""
        self._stop_requested = True


class ExportTracker(QObject):
    """Service for tracking and mapping exports to projects."""
    
    # Signals
    export_found = pyqtSignal(str, str)   # Path, suggested project name
    mapping_created = pyqtSignal(int, int)  # Export ID, Project ID
    scan_complete = pyqtSignal(int)       # Total found
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._scanner: Optional[ExportScanner] = None
        self._export_folders: List[str] = []
    
    def set_export_folders(self, folders: List[str]) -> None:
        """Set the list of export folders to scan.
        
        Args:
            folders: List of folder paths.
        """
        self._export_folders = folders
    
    def scan_exports(self, project_id: Optional[int] = None) -> None:
        """Scan export folders for audio files.
        
        Args:
            project_id: If provided, only scan folders related to this project.
        """
        if self._scanner and self._scanner.isRunning():
            return
        
        session = get_session()
        try:
            # Get folders to scan
            folders: List[Path] = []
            
            if project_id:
                project = session.query(Project).get(project_id)
                if project:
                    folders = find_export_folders(Path(project.file_path))
            else:
                # Use configured export folders
                for folder in self._export_folders:
                    path = Path(folder)
                    if path.exists():
                        folders.append(path)
                
                # Also check project-relative folders
                for project in session.query(Project).all():
                    folders.extend(find_export_folders(Path(project.file_path)))
            
            # Get project names for matching
            projects = session.query(Project.id, Project.name).all()
            project_names = [(p.id, p.name) for p in projects]
            
            # Add export song names as alternatives
            for project in session.query(Project).filter(
                Project.export_song_name.isnot(None)
            ).all():
                project_names.append((project.id, project.export_song_name))
            
            # Start scan
            self._scanner = ExportScanner(list(set(folders)), project_names)
            self._scanner.export_found.connect(self._on_export_found)
            self._scanner.scan_complete.connect(self.scan_complete.emit)
            self._scanner.start()
            
        finally:
            session.close()
    
    def _on_export_found(self, path: str, suggested: str) -> None:
        """Handle export found during scan."""
        self.export_found.emit(path, suggested)
    
    def stop(self) -> None:
        """Stop current scan."""
        if self._scanner:
            self._scanner.stop()
            self._scanner.wait(5000)
            self._scanner = None
    
    def add_export(self, export_path: str, project_id: Optional[int] = None) -> Optional[int]:
        """Add an export to the database.
        
        Args:
            export_path: Path to the export file.
            project_id: Optional project to link to.
            
        Returns:
            Export ID if created, None if failed.
        """
        path = Path(export_path)
        if not path.exists():
            return None
        
        session = get_session()
        try:
            # Check if already exists
            existing = session.query(Export).filter(
                Export.export_path == export_path
            ).first()
            
            if existing:
                if project_id and not existing.project_id:
                    existing.project_id = project_id
                    session.commit()
                return existing.id
            
            # Get file info
            stat = path.stat()
            
            # Determine format
            format_ext = path.suffix.lower().strip('.')
            
            export = Export(
                project_id=project_id,
                export_path=export_path,
                export_name=path.stem,
                export_date=datetime.fromtimestamp(stat.st_mtime),
                format=format_ext,
                file_size=stat.st_size
            )
            
            session.add(export)
            session.commit()
            
            return export.id
            
        finally:
            session.close()
    
    def link_export_to_project(self, export_id: int, project_id: int) -> bool:
        """Link an export to a project.
        
        Args:
            export_id: Export database ID.
            project_id: Project database ID.
            
        Returns:
            True if successful.
        """
        session = get_session()
        try:
            export = session.query(Export).get(export_id)
            if export:
                export.project_id = project_id
                session.commit()
                self.mapping_created.emit(export_id, project_id)
                return True
            return False
        finally:
            session.close()
    
    def auto_match_exports(self, threshold: float = 70.0) -> int:
        """Automatically match unlinked exports to projects.
        
        Args:
            threshold: Minimum similarity score (0-100).
            
        Returns:
            Number of matches made.
        """
        session = get_session()
        try:
            # Get unlinked exports
            unlinked = session.query(Export).filter(
                Export.project_id.is_(None)
            ).all()
            
            if not unlinked:
                return 0
            
            # Get all projects
            projects = session.query(Project).all()
            project_map = {p.name.lower(): p.id for p in projects}
            
            # Also map by export song name
            for p in projects:
                if p.export_song_name:
                    project_map[p.export_song_name.lower()] = p.id
            
            matches_made = 0
            
            for export in unlinked:
                export_name = export.export_name.lower()
                
                # Try exact match first
                if export_name in project_map:
                    export.project_id = project_map[export_name]
                    matches_made += 1
                    continue
                
                # Try fuzzy match
                best_match = None
                best_score = 0
                
                for name, pid in project_map.items():
                    score = calculate_similarity(export_name, name)
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = pid
                
                if best_match:
                    export.project_id = best_match
                    matches_made += 1
            
            session.commit()
            return matches_made
            
        finally:
            session.close()
    
    def find_exports_by_time(self, project_id: int, hours: int = 24) -> List[Export]:
        """Find potential exports created around the same time as project modifications.
        
        Args:
            project_id: Project to find exports for.
            hours: Time window in hours.
            
        Returns:
            List of potential export matches.
        """
        session = get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project or not project.modified_date:
                return []
            
            # Search for exports created within the time window
            start = project.modified_date - timedelta(hours=hours)
            end = project.modified_date + timedelta(hours=hours)
            
            exports = session.query(Export).filter(
                Export.project_id.is_(None),
                Export.export_date >= start,
                Export.export_date <= end
            ).all()
            
            return exports
            
        finally:
            session.close()
    
    def get_project_exports(self, project_id: int) -> List[Export]:
        """Get all exports linked to a project.
        
        Args:
            project_id: Project ID.
            
        Returns:
            List of linked exports.
        """
        session = get_session()
        try:
            return session.query(Export).filter(
                Export.project_id == project_id
            ).order_by(Export.export_date.desc()).all()
        finally:
            session.close()
