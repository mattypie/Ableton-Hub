"""Remote location sync service for Dropbox, cloud storage, and network shares."""

from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
import os
import sys
import json

from PyQt6.QtCore import QObject, pyqtSignal

from ..database import get_session, Location, LocationType


class RemoteSync(QObject):
    """Service for handling remote and cloud storage locations."""
    
    # Signals
    sync_status_changed = pyqtSignal(int, str)  # location_id, status
    location_online = pyqtSignal(int)           # location_id
    location_offline = pyqtSignal(int)          # location_id
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._location_status: Dict[int, str] = {}
    
    def detect_dropbox_folder(self) -> Optional[Path]:
        """Detect the Dropbox folder location.
        
        Returns:
            Path to Dropbox folder, or None if not found.
        """
        # Check common locations
        home = Path.home()
        
        common_paths = [
            home / "Dropbox",
            home / "Documents" / "Dropbox",
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        # Try to read Dropbox config file
        config_locations = []
        
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            localappdata = os.environ.get("LOCALAPPDATA", "")
            config_locations = [
                Path(appdata) / "Dropbox" / "info.json",
                Path(localappdata) / "Dropbox" / "info.json",
            ]
        elif sys.platform == "darwin":
            config_locations = [
                home / ".dropbox" / "info.json",
            ]
        else:
            config_locations = [
                home / ".dropbox" / "info.json",
            ]
        
        for config_path in config_locations:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        info = json.load(f)
                    
                    # Personal account
                    if 'personal' in info:
                        return Path(info['personal']['path'])
                    # Business account
                    if 'business' in info:
                        return Path(info['business']['path'])
                except Exception:
                    pass
        
        return None
    
    def detect_onedrive_folder(self) -> Optional[Path]:
        """Detect the OneDrive folder location.
        
        Returns:
            Path to OneDrive folder, or None if not found.
        """
        home = Path.home()
        
        common_paths = [
            home / "OneDrive",
            home / "OneDrive - Personal",
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        # Check Windows registry location
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\OneDrive"
                )
                path, _ = winreg.QueryValueEx(key, "UserFolder")
                if Path(path).exists():
                    return Path(path)
            except Exception:
                pass
        
        return None
    
    def detect_google_drive_folder(self) -> Optional[Path]:
        """Detect the Google Drive folder location.
        
        Returns:
            Path to Google Drive folder, or None if not found.
        """
        home = Path.home()
        
        common_paths = [
            home / "Google Drive",
            home / "My Drive",
            home / "GoogleDrive",
        ]
        
        # Google Drive Stream paths
        if sys.platform == "win32":
            common_paths.extend([
                Path("G:") / "My Drive",
                Path("G:") / "Shared drives",
            ])
        elif sys.platform == "darwin":
            common_paths.extend([
                Path("/Volumes/GoogleDrive/My Drive"),
                Path("/Volumes/GoogleDrive/Shared drives"),
            ])
        
        for path in common_paths:
            if path.exists():
                return path
        
        return None
    
    def detect_icloud_folder(self) -> Optional[Path]:
        """Detect the iCloud Drive folder location.
        
        Returns:
            Path to iCloud Drive folder, or None if not found.
        """
        if sys.platform != "darwin":
            return None
        
        home = Path.home()
        icloud_path = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        
        if icloud_path.exists():
            return icloud_path
        
        return None
    
    def detect_ableton_cloud_folder(self) -> Optional[Path]:
        """Detect the Ableton Cloud/Collab folder location.
        
        Returns:
            Path to Ableton Cloud folder, or None if not found.
        """
        home = Path.home()
        
        # Ableton Cloud stores files locally
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
            paths = [
                base / "Ableton" / "Cloud",
                base / "Ableton" / "Live Cloud",
            ]
        elif sys.platform == "darwin":
            paths = [
                home / "Library" / "Application Support" / "Ableton" / "Cloud",
                home / "Music" / "Ableton" / "Cloud",
            ]
        else:
            paths = [
                home / ".ableton" / "cloud",
            ]
        
        for path in paths:
            if path.exists():
                return path
        
        return None
    
    def detect_all_cloud_folders(self) -> Dict[str, Optional[Path]]:
        """Detect all available cloud storage folders.
        
        Returns:
            Dictionary of service name to path (or None if not found).
        """
        return {
            'dropbox': self.detect_dropbox_folder(),
            'onedrive': self.detect_onedrive_folder(),
            'google_drive': self.detect_google_drive_folder(),
            'icloud': self.detect_icloud_folder(),
            'ableton_cloud': self.detect_ableton_cloud_folder(),
        }
    
    def check_location_online(self, location_id: int) -> bool:
        """Check if a location is online/accessible.
        
        Args:
            location_id: Database ID of the location.
            
        Returns:
            True if location is accessible.
        """
        session = get_session()
        try:
            location = session.query(Location).get(location_id)
            if not location:
                return False
            
            path = Path(location.path)
            is_online = path.exists() and path.is_dir()
            
            # Update status
            old_status = self._location_status.get(location_id)
            new_status = "online" if is_online else "offline"
            self._location_status[location_id] = new_status
            
            # Emit signals on change
            if old_status != new_status:
                self.sync_status_changed.emit(location_id, new_status)
                if is_online:
                    self.location_online.emit(location_id)
                else:
                    self.location_offline.emit(location_id)
            
            return is_online
            
        finally:
            session.close()
    
    def check_all_locations(self) -> Dict[int, bool]:
        """Check online status of all locations.
        
        Returns:
            Dictionary of location_id to online status.
        """
        session = get_session()
        try:
            locations = session.query(Location).filter(
                Location.is_active == True
            ).all()
            
            results = {}
            for location in locations:
                results[location.id] = self.check_location_online(location.id)
            
            return results
            
        finally:
            session.close()
    
    def get_sync_status(self, path: Path) -> str:
        """Get the sync status of a file or folder.
        
        This checks cloud provider sync status attributes.
        
        Args:
            path: Path to check.
            
        Returns:
            Status string: "synced", "syncing", "pending", "error", or "unknown".
        """
        if not path.exists():
            return "missing"
        
        # Dropbox uses extended attributes on macOS
        if sys.platform == "darwin":
            try:
                import xattr
                attrs = xattr.xattr(path)
                
                # Dropbox
                if 'com.dropbox.attributes' in attrs:
                    # Parse Dropbox attributes
                    return "synced"  # Simplified
                
            except Exception:
                pass
        
        # Windows - check Dropbox sync status
        if sys.platform == "win32":
            try:
                # Dropbox creates overlay icons via shell extensions
                # We can't easily check this without COM
                pass
            except Exception:
                pass
        
        return "unknown"
    
    def is_network_share(self, path: Path) -> bool:
        """Check if a path is a network share.
        
        Args:
            path: Path to check.
            
        Returns:
            True if path is a network share.
        """
        path_str = str(path)
        
        # Windows UNC paths
        if path_str.startswith("\\\\"):
            return True
        
        # Windows mapped drives might be network shares
        if sys.platform == "win32" and len(path_str) >= 2 and path_str[1] == ':':
            try:
                import ctypes
                drive = path_str[0] + ":"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
                return drive_type == 4  # DRIVE_REMOTE
            except Exception:
                pass
        
        # Unix - check if mounted via NFS/SMB/AFP
        if sys.platform != "win32":
            try:
                # Check mount point
                import subprocess
                result = subprocess.run(
                    ["df", "-T", str(path)],
                    capture_output=True, text=True, timeout=5
                )
                fs_type = result.stdout.split('\n')[1].split()[1].lower()
                return fs_type in ['nfs', 'cifs', 'smbfs', 'afpfs', 'webdav']
            except Exception:
                pass
        
        return False
    
    def auto_detect_location_type(self, path: Path) -> LocationType:
        """Auto-detect the type of a location.
        
        Args:
            path: Path to analyze.
            
        Returns:
            Detected LocationType.
        """
        path_str = str(path).lower()
        
        # Check for cloud storage paths
        if "dropbox" in path_str:
            return LocationType.DROPBOX
        
        if "onedrive" in path_str or "one drive" in path_str:
            return LocationType.CLOUD
        
        if "google" in path_str and "drive" in path_str:
            return LocationType.CLOUD
        
        if "icloud" in path_str or "mobile documents" in path_str:
            return LocationType.CLOUD
        
        if "ableton" in path_str and "cloud" in path_str:
            return LocationType.COLLAB
        
        # Check for network share
        if self.is_network_share(path):
            return LocationType.NETWORK
        
        # Check for removable drive
        if sys.platform == "win32":
            try:
                import ctypes
                drive = str(path)[:3]
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                if drive_type == 2:  # DRIVE_REMOVABLE
                    return LocationType.USB
            except Exception:
                pass
        elif sys.platform == "darwin":
            if "/Volumes/" in str(path) and path != Path("/Volumes/Macintosh HD"):
                # Could be USB or external drive
                return LocationType.USB
        
        return LocationType.LOCAL
    
    def create_location_from_cloud(self, service: str) -> Optional[int]:
        """Create a location from a detected cloud service.
        
        Args:
            service: Service name (dropbox, onedrive, etc.)
            
        Returns:
            Location ID if created, None otherwise.
        """
        folders = self.detect_all_cloud_folders()
        path = folders.get(service)
        
        if not path:
            return None
        
        # Map service to location type
        type_map = {
            'dropbox': LocationType.DROPBOX,
            'onedrive': LocationType.CLOUD,
            'google_drive': LocationType.CLOUD,
            'icloud': LocationType.CLOUD,
            'ableton_cloud': LocationType.COLLAB,
        }
        
        # Map service to display name
        name_map = {
            'dropbox': 'Dropbox',
            'onedrive': 'OneDrive',
            'google_drive': 'Google Drive',
            'icloud': 'iCloud Drive',
            'ableton_cloud': 'Ableton Cloud',
        }
        
        loc_type = type_map.get(service, LocationType.CLOUD)
        name = name_map.get(service, service.title())
        
        session = get_session()
        try:
            # Check if already exists
            existing = session.query(Location).filter(
                Location.path == str(path)
            ).first()
            
            if existing:
                return existing.id
            
            # Create location
            location = Location(
                name=name,
                path=str(path),
                location_type=loc_type,
                is_active=True
            )
            session.add(location)
            session.commit()
            
            return location.id
            
        finally:
            session.close()
