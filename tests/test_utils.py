"""Test utilities for finding and loading example projects and test data."""

from pathlib import Path
from typing import List, Optional
import json

# Path to example-projects directory (inside ableton_hub)
EXAMPLE_PROJECTS_DIR = Path(__file__).parent.parent / "example-projects"


def find_example_projects() -> List[Path]:
    """Find all .als files in example-projects directory.
    
    Returns:
        List of paths to .als files. Returns empty list if directory doesn't exist.
    """
    if not EXAMPLE_PROJECTS_DIR.exists():
        return []
    
    als_files = list(EXAMPLE_PROJECTS_DIR.rglob("*.als"))
    return als_files


def find_example_asd_files() -> List[Path]:
    """Find all .asd files in example-projects directory.
    
    Returns:
        List of paths to .asd files. Returns empty list if directory doesn't exist.
    """
    if not EXAMPLE_PROJECTS_DIR.exists():
        return []
    
    asd_files = list(EXAMPLE_PROJECTS_DIR.rglob("*.asd"))
    return asd_files


def get_live_version_from_project(als_path: Path) -> Optional[str]:
    """Extract Live version from an ALS file.
    
    Args:
        als_path: Path to the .als file.
        
    Returns:
        Version string like "Ableton Live 12.3" or None if not found.
    """
    import gzip
    import xml.etree.ElementTree as ET
    
    try:
        with gzip.open(als_path, 'rb') as f:
            xml_data = f.read()
        
        root = ET.fromstring(xml_data)
        creator = root.get('Creator')
        if creator:
            return creator
        
        # Fallback: look for AbletonLiveProject element
        for elem in root.iter():
            if 'AbletonLiveProject' in elem.tag:
                creator = elem.get('Creator')
                if creator:
                    return creator
        
        return None
    except Exception:
        return None


def is_live12_project(als_path: Path) -> bool:
    """Check if an ALS file is from Live 12.
    
    Args:
        als_path: Path to the .als file.
        
    Returns:
        True if Live 12, False otherwise.
    """
    version = get_live_version_from_project(als_path)
    if version:
        return "Live 12" in version or "12." in version
    return False


def load_test_project(project_name: str) -> Optional[Path]:
    """Load a specific test project by name.
    
    Args:
        project_name: Name of the project (filename or directory name).
        
    Returns:
        Path to the .als file, or None if not found.
    """
    if not EXAMPLE_PROJECTS_DIR.exists():
        return None
    
    # Try exact match first
    exact_match = EXAMPLE_PROJECTS_DIR / f"{project_name}.als"
    if exact_match.exists():
        return exact_match
    
    # Try directory match
    dir_match = EXAMPLE_PROJECTS_DIR / project_name
    if dir_match.is_dir():
        als_file = dir_match / f"{project_name}.als"
        if als_file.exists():
            return als_file
        
        # Look for any .als file in the directory
        als_files = list(dir_match.glob("*.als"))
        if als_files:
            return als_files[0]
    
    # Try fuzzy search
    for als_file in find_example_projects():
        if project_name.lower() in als_file.name.lower() or project_name.lower() in als_file.parent.name.lower():
            return als_file
    
    return None


def get_project_markers_count(project_path: Path) -> int:
    """Get the number of timeline markers in a project (for testing).
    
    Args:
        project_path: Path to the .als file.
        
    Returns:
        Number of markers, or -1 if extraction fails.
    """
    try:
        from src.services.marker_extractor import MarkerExtractor
        extractor = MarkerExtractor()
        if not extractor.is_available:
            return -1
        
        markers = extractor.extract_markers(project_path)
        return len(markers)
    except Exception:
        return -1
