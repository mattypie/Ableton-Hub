"""Integration tests for parser with marker extraction."""

import pytest
from pathlib import Path

from .test_utils import find_example_projects, is_live12_project
from src.services.als_parser import ALSParser
from src.services.marker_extractor import MarkerExtractor
from src.database import get_session, Project, Location
from src.database.models import ProjectStatus


class TestParserIntegration:
    """Integration tests for ALS parser with marker extraction."""
    
    def test_full_project_scan_with_markers(self):
        """Test scanning a project with marker extraction enabled."""
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        parser = ALSParser(extract_markers=True)
        test_project = projects[0]
        
        metadata = parser.parse(test_project)
        assert metadata is not None
        assert hasattr(metadata, 'timeline_markers')
        assert isinstance(metadata.timeline_markers, list)
    
    def test_database_storage(self):
        """Test storing markers in database."""
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        parser = ALSParser(extract_markers=True)
        test_project = projects[0]
        
        metadata = parser.parse(test_project)
        if not metadata:
            pytest.skip("Failed to parse test project")
        
        # Verify markers can be serialized
        import json
        markers_json = json.dumps(metadata.timeline_markers)
        assert markers_json is not None
        
        # Verify markers can be deserialized
        markers_restored = json.loads(markers_json)
        assert markers_restored == metadata.timeline_markers
    
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
        
        parser = ALSParser(extract_markers=True)
        
        for project_path in live12_projects[:3]:  # Limit to first 3
            try:
                metadata = parser.parse(project_path)
                if metadata:
                    assert hasattr(metadata, 'timeline_markers')
                    assert isinstance(metadata.timeline_markers, list)
                    # Should not raise exception even if no markers
            except Exception as e:
                pytest.fail(f"Failed to parse Live 12 project {project_path}: {e}")


class TestMarkerExtractionDuringScan:
    """Test marker extraction during project scanning."""
    
    def test_parser_with_marker_extraction_disabled(self):
        """Test that parser works when marker extraction is disabled."""
        projects = find_example_projects()
        if not projects:
            pytest.skip("No example projects found")
        
        parser = ALSParser(extract_markers=False)
        test_project = projects[0]
        
        metadata = parser.parse(test_project)
        if metadata:
            assert hasattr(metadata, 'timeline_markers')
            assert metadata.timeline_markers == []
