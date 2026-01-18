"""Tests for export tracking functionality."""

import pytest
from src.utils.fuzzy_match import (
    calculate_similarity,
    normalize_for_comparison,
    fuzzy_match_projects,
    match_export_to_project,
    extract_song_name
)


class TestNormalizeForComparison:
    """Tests for string normalization."""
    
    def test_removes_extension(self):
        """Test that file extensions are removed."""
        assert "song" in normalize_for_comparison("song.als")
        assert "song" in normalize_for_comparison("song.wav")
    
    def test_removes_version_suffix(self):
        """Test that version numbers are removed."""
        result = normalize_for_comparison("my_song_v3")
        assert "v3" not in result
    
    def test_removes_final_suffix(self):
        """Test that common suffixes are removed."""
        result = normalize_for_comparison("my_song_final")
        assert "final" not in result
        
        result = normalize_for_comparison("my_song_master")
        assert "master" not in result
    
    def test_standardizes_separators(self):
        """Test that separators are standardized."""
        result = normalize_for_comparison("my-song_name")
        assert "-" not in result or "_" not in result
    
    def test_lowercase(self):
        """Test that result is lowercase."""
        result = normalize_for_comparison("MY_SONG")
        assert result == result.lower()


class TestCalculateSimilarity:
    """Tests for similarity calculation."""
    
    def test_identical_strings(self):
        """Test that identical strings have 100% similarity."""
        score = calculate_similarity("test", "test")
        assert score >= 99  # Allow small floating point variance
    
    def test_completely_different(self):
        """Test that different strings have low similarity."""
        score = calculate_similarity("aaa", "zzz")
        assert score < 50
    
    def test_similar_strings(self):
        """Test that similar strings have high similarity."""
        score = calculate_similarity("my song", "my_song")
        assert score > 80
    
    def test_partial_match(self):
        """Test partial matching."""
        score = calculate_similarity("song", "my song final")
        assert score > 50


class TestFuzzyMatchProjects:
    """Tests for project fuzzy matching."""
    
    def test_exact_match(self):
        """Test exact matching."""
        projects = ["Song A", "Song B", "Song C"]
        results = fuzzy_match_projects("Song A", projects)
        
        assert len(results) > 0
        assert results[0].matched_text == "Song A"
        assert results[0].score >= 99
    
    def test_similar_match(self):
        """Test similar string matching."""
        projects = ["Beach Vibes", "Mountain Song", "Ocean Wave"]
        results = fuzzy_match_projects("beach_vibes", projects)
        
        assert len(results) > 0
        assert results[0].matched_text == "Beach Vibes"
    
    def test_threshold_filtering(self):
        """Test that results below threshold are filtered."""
        projects = ["AAA", "BBB", "CCC"]
        results = fuzzy_match_projects("XYZ", projects, threshold=90)
        
        assert len(results) == 0
    
    def test_limit_results(self):
        """Test that results are limited."""
        projects = [f"Song {i}" for i in range(20)]
        results = fuzzy_match_projects("Song", projects, limit=5)
        
        assert len(results) <= 5


class TestMatchExportToProject:
    """Tests for export-to-project matching."""
    
    def test_match_with_suffix(self):
        """Test matching exports with common suffixes."""
        projects = ["Beach Song", "Mountain Song"]
        results = match_export_to_project("Beach_Song_Final_Master", projects)
        
        assert len(results) > 0
        assert results[0][0] == "Beach Song"
    
    def test_match_with_version(self):
        """Test matching exports with version numbers."""
        projects = ["My Track", "Other Track"]
        results = match_export_to_project("My_Track_v3", projects)
        
        assert len(results) > 0
        assert results[0][0] == "My Track"
    
    def test_returns_sorted_by_score(self):
        """Test that results are sorted by score descending."""
        projects = ["AAA", "AA", "A"]
        results = match_export_to_project("AAA", projects)
        
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestExtractSongName:
    """Tests for song name extraction."""
    
    def test_removes_track_number(self):
        """Test that track numbers are removed."""
        result = extract_song_name("01 - My Song")
        assert result == "My Song"
        
        result = extract_song_name("01_My Song")
        assert "01" not in result
    
    def test_extracts_from_album_format(self):
        """Test extraction from album format."""
        result = extract_song_name("Artist - Album - Song Title")
        assert result == "Song Title"
    
    def test_removes_parenthetical(self):
        """Test that parenthetical suffixes are removed."""
        result = extract_song_name("My Song (Radio Edit)")
        assert "(Radio Edit)" not in result
    
    def test_removes_brackets(self):
        """Test that bracketed suffixes are removed."""
        result = extract_song_name("My Song [Remix]")
        assert "[Remix]" not in result
    
    def test_handles_simple_name(self):
        """Test handling of simple names."""
        result = extract_song_name("Simple Song")
        assert result == "Simple Song"
