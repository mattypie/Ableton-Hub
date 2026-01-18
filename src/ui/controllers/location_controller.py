"""Controller for managing project locations."""

import logging
from typing import Optional, List

from PyQt6.QtCore import QObject, pyqtSignal

from ...database import get_session, Location, Project, ProjectCollection
from ...utils.logging import get_logger


class LocationController(QObject):
    """Manages location operations."""
    
    # Signals
    location_added = pyqtSignal(int)  # location_id
    location_removed = pyqtSignal(int)  # location_id
    location_updated = pyqtSignal(int)  # location_id
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the location controller.
        
        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.logger = get_logger(__name__)
    
    def get_all_locations(self) -> List[Location]:
        """Get all locations.
        
        Returns:
            List of Location objects.
        """
        with get_session() as session:
            return session.query(Location).filter(Location.is_active == True).order_by(Location.name).all()
    
    def get_location(self, location_id: int) -> Optional[Location]:
        """Get a location by ID.
        
        Args:
            location_id: Location ID.
            
        Returns:
            Location object or None if not found.
        """
        with get_session() as session:
            return session.query(Location).filter(Location.id == location_id).first()
    
    def remove_location(self, location_id: int, delete_projects: bool = False) -> bool:
        """Remove a location and optionally its projects.
        
        Args:
            location_id: Location ID to remove.
            delete_projects: If True, delete projects not in collections.
            
        Returns:
            True if removed successfully.
        """
        with get_session() as session:
            location = session.query(Location).filter(Location.id == location_id).first()
            if not location:
                return False
            
            location_name = location.name
            
            if delete_projects:
                # Count projects in collections vs not in collections
                projects = session.query(Project).filter(Project.location_id == location_id).all()
                deleted_count = 0
                kept_count = 0
                
                for project in projects:
                    # Check if project is in any collection
                    in_collection = session.query(ProjectCollection).filter(
                        ProjectCollection.project_id == project.id
                    ).first() is not None
                    
                    if in_collection:
                        # Keep project but clear location_id
                        project.location_id = None
                        kept_count += 1
                    else:
                        # Delete project
                        session.delete(project)
                        deleted_count += 1
                
                if deleted_count > 0:
                    self.logger.info(f"Deleted {deleted_count} project(s) not in collections")
                if kept_count > 0:
                    self.logger.info(f"Kept {kept_count} project(s) in collections (location cleared)")
            
            session.delete(location)
            session.commit()
            
            self.logger.info(f"Removed location: {location_name} (ID: {location_id})")
            self.location_removed.emit(location_id)
            return True
