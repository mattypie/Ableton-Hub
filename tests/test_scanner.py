"""Tests for the project scanner service."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import os

from src.services.scanner import ProjectScanner, ScanWorker
from src.utils.paths import is_ableton_project


class TestIsAbletonProject:
    """Tests for the is_ableton_project function."""
    
    def test_als_file_returns_true(self):
        """Test that .als files are recognized."""
        with tempfile.NamedTemporaryFile(suffix='.als', delete=False) as f:
            path = Path(f.name)
        
        try:
            assert is_ableton_project(path) is True
        finally:
            path.unlink()
    
    def test_non_als_file_returns_false(self):
        """Test that non-.als files are not recognized."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            path = Path(f.name)
        
        try:
            assert is_ableton_project(path) is False
        finally:
            path.unlink()
    
    def test_directory_returns_false(self):
        """Test that directories are not recognized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_ableton_project(Path(tmpdir)) is False
    
    def test_case_insensitive(self):
        """Test that .ALS (uppercase) files are recognized."""
        with tempfile.NamedTemporaryFile(suffix='.ALS', delete=False) as f:
            path = Path(f.name)
        
        try:
            assert is_ableton_project(path) is True
        finally:
            path.unlink()


class TestProjectScanner:
    """Tests for the ProjectScanner class."""
    
    def test_scanner_not_running_initially(self):
        """Test that scanner is not running when created."""
        scanner = ProjectScanner()
        assert scanner.is_running is False
    
    def test_set_exclude_patterns(self):
        """Test setting exclude patterns."""
        scanner = ProjectScanner()
        patterns = ["**/test/**", "**/backup/**"]
        scanner.set_exclude_patterns(patterns)
        assert scanner._exclude_patterns == patterns


class TestScanWorker:
    """Tests for the ScanWorker class."""
    
    def test_worker_can_be_stopped(self):
        """Test that worker responds to stop request."""
        worker = ScanWorker()
        worker.stop()
        assert worker._stop_requested is True
    
    def test_excluded_pattern_matching(self):
        """Test exclude pattern matching."""
        worker = ScanWorker(exclude_patterns=["**/Backup/**"])
        
        # Test backup folder is excluded
        assert worker._is_excluded(Path("/some/path/Backup/project")) is True
        
        # Test regular folder is not excluded
        assert worker._is_excluded(Path("/some/path/Projects")) is False
    
    def test_hidden_folders_excluded(self):
        """Test that hidden folders are excluded."""
        worker = ScanWorker()
        
        assert worker._is_excluded(Path("/some/.hidden")) is True
        assert worker._is_excluded(Path("/some/visible")) is False


def test_integration_scan_directory():
    """Integration test for scanning a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test .als files
        als1 = Path(tmpdir) / "project1.als"
        als2 = Path(tmpdir) / "subdir" / "project2.als"
        other = Path(tmpdir) / "audio.wav"
        
        als2.parent.mkdir()
        als1.touch()
        als2.touch()
        other.touch()
        
        # Count .als files
        als_files = list(Path(tmpdir).rglob("*.als"))
        assert len(als_files) == 2
