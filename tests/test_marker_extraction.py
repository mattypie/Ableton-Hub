"""Tests for timeline marker extraction using dawtool."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .test_utils import (
    find_example_projects,
    get_live_version_from_project,
    is_live12_project,
    load_test_project,
    get_project_markers_count
)
from src.services.marker_extractor import MarkerExtractor


class TestMarkerExtractor:
    """Tests for MarkerExtractor service."""
    
    def test_marker_extractor_initialization(self):
        """Test that MarkerExtractor initializes correctly."""
        extractor = MarkerExtractor()
        assert extractor is not None
        
        # Check availability (may be False if dawtool not installed)
        assert isinstance(extractor.is_available, bool)
    
    def test_extract_markers_nonexistent_file(self):
        """Test extracting markers from non-existent file."""
        extractor = MarkerExtractor()
        result = extractor.extract_markers(Path("/nonexistent/file.als"))
        assert result == []
    
    @pytest.mark.skipif(not MarkerExtractor().is_available, reason="dawtool not available")
    def test_extract_markers_with_dawtool(self):
        """Test marker extraction with dawtool (if available)."""
        extractor = MarkerExtractor()
        if not extractor.is_available:
            pytest.skip("dawtool not available")
        
        # Try to find a test project
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        # Test with first available project
        test_project = projects[0]
        markers = extractor.extract_markers(test_project)
        
        # Should return a list (may be empty if no markers)
        assert isinstance(markers, list)
        
        # If markers exist, verify structure
        for marker in markers:
            assert isinstance(marker, dict)
            assert 'time' in marker
            assert 'text' in marker
            assert isinstance(marker['time'], (int, float))
            assert isinstance(marker['text'], str)
    
    def test_extract_markers_fallback_when_unavailable(self):
        """Test that extractor returns empty list when dawtool unavailable."""
        with patch('src.services.marker_extractor.DAWTOOL_AVAILABLE', False):
            extractor = MarkerExtractor()
            assert not extractor.is_available
            
            # Should return empty list even with valid path
            result = extractor.extract_markers(Path("/some/path.als"))
            assert result == []
    
    def test_marker_serialization(self):
        """Test that markers can be serialized to JSON."""
        markers = [
            {'time': 0.0, 'text': 'Start'},
            {'time': 120.5, 'text': 'Chorus'},
            {'time': 240.0, 'text': 'End'}
        ]
        
        import json
        json_str = json.dumps(markers)
        assert json_str is not None
        
        # Should be able to deserialize
        deserialized = json.loads(json_str)
        assert deserialized == markers


class TestMarkerExtractionIntegration:
    """Integration tests for marker extraction with real projects."""
    
    @pytest.mark.skipif(not MarkerExtractor().is_available, reason="dawtool not available")
    def test_markers_in_example_projects(self):
        """Test marker extraction on all example projects."""
        extractor = MarkerExtractor()
        if not extractor.is_available:
            pytest.skip("dawtool not available")
        
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        for project_path in projects[:5]:  # Limit to first 5 for performance
            try:
                markers = extractor.extract_markers(project_path)
                assert isinstance(markers, list)
                # Should not raise exception even if no markers
            except Exception as e:
                pytest.fail(f"Failed to extract markers from {project_path}: {e}")
    
    @pytest.mark.skipif(not MarkerExtractor().is_available, reason="dawtool not available")
    def test_markers_with_live12_projects(self):
        """Test marker extraction specifically with Live 12 projects."""
        extractor = MarkerExtractor()
        if not extractor.is_available:
            pytest.skip("dawtool not available")
        
        projects = find_example_projects()
        live12_projects = [p for p in projects if is_live12_project(p)]
        
        if not live12_projects:
            pytest.skip("No Live 12 example projects found")
        
        for project_path in live12_projects[:3]:  # Limit to first 3
            try:
                markers = extractor.extract_markers(project_path)
                assert isinstance(markers, list)
                # dawtool supports Live 12, so this should work
            except Exception as e:
                pytest.fail(f"Failed to extract markers from Live 12 project {project_path}: {e}")
    
    @pytest.mark.skipif(not MarkerExtractor().is_available, reason="dawtool not available")
    def test_markers_with_tempo_automation(self):
        """Test marker extraction with projects that have tempo automation.
        
        Note: dawtool supports linear tempo automation, so markers should
        be accurately positioned even with tempo changes.
        """
        extractor = MarkerExtractor()
        if not extractor.is_available:
            pytest.skip("dawtool not available")
        
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        # Test with first available project
        # Note: We can't easily detect tempo automation without parsing,
        # so we just verify extraction works
        test_project = projects[0]
        markers = extractor.extract_markers(test_project)
        
        # Should return list (may be empty)
        assert isinstance(markers, list)
        
        # If markers exist, verify they're sorted by time
        if len(markers) > 1:
            times = [m['time'] for m in markers]
            assert times == sorted(times), "Markers should be sorted by time"


class TestMarkerExtractionInParser:
    """Tests for marker extraction integrated into ALSParser."""
    
    def test_parser_with_marker_extraction(self):
        """Test that ALSParser can extract markers."""
        from src.services.als_parser import ALSParser
        
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        parser = ALSParser(extract_markers=True)
        test_project = projects[0]
        
        metadata = parser.parse(test_project)
        if metadata:
            assert hasattr(metadata, 'timeline_markers')
            assert isinstance(metadata.timeline_markers, list)
    
    def test_parser_without_marker_extraction(self):
        """Test that ALSParser can skip marker extraction."""
        from src.services.als_parser import ALSParser
        
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        parser = ALSParser(extract_markers=False)
        test_project = projects[0]
        
        metadata = parser.parse(test_project)
        if metadata:
            assert hasattr(metadata, 'timeline_markers')
            # Should be empty list when extraction disabled
            assert metadata.timeline_markers == []
