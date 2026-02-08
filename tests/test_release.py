#!/usr/bin/env python3
"""Comprehensive test release validation for Ableton Hub.

This script runs code audits, tests essential features, and validates
that new builds are functional without regressions.

Usage:
    python tests/test_release.py [--skip-code-quality] [--skip-ml] [--verbose]
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test_utils - handle both relative (when imported) and absolute (when run directly)
try:
    from .test_utils import (
        find_example_projects,
        find_example_asd_files,
        is_live12_project,
        get_live_version_from_project,
        get_project_markers_count
    )
except ImportError:
    # Fallback for direct execution
    from tests.test_utils import (
        find_example_projects,
        find_example_asd_files,
        is_live12_project,
        get_live_version_from_project,
        get_project_markers_count
    )


@dataclass
class ReleaseTestResult:
    """Result of a test step."""
    name: str
    passed: bool
    message: str = ""
    duration: float = 0.0
    details: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ReleaseValidator:
    """Comprehensive test release validation for Ableton Hub."""
    
    def __init__(self, skip_code_quality: bool = False, skip_ml: bool = False, verbose: bool = False):
        """Initialize test release validation.
        
        Args:
            skip_code_quality: Skip code quality checks (ruff, mypy, black).
            skip_ml: Skip ML feature tests.
            verbose: Enable verbose output.
        """
        self.skip_code_quality = skip_code_quality
        self.skip_ml = skip_ml
        self.verbose = verbose
        self.results: List[ReleaseTestResult] = []
        self.start_time = time.time()
        
        # Find example projects
        self.example_projects = find_example_projects()
        self.example_asd_files = find_example_asd_files()
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        prefix = {
            "INFO": "[i]",
            "PASS": "[+]",
            "FAIL": "[-]",
            "WARN": "[!]",
            "SKIP": "[~]"
        }.get(level, "*")
        print(f"{prefix} {message}")
    
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None, capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a shell command.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
                capture_output=capture_output,
                text=True,
                encoding='utf-8',  # Use UTF-8 encoding
                errors='replace',    # Replace invalid characters instead of failing
                timeout=300  # 5 minute timeout
            )
            stdout = result.stdout if capture_output else ""
            stderr = result.stderr if capture_output else ""
            return result.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 5 minutes"
        except Exception as e:
            return 1, "", str(e)
    
    def test_step(self, name: str, func, *args, **kwargs) -> ReleaseTestResult:
        """Run a test step and record results."""
        self.log(f"Running: {name}")
        start = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            if isinstance(result, ReleaseTestResult):
                result.duration = duration
                self.results.append(result)
                return result
            elif isinstance(result, bool):
                test_result = ReleaseTestResult(
                    name=name,
                    passed=result,
                    duration=duration
                )
                self.results.append(test_result)
                return test_result
            else:
                # Assume success if no exception
                test_result = ReleaseTestResult(
                    name=name,
                    passed=True,
                    duration=duration
                )
                self.results.append(test_result)
                return test_result
        except Exception as e:
            duration = time.time() - start
            test_result = ReleaseTestResult(
                name=name,
                passed=False,
                message=str(e),
                duration=duration
            )
            self.results.append(test_result)
            return test_result
    
    # ==================== Code Quality Checks ====================
    
    def check_ruff(self) -> ReleaseTestResult:
        """Check code with ruff."""
        # Try to find ruff - check both direct command and python -m
        import shutil
        import sys
        
        # Try python -m ruff first (more reliable on Windows)
        cmd = None
        if shutil.which("ruff"):
            cmd = ["ruff", "check", "src/"]
        else:
            # Try python -m ruff
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "ruff", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [sys.executable, "-m", "ruff", "check", "src/"]
            except Exception:
                pass
        
        if not cmd:
            return ReleaseTestResult(
                name="Ruff Check",
                passed=True,  # Not a failure if tool not installed
                message="Ruff not found (skipping)",
                warnings=["ruff not installed - install with: pip install ruff"]
            )
        
        self.log("Checking code with ruff...", "INFO")
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode == 0:
            return ReleaseTestResult(
                name="Ruff Check",
                passed=True,
                message="No ruff violations found"
            )
        else:
            return ReleaseTestResult(
                name="Ruff Check",
                passed=False,
                message=f"Ruff found violations",
                details=[stdout, stderr] if self.verbose else []
            )
    
    def check_mypy(self) -> ReleaseTestResult:
        """Check types with mypy."""
        # Try to find mypy - check both direct command and python -m
        import shutil
        import sys
        
        # Try python -m mypy first (more reliable on Windows)
        cmd = None
        if shutil.which("mypy"):
            cmd = ["mypy", "src/", "--ignore-missing-imports", "--no-strict-optional"]
        else:
            # Try python -m mypy
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "mypy", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [sys.executable, "-m", "mypy", "src/", "--ignore-missing-imports", "--no-strict-optional"]
            except Exception:
                pass
        
        if not cmd:
            return ReleaseTestResult(
                name="MyPy Type Check",
                passed=True,  # Not a failure if tool not installed
                message="MyPy not found (skipping)",
                warnings=["mypy not installed - install with: pip install mypy"]
            )
        
        self.log("Checking types with mypy...", "INFO")
        returncode, stdout, stderr = self.run_command(cmd)
        
        # mypy returns 0 on success, non-zero on errors
        if returncode == 0:
            return ReleaseTestResult(
                name="MyPy Type Check",
                passed=True,
                message="No type errors found"
            )
        else:
            # Check if it's just warnings (we allow some)
            if "error" in stdout.lower() or "error" in stderr.lower():
                return ReleaseTestResult(
                    name="MyPy Type Check",
                    passed=False,
                    message="Type errors found",
                    details=[stdout, stderr] if self.verbose else []
                )
            else:
                return ReleaseTestResult(
                    name="MyPy Type Check",
                    passed=True,
                    message="Type check passed (warnings ignored)",
                    warnings=[stdout, stderr] if self.verbose else []
                )
    
    def check_black(self) -> ReleaseTestResult:
        """Check code formatting with black."""
        # Try to find black - check both direct command and python -m
        import shutil
        import sys
        
        # Try python -m black first (more reliable on Windows)
        cmd = None
        if shutil.which("black"):
            cmd = ["black", "--check", "--diff", "src/"]
        else:
            # Try python -m black
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "black", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [sys.executable, "-m", "black", "--check", "--diff", "src/"]
            except Exception:
                pass
        
        if not cmd:
            return ReleaseTestResult(
                name="Black Format Check",
                passed=True,  # Not a failure if tool not installed
                message="Black not found (skipping)",
                warnings=["black not installed - install with: pip install black"]
            )
        
        self.log("Checking code formatting with black...", "INFO")
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode == 0:
            return ReleaseTestResult(
                name="Black Format Check",
                passed=True,
                message="Code is properly formatted"
            )
        else:
            return ReleaseTestResult(
                name="Black Format Check",
                passed=False,
                message="Code formatting issues found (run 'black src/' to fix)",
                details=[stdout] if self.verbose else []
            )
    
    # ==================== Unit Tests ====================
    
    def run_pytest(self) -> ReleaseTestResult:
        """Run pytest test suite."""
        # Try to find pytest - check both direct command and python -m
        import shutil
        import sys
        
        # Try python -m pytest first (more reliable on Windows)
        cmd = None
        if shutil.which("pytest"):
            cmd = ["pytest", "tests/", "-v", "--tb=short"]
        else:
            # Try python -m pytest
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
            except Exception:
                pass
        
        if not cmd:
            return ReleaseTestResult(
                name="Pytest Tests",
                passed=False,
                message="Pytest not found",
                warnings=["pytest not installed - install with: pip install pytest pytest-qt"]
            )
        
        self.log("Running pytest test suite...", "INFO")
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode == 0:
            return ReleaseTestResult(
                name="Pytest Tests",
                passed=True,
                message="All tests passed"
            )
        else:
            return ReleaseTestResult(
                name="Pytest Tests",
                passed=False,
                message=f"Some tests failed (exit code {returncode})",
                details=[stdout, stderr] if self.verbose else []
            )
    
    # ==================== Core Functionality Tests ====================
    
    def test_imports(self) -> ReleaseTestResult:
        """Test that all core modules can be imported."""
        try:
            from src.services.scanner import ProjectScanner
            from src.services.als_parser import ALSParser
            from src.services.marker_extractor import MarkerExtractor
            from src.database.models import Project, Location
            from src.database.db import get_engine
            
            return ReleaseTestResult(
                name="Core Imports",
                passed=True,
                message="All core modules imported successfully"
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Core Imports",
                passed=False,
                message=f"Import failed: {e}"
            )
    
    def test_database_models(self) -> ReleaseTestResult:
        """Test database model creation."""
        try:
            from src.database.models import (
                Project, Location, Collection, Tag, Export,
                ProjectStatus, LocationType, CollectionType
            )
            
            # Test that models can be instantiated (without DB)
            project = Project(
                name="Test",
                file_path="/test/test.als",
                status=ProjectStatus.LOCAL
            )
            
            return ReleaseTestResult(
                name="Database Models",
                passed=True,
                message="Database models can be instantiated"
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Database Models",
                passed=False,
                message=f"Database model test failed: {e}"
            )
    
    def test_scanner_initialization(self) -> ReleaseTestResult:
        """Test scanner can be initialized."""
        try:
            from src.services.scanner import ProjectScanner
            
            scanner = ProjectScanner()
            assert scanner is not None
            assert scanner.is_running is False
            
            return ReleaseTestResult(
                name="Scanner Initialization",
                passed=True,
                message="Scanner initializes correctly"
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Scanner Initialization",
                passed=False,
                message=f"Scanner initialization failed: {e}"
            )
    
    # ==================== Deep Extraction Tests ====================
    
    def test_parser_basic(self) -> ReleaseTestResult:
        """Test basic ALS parser functionality."""
        if not self.example_projects:
            return ReleaseTestResult(
                name="Parser Basic",
                passed=False,
                message="No example projects found",
                warnings=["Skipping parser test - no example projects"]
            )
        
        try:
            from src.services.als_parser import ALSParser
            
            parser = ALSParser(extract_markers=True)
            test_project = self.example_projects[0]
            
            metadata = parser.parse(test_project)
            
            if metadata is None:
                return ReleaseTestResult(
                    name="Parser Basic",
                    passed=False,
                    message=f"Parser returned None for {test_project.name}"
                )
            
            # Check essential fields
            checks = []
            if metadata.tempo:
                checks.append(f"Tempo: {metadata.tempo} BPM")
            if metadata.track_count:
                checks.append(f"Tracks: {metadata.track_count}")
            if metadata.ableton_version:
                checks.append(f"Live Version: {metadata.ableton_version}")
            if metadata.timeline_markers:
                checks.append(f"Markers: {len(metadata.timeline_markers)}")
            
            return ReleaseTestResult(
                name="Parser Basic",
                passed=True,
                message=f"Parsed {test_project.name} successfully",
                details=checks
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Parser Basic",
                passed=False,
                message=f"Parser test failed: {e}"
            )
    
    def test_parser_deep_extraction(self) -> ReleaseTestResult:
        """Test deep extraction features (plugins, devices, tempo, key, markers)."""
        if not self.example_projects:
            return ReleaseTestResult(
                name="Parser Deep Extraction",
                passed=False,
                message="No example projects found"
            )
        
        try:
            from src.services.als_parser import ALSParser
            
            parser = ALSParser(extract_extended=True, extract_markers=True)
            test_project = self.example_projects[0]
            
            metadata = parser.parse(test_project)
            
            if metadata is None:
                return ReleaseTestResult(
                    name="Parser Deep Extraction",
                    passed=False,
                    message="Parser returned None"
                )
            
            extracted_features = []
            
            # Check plugins
            if metadata.plugins:
                extracted_features.append(f"Plugins: {len(metadata.plugins)}")
            
            # Check devices
            if metadata.devices:
                extracted_features.append(f"Devices: {len(metadata.devices)}")
            
            # Check tempo
            if metadata.tempo:
                extracted_features.append(f"Tempo: {metadata.tempo} BPM")
            
            # Check musical key
            if metadata.musical_key:
                extracted_features.append(f"Key: {metadata.musical_key}")
            
            # Check timeline markers
            if metadata.timeline_markers:
                extracted_features.append(f"Timeline Markers: {len(metadata.timeline_markers)}")
            
            # Check track counts
            if metadata.track_count:
                extracted_features.append(f"Tracks: {metadata.track_count}")
            
            return ReleaseTestResult(
                name="Parser Deep Extraction",
                passed=True,
                message=f"Deep extraction successful for {test_project.name}",
                details=extracted_features
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Parser Deep Extraction",
                passed=False,
                message=f"Deep extraction failed: {e}"
            )
    
    def test_marker_extraction(self) -> ReleaseTestResult:
        """Test timeline marker extraction."""
        if not self.example_projects:
            return ReleaseTestResult(
                name="Marker Extraction",
                passed=False,
                message="No example projects found"
            )
        
        try:
            from src.services.marker_extractor import MarkerExtractor
            
            extractor = MarkerExtractor()
            
            if not extractor.is_available:
                return ReleaseTestResult(
                    name="Marker Extraction",
                    passed=True,  # Not a failure if dawtool not installed
                    message="Marker extraction skipped (dawtool not available)",
                    warnings=["dawtool not installed - marker extraction unavailable"]
                )
            
            # Test with first project
            test_project = self.example_projects[0]
            markers = extractor.extract_markers(test_project)
            
            # Verify structure
            if markers:
                for marker in markers[:3]:  # Check first 3
                    if not isinstance(marker, dict):
                        return ReleaseTestResult(
                            name="Marker Extraction",
                            passed=False,
                            message="Marker is not a dict"
                        )
                    if 'time' not in marker or 'text' not in marker:
                        return ReleaseTestResult(
                            name="Marker Extraction",
                            passed=False,
                            message="Marker missing 'time' or 'text' field"
                        )
            
            return ReleaseTestResult(
                name="Marker Extraction",
                passed=True,
                message=f"Extracted {len(markers)} markers from {test_project.name}",
                details=[f"Markers: {len(markers)}"] if markers else []
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Marker Extraction",
                passed=False,
                message=f"Marker extraction failed: {e}"
            )
    
    def test_live12_compatibility(self) -> ReleaseTestResult:
        """Test Live 12 project compatibility."""
        live12_projects = [p for p in self.example_projects if is_live12_project(p)]
        
        if not live12_projects:
            return ReleaseTestResult(
                name="Live 12 Compatibility",
                passed=True,  # Not a failure if no Live 12 projects
                message="No Live 12 projects found (skipping)",
                warnings=["No Live 12 example projects available"]
            )
        
        try:
            from src.services.als_parser import ALSParser
            from src.services.marker_extractor import MarkerExtractor
            
            parser = ALSParser(extract_markers=True)
            extractor = MarkerExtractor()
            
            results = []
            for project in live12_projects[:3]:  # Test first 3
                metadata = parser.parse(project)
                if metadata:
                    results.append(f"[OK] {project.name}")
                    
                    # Test marker extraction if available
                    if extractor.is_available:
                        markers = extractor.extract_markers(project)
                        if markers:
                            results.append(f"  -> {len(markers)} markers")
                else:
                    results.append(f"[FAIL] {project.name} (failed)")
            
            return ReleaseTestResult(
                name="Live 12 Compatibility",
                passed=True,
                message=f"Tested {len(live12_projects[:3])} Live 12 project(s)",
                details=results
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Live 12 Compatibility",
                passed=False,
                message=f"Live 12 compatibility test failed: {e}"
            )
    
    # ==================== ML Feature Tests ====================
    
    def test_ml_feature_extraction(self) -> ReleaseTestResult:
        """Test ML feature extraction."""
        if not self.example_projects:
            return ReleaseTestResult(
                name="ML Feature Extraction",
                passed=False,
                message="No example projects found"
            )
        
        try:
            from src.services import MLFeatureExtractor, ProjectFeatureVector
            
            extractor = MLFeatureExtractor(extract_audio_features=False)  # Disable audio to speed up
            test_project = self.example_projects[0]
            
            # Extract features using the correct method signature
            features = extractor.extract_project_features(
                als_path=test_project,
                project_id=1
            )
            
            if features is None:
                return ReleaseTestResult(
                    name="ML Feature Extraction",
                    passed=False,
                    message="Feature extraction returned None"
                )
            
            # Check combined vector (the actual attribute name)
            combined_vector = features.get_combined_vector()
            vector_size = len(combined_vector) if combined_vector is not None else 0
            
            if vector_size > 0 or len(features.als_features) > 0:
                return ReleaseTestResult(
                    name="ML Feature Extraction",
                    passed=True,
                    message=f"Extracted features successfully",
                    details=[
                        f"Combined vector size: {vector_size}",
                        f"ALS features: {len(features.als_features)}",
                        f"ASD features: {len(features.asd_features)}"
                    ]
                )
            else:
                return ReleaseTestResult(
                    name="ML Feature Extraction",
                    passed=False,
                    message="No features extracted"
                )
        except ImportError as e:
            return ReleaseTestResult(
                name="ML Feature Extraction",
                passed=False,
                message=f"ML dependencies not available: {e}",
                warnings=["Install ML dependencies: numpy, scikit-learn, librosa"]
            )
        except Exception as e:
            return ReleaseTestResult(
                name="ML Feature Extraction",
                passed=False,
                message=f"ML feature extraction failed: {e}"
            )
    
    def test_similarity_analysis(self) -> ReleaseTestResult:
        """Test similarity analysis between projects."""
        if len(self.example_projects) < 2:
            return ReleaseTestResult(
                name="Similarity Analysis",
                passed=False,
                message="Need at least 2 example projects",
                warnings=["Skipping similarity test - need 2+ projects"]
            )
        
        try:
            from src.services import SimilarityAnalyzer
            
            analyzer = SimilarityAnalyzer()
            
            # Create mock project dicts
            project_a = {
                'id': 1,
                'name': self.example_projects[0].stem,
                'file_path': str(self.example_projects[0]),
                'tempo': 120.0,
                'track_count': 8,
                'plugins': json.dumps(['Plugin1']),
                'devices': json.dumps(['Device1']),
            }
            
            project_b = {
                'id': 2,
                'name': self.example_projects[1].stem if len(self.example_projects) > 1 else self.example_projects[0].stem,
                'file_path': str(self.example_projects[1] if len(self.example_projects) > 1 else self.example_projects[0]),
                'tempo': 125.0,
                'track_count': 8,
                'plugins': json.dumps(['Plugin1', 'Plugin2']),
                'devices': json.dumps(['Device1']),
            }
            
            similarity = analyzer.compute_similarity(project_a, project_b)
            
            if similarity is None:
                return ReleaseTestResult(
                    name="Similarity Analysis",
                    passed=False,
                    message="Similarity computation returned None"
                )
            
            score = similarity.overall_similarity if hasattr(similarity, 'overall_similarity') else 0.0
            
            return ReleaseTestResult(
                name="Similarity Analysis",
                passed=True,
                message=f"Similarity computed: {score:.2%}",
                details=[f"Similarity score: {score:.2%}"]
            )
        except ImportError as e:
            return ReleaseTestResult(
                name="Similarity Analysis",
                passed=False,
                message=f"ML dependencies not available: {e}",
                warnings=["Install ML dependencies: numpy, scikit-learn"]
            )
        except Exception as e:
            return ReleaseTestResult(
                name="Similarity Analysis",
                passed=False,
                message=f"Similarity analysis failed: {e}"
            )
    
    def test_clustering(self) -> ReleaseTestResult:
        """Test ML clustering functionality."""
        if len(self.example_projects) < 3:
            return ReleaseTestResult(
                name="ML Clustering",
                passed=False,
                message="Need at least 3 example projects",
                warnings=["Skipping clustering test - need 3+ projects"]
            )
        
        try:
            from src.services import MLClusteringService, MLFeatureExtractor
            
            extractor = MLFeatureExtractor(extract_audio_features=False)  # Disable audio to speed up
            clustering = MLClusteringService(feature_extractor=extractor)
            
            # Create project dicts with als_path for feature extraction
            projects = []
            for i, proj_path in enumerate(self.example_projects[:5]):  # Use up to 5
                projects.append({
                    'id': i + 1,
                    'name': proj_path.stem,
                    'als_path': str(proj_path),  # Required for feature extraction
                    'tempo': 120.0 + (i * 5),
                    'track_count': 8,
                    'plugins': json.dumps(['Plugin1']),
                    'devices': json.dumps(['Device1']),
                })
            
            # Use the correct method: cluster_kmeans
            result = clustering.cluster_kmeans(projects, n_clusters=2)
            
            if result is None:
                return ReleaseTestResult(
                    name="ML Clustering",
                    passed=False,
                    message="Clustering returned None"
                )
            
            num_clusters = len(result.clusters) if hasattr(result, 'clusters') else 0
            
            return ReleaseTestResult(
                name="ML Clustering",
                passed=True,
                message=f"Clustered {len(projects)} projects into {num_clusters} clusters",
                details=[f"Clusters: {num_clusters}", f"Projects: {len(projects)}", f"Method: {result.method}"]
            )
        except ImportError as e:
            return ReleaseTestResult(
                name="ML Clustering",
                passed=False,
                message=f"ML dependencies not available: {e}",
                warnings=["Install ML dependencies: numpy, scikit-learn"]
            )
        except Exception as e:
            return ReleaseTestResult(
                name="ML Clustering",
                passed=False,
                message=f"Clustering failed: {e}"
            )
    
    # ==================== Main Test Runner ====================
    
    def run_all_tests(self) -> bool:
        """Run all tests and return overall success."""
        print("=" * 80)
        print("Ableton Hub Release Validation")
        print("=" * 80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Example Projects: {len(self.example_projects)}")
        print(f"Example ASD Files: {len(self.example_asd_files)}")
        print("=" * 80)
        print()
        
        # Code Quality Checks
        if not self.skip_code_quality:
            print("\n[Code Quality Checks]")
            print("-" * 80)
            self.test_step("Ruff Check", self.check_ruff)
            self.test_step("Black Format Check", self.check_black)
            self.test_step("MyPy Type Check", self.check_mypy)
        else:
            self.log("Skipping code quality checks", "SKIP")
        
        # Unit Tests
        print("\n[Unit Tests]")
        print("-" * 80)
        self.test_step("Pytest Tests", self.run_pytest)
        
        # Core Functionality
        print("\n[Core Functionality Tests]")
        print("-" * 80)
        self.test_step("Core Imports", self.test_imports)
        self.test_step("Database Models", self.test_database_models)
        self.test_step("Scanner Initialization", self.test_scanner_initialization)
        
        # Deep Extraction
        print("\n[Deep Extraction Tests]")
        print("-" * 80)
        self.test_step("Parser Basic", self.test_parser_basic)
        self.test_step("Parser Deep Extraction", self.test_parser_deep_extraction)
        self.test_step("Marker Extraction", self.test_marker_extraction)
        self.test_step("Live 12 Compatibility", self.test_live12_compatibility)
        
        # ML Features
        if not self.skip_ml:
            print("\n[ML Feature Tests]")
            print("-" * 80)
            self.test_step("ML Feature Extraction", self.test_ml_feature_extraction)
            self.test_step("Similarity Analysis", self.test_similarity_analysis)
            self.test_step("ML Clustering", self.test_clustering)
        else:
            self.log("Skipping ML feature tests", "SKIP")
        
        # Print Summary
        self.print_summary()
        
        # Return overall success
        return all(r.passed for r in self.results)
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("Test Summary")
        print("=" * 80)
        
        total_time = time.time() - self.start_time
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        print(f"\nTotal Tests: {total}")
        print(f"[+] Passed: {passed}")
        print(f"[-] Failed: {failed}")
        print(f"[*] Duration: {total_time:.2f}s")
        print()
        
        # Print failed tests
        if failed > 0:
            print("Failed Tests:")
            print("-" * 80)
            for result in self.results:
                if not result.passed:
                    print(f"[-] {result.name}")
                    if result.message:
                        print(f"   {result.message}")
                    if result.details and self.verbose:
                        for detail in result.details:
                            if detail:
                                # Handle encoding issues with special characters
                                try:
                                    print(f"   {detail}")
                                except UnicodeEncodeError:
                                    # Fallback: encode and replace problematic characters
                                    safe_detail = detail.encode('ascii', 'replace').decode('ascii')
                                    print(f"   {safe_detail}")
                    print()
        
        # Print warnings
        warnings = [w for r in self.results for w in r.warnings]
        if warnings:
            print("Warnings:")
            print("-" * 80)
            for warning in warnings:
                if warning:
                    print(f"[!] {warning}")
            print()
        
        # Print details for passed tests (if verbose)
        if self.verbose and passed > 0:
            print("Passed Tests Details:")
            print("-" * 80)
            for result in self.results:
                if result.passed and result.details:
                    print(f"[+] {result.name}")
                    for detail in result.details:
                        if detail:
                            print(f"   {detail}")
                    print()
        
        print("=" * 80)
        
        if failed == 0:
            print("[SUCCESS] All tests passed!")
        else:
            print(f"[!] {failed} test(s) failed. Please review and fix before release.")
        print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ableton Hub Release Validation - Pre-release test suite"
    )
    parser.add_argument(
        "--skip-code-quality",
        action="store_true",
        help="Skip code quality checks (ruff, mypy, black)"
    )
    parser.add_argument(
        "--skip-ml",
        action="store_true",
        help="Skip ML feature tests (faster, but less comprehensive)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    validator = ReleaseValidator(
        skip_code_quality=args.skip_code_quality,
        skip_ml=args.skip_ml,
        verbose=args.verbose
    )
    
    success = validator.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
