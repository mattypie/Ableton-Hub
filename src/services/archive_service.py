"""Archive service for backing up Ableton projects."""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal


class ArchiveService(QObject):
    """Service for archiving and backing up Ableton projects.
    
    Supports:
    - Copying project folders to a backup location
    - Creating ZIP archives of projects
    - Incremental updates of existing backups
    """
    
    # Signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    archive_complete = pyqtSignal(str)  # archive path
    error_occurred = pyqtSignal(str)  # error message
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
    
    def archive_project(
        self,
        project_path: str,
        backup_location: str,
        compress: bool = False,
        include_timestamp: bool = True
    ) -> str:
        """Archive a project to the backup location.
        
        Args:
            project_path: Path to the .als project file.
            backup_location: Path to the backup folder.
            compress: If True, create a ZIP archive instead of copying.
            include_timestamp: If True, append timestamp to backup name.
            
        Returns:
            Path to the created backup.
            
        Raises:
            FileNotFoundError: If project doesn't exist.
            PermissionError: If backup location is not writable.
            Exception: For other errors.
        """
        project_file = Path(project_path)
        backup_dir = Path(backup_location)
        
        if not project_file.exists():
            raise FileNotFoundError(f"Project file not found: {project_path}")
        
        if not backup_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Get the project folder (parent of .als file)
        project_folder = project_file.parent
        project_name = project_folder.name
        
        # Create backup name
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{project_name}_{timestamp}"
        else:
            backup_name = project_name
        
        if compress:
            return self._create_zip_archive(project_folder, backup_dir, backup_name)
        else:
            return self._copy_project_folder(project_folder, backup_dir, backup_name)
    
    def _copy_project_folder(
        self,
        source_folder: Path,
        backup_dir: Path,
        backup_name: str
    ) -> str:
        """Copy project folder to backup location.
        
        Args:
            source_folder: Source project folder.
            backup_dir: Destination backup directory.
            backup_name: Name for the backup folder.
            
        Returns:
            Path to the created backup folder.
        """
        dest_folder = backup_dir / backup_name
        
        # If destination exists, add a counter
        counter = 1
        original_name = backup_name
        while dest_folder.exists():
            backup_name = f"{original_name}_{counter}"
            dest_folder = backup_dir / backup_name
            counter += 1
        
        # Count files for progress
        total_files = sum(1 for _ in source_folder.rglob("*") if _.is_file())
        copied_files = 0
        
        self.progress_updated.emit(0, total_files, "Starting backup...")
        
        # Copy the folder
        def copy_with_progress(src, dst):
            nonlocal copied_files
            if os.path.isdir(src):
                if not os.path.exists(dst):
                    os.makedirs(dst)
                for item in os.listdir(src):
                    copy_with_progress(os.path.join(src, item), os.path.join(dst, item))
            else:
                shutil.copy2(src, dst)
                copied_files += 1
                if copied_files % 10 == 0 or copied_files == total_files:
                    self.progress_updated.emit(
                        copied_files, total_files,
                        f"Copying: {os.path.basename(src)}"
                    )
        
        copy_with_progress(str(source_folder), str(dest_folder))
        
        self.progress_updated.emit(total_files, total_files, "Backup complete!")
        self.archive_complete.emit(str(dest_folder))
        
        return str(dest_folder)
    
    def _create_zip_archive(
        self,
        source_folder: Path,
        backup_dir: Path,
        backup_name: str
    ) -> str:
        """Create a ZIP archive of the project.
        
        Args:
            source_folder: Source project folder.
            backup_dir: Destination backup directory.
            backup_name: Name for the archive (without .zip extension).
            
        Returns:
            Path to the created ZIP file.
        """
        zip_path = backup_dir / f"{backup_name}.zip"
        
        # If destination exists, add a counter
        counter = 1
        original_name = backup_name
        while zip_path.exists():
            backup_name = f"{original_name}_{counter}"
            zip_path = backup_dir / f"{backup_name}.zip"
            counter += 1
        
        # Count files for progress
        all_files = list(source_folder.rglob("*"))
        total_files = len([f for f in all_files if f.is_file()])
        archived_files = 0
        
        self.progress_updated.emit(0, total_files, "Creating archive...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in all_files:
                if file_path.is_file():
                    # Calculate relative path
                    arcname = file_path.relative_to(source_folder.parent)
                    zipf.write(file_path, arcname)
                    
                    archived_files += 1
                    if archived_files % 10 == 0 or archived_files == total_files:
                        self.progress_updated.emit(
                            archived_files, total_files,
                            f"Archiving: {file_path.name}"
                        )
        
        self.progress_updated.emit(total_files, total_files, "Archive complete!")
        self.archive_complete.emit(str(zip_path))
        
        return str(zip_path)
    
    def get_backup_size(self, project_path: str) -> Tuple[int, int]:
        """Calculate the size of a project for backup estimation.
        
        Args:
            project_path: Path to the .als project file.
            
        Returns:
            Tuple of (total_size_bytes, file_count).
        """
        project_file = Path(project_path)
        if not project_file.exists():
            return (0, 0)
        
        project_folder = project_file.parent
        
        total_size = 0
        file_count = 0
        
        for file_path in project_folder.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        return (total_size, file_count)
    
    def list_backups(self, backup_location: str, project_name: str) -> list:
        """List existing backups for a project.
        
        Args:
            backup_location: Path to the backup folder.
            project_name: Name of the project to find backups for.
            
        Returns:
            List of backup paths sorted by date (newest first).
        """
        backup_dir = Path(backup_location)
        
        if not backup_dir.exists():
            return []
        
        backups = []
        
        # Find folders and zips matching project name
        for item in backup_dir.iterdir():
            if item.name.startswith(project_name):
                if item.is_dir() or (item.is_file() and item.suffix == '.zip'):
                    backups.append({
                        'path': str(item),
                        'name': item.name,
                        'is_zip': item.suffix == '.zip',
                        'modified': datetime.fromtimestamp(item.stat().st_mtime),
                        'size': self._get_item_size(item)
                    })
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
        return backups
    
    def _get_item_size(self, path: Path) -> int:
        """Get the total size of a file or folder."""
        if path.is_file():
            return path.stat().st_size
        
        total = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total
    
    def delete_backup(self, backup_path: str) -> bool:
        """Delete a backup.
        
        Args:
            backup_path: Path to the backup to delete.
            
        Returns:
            True if deleted successfully.
        """
        path = Path(backup_path)
        
        if not path.exists():
            return False
        
        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to delete backup: {str(e)}")
            return False
