"""Service for detecting installed Ableton Live versions."""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class LiveVersion:
    """Represents an installed Ableton Live version."""
    version: str  # e.g., "11.3.13"
    path: Path  # Path to Live executable
    build: Optional[str] = None  # Build number if available
    is_suite: bool = False  # True if Live Suite, False if Standard/Intro
    
    def __str__(self) -> str:
        suite_str = " Suite" if self.is_suite else ""
        return f"Live {self.version}{suite_str}"


class LiveDetector:
    """Detects installed Ableton Live versions on the system."""
    
    def __init__(self):
        self._versions: List[LiveVersion] = []
        self._scan()
    
    def get_versions(self) -> List[LiveVersion]:
        """Get all detected Live versions, sorted by version (newest first)."""
        return sorted(self._versions, key=lambda v: self._parse_version(v.version), reverse=True)
    
    def get_version_by_path(self, path: Path) -> Optional[LiveVersion]:
        """Get Live version by executable path."""
        for version in self._versions:
            if version.path == path:
                return version
        return None
    
    def _scan(self) -> None:
        """Scan for installed Live versions."""
        self._versions.clear()
        
        if sys.platform == "win32":
            self._scan_windows()
        elif sys.platform == "darwin":
            self._scan_macos()
        else:
            self._scan_linux()
    
    def _scan_windows(self) -> None:
        """Scan for Live on Windows."""
        # Common installation base paths on Windows
        program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        program_data = Path(os.environ.get("ProgramData", "C:\\ProgramData"))
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        
        # Base paths that might contain an "Ableton" folder
        base_search_paths = [
            program_files,
            program_files_x86,
            program_data,  # C:\ProgramData\Ableton
            local_appdata,
            appdata,
        ]
        
        import re
        
        # Scan all base paths for "Ableton" folders
        for base_path in base_search_paths:
            print(f"[LIVE DETECT] Checking base path: {base_path}")
            if not base_path.exists():
                print(f"[LIVE DETECT] Base path does not exist: {base_path}")
                continue
            
            try:
                # Look for "Ableton" folder in this base path
                ableton_folder = base_path / "Ableton"
                print(f"[LIVE DETECT] Checking for Ableton folder: {ableton_folder}")
                if not ableton_folder.exists():
                    print(f"[LIVE DETECT] Ableton folder does not exist: {ableton_folder}")
                    # Also check if there are any folders starting with "Ableton" or containing "Live"
                    try:
                        for item in base_path.iterdir():
                            if item.is_dir() and ("Ableton" in item.name or "Live" in item.name):
                                print(f"[LIVE DETECT] Found potential Ableton/Live folder: {item}")
                    except (PermissionError, OSError):
                        pass
                    continue
                
                if not ableton_folder.is_dir():
                    print(f"[LIVE DETECT] Path exists but is not a directory: {ableton_folder}")
                    continue
                
                print(f"[LIVE DETECT] Found Ableton folder: {ableton_folder}, scanning contents...")
                
                # Now scan inside the Ableton folder for Live installations
                # Support Live 10, Live 11, Live 12, and future versions
                found_items = []
                for item in ableton_folder.iterdir():
                    found_items.append(item.name)
                    if not item.is_dir():
                        continue
                    
                    print(f"[LIVE DETECT] Checking item in Ableton folder: {item.name}")
                    
                    # Match patterns like:
                    # - "Live 10", "Live 11", "Live 12"
                    # - "Live 10 Suite", "Live 11 Standard", "Live 12 Suite"
                    # - "Live 10.1.30", "Live 11.3.13", "Live 12.0.5"
                    # - "Live 10 Suite 10.1.30", "Live 11 Standard 11.3.13", etc.
                    # Regex matches Live followed by version number (10, 11, 12, or any future version)
                    live_match = re.match(r'^Live\s+(\d+(?:\.\d+)*)', item.name, re.IGNORECASE)
                    if live_match:
                        version_num = live_match.group(1)
                        # Extract major version (10, 11, or 12) for validation
                        major_version = int(version_num.split('.')[0])
                        
                        # Only process Live 10, 11, 12 (and future versions >= 10)
                        if major_version >= 10:
                            print(f"[LIVE DETECT] Matched Live pattern: {item.name} -> version {version_num} (major: {major_version})")
                            
                            # Try multiple possible locations for Live.exe
                            possible_paths = [
                                item / "Live.exe",  # Direct in Live folder
                                item / "Program" / "Ableton Live.exe",  # In Program subfolder
                                item / "Program" / f"Ableton Live {version_num}.exe",  # Versioned in Program
                            ]
                            
                            # Also check for Suite/Standard variants in Program folder
                            suite_variants = [
                                item / "Program" / f"Ableton Live {version_num} Suite.exe",
                                item / "Program" / f"Ableton Live {version_num} Standard.exe",
                            ]
                            possible_paths.extend(suite_variants)
                            
                            # For Live 10, 11, 12, also check common alternative naming
                            if major_version in [10, 11, 12]:
                                # Check for "Live X Suite" or "Live X Standard" folder names with executable
                                possible_paths.extend([
                                    item / f"Live {major_version}.exe",  # Simple version
                                    item / "Program" / f"Live {major_version}.exe",  # In Program
                                ])
                            
                            live_exe = None
                            for exe_path in possible_paths:
                                print(f"[LIVE DETECT] Checking for Live.exe at: {exe_path}")
                                if exe_path.exists():
                                    live_exe = exe_path
                                    print(f"[LIVE DETECT] Found Live.exe: {live_exe}")
                                    break
                            
                            if live_exe:
                                # Extract version from folder name
                                version_str = version_num  # Use the extracted version number
                                
                                # Check if it's Suite (Standard is default if not Suite)
                                # Check both folder name and executable name
                                is_suite = ("Suite" in item.name or 
                                          "Suite" in live_exe.name or 
                                          self._check_suite_windows(item))
                                
                                # Avoid duplicates (check if we already have this path)
                                if not any(v.path == live_exe for v in self._versions):
                                    print(f"[LIVE DETECT] Adding Live version: {version_str} {'Suite' if is_suite else 'Standard'} at {live_exe}")
                                    self._versions.append(LiveVersion(
                                        version=version_str,
                                        path=live_exe,
                                        is_suite=is_suite
                                    ))
                            else:
                                print(f"[LIVE DETECT] Live.exe not found in any expected location for: {item.name}")
                        else:
                            print(f"[LIVE DETECT] Skipping Live version {major_version} (only supporting Live 10+)")
                            continue
                    else:
                        print(f"[LIVE DETECT] Item does not match Live pattern: {item.name}")
                
                if found_items:
                    print(f"[LIVE DETECT] All items in {ableton_folder}: {', '.join(found_items)}")
            except (PermissionError, OSError) as e:
                print(f"[LIVE DETECT] Error accessing {base_path}: {e}")
                # Skip paths we can't access
                continue
    
    def _scan_macos(self) -> None:
        """Scan for Live on macOS."""
        # Common installation paths on macOS
        applications = Path("/Applications")
        user_applications = Path.home() / "Applications"
        
        # Also check common user data locations
        library_app_support = Path.home() / "Library" / "Application Support" / "Ableton"
        
        search_paths = [applications, user_applications]
        
        for base_path in search_paths:
            if not base_path.exists():
                continue
            
            try:
                # Look for Live X.X.app bundles
                # Support Live 10, Live 11, Live 12, and future versions
                for item in base_path.iterdir():
                    if not item.is_dir() or item.suffix != ".app":
                        continue
                    
                    # Match patterns like:
                    # - "Live 10.app", "Live 11.app", "Live 12.app"
                    # - "Live 10 Suite.app", "Live 11 Standard.app", "Live 12 Suite.app"
                    # - "Live 10.1.30.app", "Live 11.3.13.app", "Live 12.0.5.app"
                    import re
                    live_match = re.match(r'^Live\s+(\d+(?:\.\d+)*)', item.name, re.IGNORECASE)
                    if live_match:
                        version_num = live_match.group(1)
                        # Extract major version (10, 11, or 12) for validation
                        major_version = int(version_num.split('.')[0])
                        
                        # Only process Live 10, 11, 12 (and future versions >= 10)
                        if major_version >= 10:
                            # Live executable is inside the .app bundle
                            live_exe = item / "Contents" / "MacOS" / "Live"
                            if live_exe.exists():
                                # Extract version number
                                version_str = version_num
                                
                                # Check if it's Suite
                                is_suite = "Suite" in item.name or self._check_suite_macos(item)
                                
                                # Avoid duplicates
                                if not any(v.path == live_exe for v in self._versions):
                                    print(f"[LIVE DETECT] Adding Live version: {version_str} {'Suite' if is_suite else 'Standard'} at {live_exe}")
                                    self._versions.append(LiveVersion(
                                        version=version_str,
                                        path=live_exe,
                                        is_suite=is_suite
                                    ))
            except (PermissionError, OSError) as e:
                # Skip paths we can't access
                continue
        
        # Also check Application Support for additional installations
        if library_app_support.exists():
            try:
                for item in library_app_support.iterdir():
                    if not item.is_dir():
                        continue
                    
                    # Look for Live folders in Application Support
                    import re
                    live_match = re.match(r'^Live\s+(\d+(?:\.\d+)*)', item.name, re.IGNORECASE)
                    if live_match:
                        version_num = live_match.group(1)
                        # Extract major version (10, 11, or 12) for validation
                        major_version = int(version_num.split('.')[0])
                        
                        # Only process Live 10, 11, 12 (and future versions >= 10)
                        if major_version >= 10:
                            # Some installations might have Live executable here
                            live_exe = item / "Live"
                            if live_exe.exists() and live_exe.is_file():
                                version_str = version_num
                                is_suite = "Suite" in item.name or self._check_suite_macos(item)
                                
                                if not any(v.path == live_exe for v in self._versions):
                                    print(f"[LIVE DETECT] Adding Live version from Application Support: {version_str} {'Suite' if is_suite else 'Standard'} at {live_exe}")
                                    self._versions.append(LiveVersion(
                                        version=version_str,
                                        path=live_exe,
                                        is_suite=is_suite
                                    ))
            except (PermissionError, OSError) as e:
                pass
    
    def _scan_linux(self) -> None:
        """Scan for Live on Linux (if running via Wine or native)."""
        # Linux paths (less common, but possible)
        home = Path.home()
        search_paths = [
            home / ".wine" / "drive_c" / "Program Files" / "Ableton",
            home / ".local" / "bin",
            Path("/usr/local/bin"),
            Path("/opt/ableton"),
        ]
        
        for base_path in search_paths:
            if not base_path.exists():
                continue
            
            if base_path.is_file() and "live" in base_path.name.lower():
                # Single executable
                version_str = self._extract_version_from_path(base_path)
                if version_str:
                    self._versions.append(LiveVersion(
                        version=version_str,
                        path=base_path,
                        is_suite=False  # Hard to determine on Linux
                    ))
            elif base_path.is_dir():
                # Look for Live folders
                for item in base_path.iterdir():
                    if item.is_dir() and "live" in item.name.lower():
                        live_exe = item / "Live"
                        if live_exe.exists():
                            version_str = self._extract_version_from_path(item)
                            if version_str:
                                self._versions.append(LiveVersion(
                                    version=version_str,
                                    path=live_exe,
                                    is_suite=False
                                ))
    
    def _check_suite_windows(self, live_dir: Path) -> bool:
        """Check if this is Live Suite on Windows."""
        # Suite typically has more content or different structure
        # Check for Suite-specific files or folders
        suite_indicators = [
            live_dir / "Max" / "Max.exe",  # Max for Live
            live_dir / "Max.app",  # Max for Live (if bundled)
        ]
        return any(indicator.exists() for indicator in suite_indicators)
    
    def _check_suite_macos(self, live_app: Path) -> bool:
        """Check if this is Live Suite on macOS."""
        # Check for Max for Live in Contents
        max_path = live_app / "Contents" / "Max"
        return max_path.exists()
    
    def _extract_version_from_path(self, path: Path) -> Optional[str]:
        """Extract version string from path."""
        name = path.name
        # Try to find version pattern like "11.3" or "11.3.13"
        import re
        match = re.search(r'(\d+\.\d+(?:\.\d+)?)', name)
        if match:
            return match.group(1)
        return None
    
    def _parse_version(self, version_str: str) -> tuple:
        """Parse version string to tuple for sorting (e.g., "11.3.13" -> (11, 3, 13))."""
        try:
            parts = [int(x) for x in version_str.split('.')]
            # Pad with zeros for consistent sorting
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts[:3])
        except ValueError:
            return (0, 0, 0)
    
    def refresh(self) -> None:
        """Rescan for Live versions."""
        self._scan()
