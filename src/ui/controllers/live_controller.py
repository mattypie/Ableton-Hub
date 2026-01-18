"""Controller for managing Ableton Live installations."""

import logging
import os
from typing import Optional, List

from PyQt6.QtCore import QObject, pyqtSignal

from ...database import get_session, LiveInstallation
from ...services.live_detector import LiveDetector
from ...utils.logging import get_logger


class LiveController(QObject):
    """Manages Ableton Live installation operations."""
    
    # Signals
    installations_changed = pyqtSignal()
    installation_added = pyqtSignal(int)  # install_id
    installation_removed = pyqtSignal(int)  # install_id
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the Live controller.
        
        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self._detector = LiveDetector()
    
    def auto_detect_installations(self) -> List:
        """Auto-detect Ableton Live installations.
        
        Returns:
            List of detected LiveVersion objects.
        """
        self.logger.info("Starting auto-detection...")
        self.logger.debug(f"ProgramFiles: {os.environ.get('ProgramFiles', 'N/A')}")
        self.logger.debug(f"ProgramFiles(x86): {os.environ.get('ProgramFiles(x86)', 'N/A')}")
        self.logger.debug(f"ProgramData: {os.environ.get('ProgramData', 'N/A')}")
        self.logger.debug(f"LOCALAPPDATA: {os.environ.get('LOCALAPPDATA', 'N/A')}")
        self.logger.debug(f"APPDATA: {os.environ.get('APPDATA', 'N/A')}")
        
        detected_versions = self._detector.detect_all()
        
        self.logger.info(f"Found {len(detected_versions)} version(s)")
        for v in detected_versions:
            self.logger.debug(f"  - {v} at {v.path}")
        
        return detected_versions
    
    def get_all_installations(self) -> List[LiveInstallation]:
        """Get all Live installations from database.
        
        Returns:
            List of LiveInstallation objects.
        """
        with get_session() as session:
            return session.query(LiveInstallation).order_by(LiveInstallation.version.desc()).all()
    
    def get_favorite_installation(self) -> Optional[LiveInstallation]:
        """Get the favorite Live installation.
        
        Returns:
            LiveInstallation object or None.
        """
        with get_session() as session:
            return session.query(LiveInstallation).filter(
                LiveInstallation.is_favorite == True
            ).first()
    
    def set_favorite(self, install_id: int) -> bool:
        """Set a Live installation as favorite.
        
        Args:
            install_id: Installation ID.
            
        Returns:
            True if successful.
        """
        with get_session() as session:
            # Clear all favorites first
            session.query(LiveInstallation).update({"is_favorite": False})
            
            # Set new favorite
            install = session.query(LiveInstallation).filter(
                LiveInstallation.id == install_id
            ).first()
            if install:
                install.is_favorite = True
                session.commit()
                self.installations_changed.emit()
                return True
            return False
    
    def remove_installation(self, install_id: int) -> bool:
        """Remove a Live installation.
        
        Args:
            install_id: Installation ID to remove.
            
        Returns:
            True if removed successfully.
        """
        with get_session() as session:
            install = session.query(LiveInstallation).filter(
                LiveInstallation.id == install_id
            ).first()
            if install:
                session.delete(install)
                session.commit()
                self.logger.info(f"Removed Live installation: {install.name} (ID: {install_id})")
                self.installation_removed.emit(install_id)
                self.installations_changed.emit()
                return True
            return False
