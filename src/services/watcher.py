"""File system watcher for automatic project updates."""

from typing import Optional, List, Dict, Set
from pathlib import Path
from datetime import datetime
import time

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler, FileSystemEvent,
    FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent
)

from ..database import get_session, Location, Project, ProjectStatus
from ..utils.paths import is_ableton_project


class AbletonEventHandler(FileSystemEventHandler):
    """Handles file system events for Ableton projects."""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if not event.is_directory:
            path = Path(event.src_path)
            if is_ableton_project(path):
                self.callback("created", event.src_path)
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix.lower() == ".als":
                self.callback("deleted", event.src_path)
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if not event.is_directory:
            path = Path(event.src_path)
            if is_ableton_project(path):
                self.callback("modified", event.src_path)
    
    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move/rename."""
        if not event.is_directory:
            src = Path(event.src_path)
            dest = Path(event.dest_path)
            
            if src.suffix.lower() == ".als" or dest.suffix.lower() == ".als":
                self.callback("moved", event.src_path, event.dest_path)


class FileWatcher(QObject):
    """Watches locations for file changes and updates the database."""
    
    # Signals
    project_created = pyqtSignal(str)   # Path
    project_modified = pyqtSignal(str)  # Path
    project_deleted = pyqtSignal(str)   # Path
    project_moved = pyqtSignal(str, str)  # Old path, new path
    error_occurred = pyqtSignal(str)    # Error message
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._observer: Optional[Observer] = None
        self._watched_paths: Dict[str, int] = {}  # path -> location_id
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._process_pending_events)
        self._pending_events: List[tuple] = []
    
    def start(self) -> None:
        """Start watching all active locations."""
        if self._observer is not None:
            self.stop()
        
        self._observer = Observer()
        self._observer.start()
        
        # Add all active locations
        session = get_session()
        try:
            locations = session.query(Location).filter(
                Location.is_active == True
            ).all()
            
            for location in locations:
                self.add_location(location.id, location.path)
        finally:
            session.close()
    
    def stop(self) -> None:
        """Stop watching all locations."""
        if self._debounce_timer:
            self._debounce_timer.stop()
            self._debounce_timer = None
        
        if self._observer:
            try:
                # Stop the observer
                if self._observer.is_alive():
                    self._observer.stop()
                    # Wait for it to finish with a longer timeout
                    self._observer.join(timeout=10)
                    # If still alive, it will be cleaned up by Python
            except Exception:
                pass  # Ignore errors during shutdown
            finally:
                self._observer = None
        
        self._watched_paths.clear()
    
    def add_location(self, location_id: int, path: str) -> bool:
        """Add a location to watch.
        
        Args:
            location_id: Database ID of the location.
            path: File system path to watch.
            
        Returns:
            True if successfully added.
        """
        if not self._observer:
            return False
        
        if path in self._watched_paths:
            return True
        
        path_obj = Path(path)
        if not path_obj.exists():
            return False
        
        try:
            handler = AbletonEventHandler(self._on_event)
            self._observer.schedule(handler, path, recursive=True)
            self._watched_paths[path] = location_id
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to watch {path}: {e}")
            return False
    
    def remove_location(self, path: str) -> None:
        """Remove a location from watching.
        
        Args:
            path: File system path to stop watching.
        """
        if path in self._watched_paths:
            # Note: watchdog doesn't support removing individual handlers easily
            # Would need to restart the observer to fully remove
            del self._watched_paths[path]
    
    def _on_event(self, event_type: str, path: str, dest_path: str = None) -> None:
        """Handle a file system event.
        
        Uses debouncing to batch rapid events.
        """
        self._pending_events.append((event_type, path, dest_path))
        
        # Restart debounce timer
        self._debounce_timer.start(500)  # 500ms debounce
    
    def _process_pending_events(self) -> None:
        """Process batched events after debounce."""
        events = self._pending_events.copy()
        self._pending_events.clear()
        
        # Deduplicate and process
        processed: Set[str] = set()
        
        for event_type, path, dest_path in events:
            if path in processed:
                continue
            processed.add(path)
            
            if event_type == "created":
                self._handle_created(path)
            elif event_type == "modified":
                self._handle_modified(path)
            elif event_type == "deleted":
                self._handle_deleted(path)
            elif event_type == "moved":
                self._handle_moved(path, dest_path)
    
    def _handle_created(self, path: str) -> None:
        """Handle project creation."""
        # Find which location this belongs to
        location_id = self._find_location(path)
        if not location_id:
            return
        
        session = get_session()
        try:
            # Check if already exists
            existing = session.query(Project).filter(
                Project.file_path == path
            ).first()
            
            if existing:
                return
            
            # Create new project
            path_obj = Path(path)
            stat = path_obj.stat()
            
            project = Project(
                name=path_obj.stem,
                file_path=path,
                location_id=location_id,
                file_size=stat.st_size,
                created_date=datetime.fromtimestamp(stat.st_ctime),
                modified_date=datetime.fromtimestamp(stat.st_mtime),
                last_scanned=datetime.utcnow(),
                status=ProjectStatus.LOCAL
            )
            
            session.add(project)
            session.commit()
            
            self.project_created.emit(path)
            
        except Exception as e:
            self.error_occurred.emit(f"Error handling created project: {e}")
        finally:
            session.close()
    
    def _handle_modified(self, path: str) -> None:
        """Handle project modification."""
        session = get_session()
        try:
            project = session.query(Project).filter(
                Project.file_path == path
            ).first()
            
            if project:
                path_obj = Path(path)
                if path_obj.exists():
                    stat = path_obj.stat()
                    project.file_size = stat.st_size
                    project.modified_date = datetime.fromtimestamp(stat.st_mtime)
                    project.last_scanned = datetime.utcnow()
                    session.commit()
                    
                    self.project_modified.emit(path)
                    
        except Exception as e:
            self.error_occurred.emit(f"Error handling modified project: {e}")
        finally:
            session.close()
    
    def _handle_deleted(self, path: str) -> None:
        """Handle project deletion."""
        session = get_session()
        try:
            project = session.query(Project).filter(
                Project.file_path == path
            ).first()
            
            if project:
                project.status = ProjectStatus.MISSING
                session.commit()
                
                self.project_deleted.emit(path)
                
        except Exception as e:
            self.error_occurred.emit(f"Error handling deleted project: {e}")
        finally:
            session.close()
    
    def _handle_moved(self, old_path: str, new_path: str) -> None:
        """Handle project move/rename."""
        session = get_session()
        try:
            project = session.query(Project).filter(
                Project.file_path == old_path
            ).first()
            
            if project:
                new_path_obj = Path(new_path)
                
                project.file_path = new_path
                project.name = new_path_obj.stem
                
                # Check if it moved to a different location
                new_location_id = self._find_location(new_path)
                if new_location_id and new_location_id != project.location_id:
                    project.location_id = new_location_id
                
                session.commit()
                
                self.project_moved.emit(old_path, new_path)
                
        except Exception as e:
            self.error_occurred.emit(f"Error handling moved project: {e}")
        finally:
            session.close()
    
    def _find_location(self, path: str) -> Optional[int]:
        """Find which watched location contains a path.
        
        Args:
            path: File path to check.
            
        Returns:
            Location ID or None if not in any watched location.
        """
        path_obj = Path(path)
        
        for watched_path, location_id in self._watched_paths.items():
            try:
                path_obj.relative_to(watched_path)
                return location_id
            except ValueError:
                continue
        
        return None
    
    @property
    def is_watching(self) -> bool:
        """Check if currently watching."""
        return self._observer is not None and self._observer.is_alive()
    
    @property
    def watched_locations(self) -> List[str]:
        """Get list of watched paths."""
        return list(self._watched_paths.keys())
