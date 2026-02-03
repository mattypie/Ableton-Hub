"""ML Feature Extraction Service for Ableton Projects.

This service extracts and combines features from multiple sources:
1. ALS project metadata (structure, plugins, devices)
2. ASD clip analysis data (warp markers, transients)
3. Audio content features (using librosa)

The extracted features are used for:
- Project similarity detection
- Clustering and grouping
- Recommendation systems
- Auto-tagging

NOTE: Heavy imports (numpy, sklearn, librosa) are deferred until first use
to avoid slowing down application startup.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from ..utils.logging import get_logger

# Type checking imports (not loaded at runtime)
if TYPE_CHECKING:
    import numpy as np

# Lazy import cache
_np = None
_librosa = None
_sklearn_scaler = None
_LIBROSA_AVAILABLE = None
_SKLEARN_AVAILABLE = None


def _get_numpy():
    """Lazy-load numpy."""
    global _np
    if _np is None:
        import numpy
        _np = numpy
    return _np


def _check_librosa():
    """Check if librosa is available (lazy)."""
    global _LIBROSA_AVAILABLE, _librosa
    if _LIBROSA_AVAILABLE is None:
        try:
            import librosa
            import soundfile as sf
            _librosa = librosa
            _LIBROSA_AVAILABLE = True
        except ImportError:
            _LIBROSA_AVAILABLE = False
    return _LIBROSA_AVAILABLE


def _check_sklearn():
    """Check if sklearn is available (lazy)."""
    global _SKLEARN_AVAILABLE, _sklearn_scaler
    if _SKLEARN_AVAILABLE is None:
        try:
            from sklearn.preprocessing import StandardScaler
            _sklearn_scaler = StandardScaler
            _SKLEARN_AVAILABLE = True
        except ImportError:
            _SKLEARN_AVAILABLE = False
    return _SKLEARN_AVAILABLE


# Import project parsers (these are lightweight)
from .als_parser import ALSParser, ProjectMetadata
from .asd_parser import ASDParser, ClipAnalysisData, find_asd_files


@dataclass
class AudioFeatures:
    """Audio content features extracted with librosa."""
    # Tempo and rhythm
    tempo: float = 0.0
    beat_strength: float = 0.0
    tempo_stability: float = 0.0
    
    # Spectral features
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_contrast: float = 0.0
    
    # Tonal features
    chroma_mean: float = 0.0
    estimated_key: Optional[str] = None
    key_confidence: float = 0.0
    
    # Energy and dynamics
    rms_mean: float = 0.0
    rms_std: float = 0.0
    zero_crossing_rate: float = 0.0
    
    # MFCCs (mean of each coefficient)
    mfcc_means: List[float] = field(default_factory=list)
    
    # Duration and sample info
    duration: float = 0.0
    sample_rate: int = 44100


@dataclass
class ProjectFeatureVector:
    """Complete feature vector for a project."""
    project_id: Optional[int] = None
    project_path: Optional[str] = None
    
    # Raw features from different sources
    als_features: List[float] = field(default_factory=list)
    asd_features: List[float] = field(default_factory=list)
    audio_features: List[float] = field(default_factory=list)
    
    # Combined normalized feature vector (numpy array, lazy-loaded)
    combined_vector: Any = field(default_factory=lambda: None)
    
    # Feature metadata
    feature_names: List[str] = field(default_factory=list)
    extraction_timestamp: Optional[str] = None
    
    def get_combined_vector(self):
        """Get combined vector as numpy array."""
        if self.combined_vector is None:
            np = _get_numpy()
            return np.array([])
        return self.combined_vector


class MLFeatureExtractor:
    """Service for extracting ML-ready features from Ableton projects.
    
    Combines features from:
    - ALS project structure and metadata
    - ASD clip analysis files
    - Audio content analysis (optional, requires librosa)
    """
    
    # Key names for chroma-based key detection
    KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def __init__(self, 
                 extract_audio_features: bool = True,
            use_extended_als: bool = True,
            normalize_features: bool = True):
        """Initialize the feature extractor.
        
        Args:
            extract_audio_features: Whether to extract audio content features.
            use_extended_als: Whether to use extended ALS metadata extraction.
            normalize_features: Whether to normalize the combined feature vector.
        """
        self.logger = get_logger(__name__)
        self._als_parser = ALSParser(extract_extended=use_extended_als)
        self._asd_parser = ASDParser()
        self._extract_audio_requested = extract_audio_features
        self._normalize_requested = normalize_features
        
        # Feature scalers (created lazily)
        self._scaler = None
        self._scaler_fitted = False
        
        # Cache for extracted features
        self._feature_cache: Dict[str, ProjectFeatureVector] = {}
    
    @property
    def _extract_audio(self) -> bool:
        """Check if audio extraction is enabled and available."""
        return self._extract_audio_requested and _check_librosa()
    
    @property
    def _normalize(self) -> bool:
        """Check if normalization is enabled and available."""
        return self._normalize_requested and _check_sklearn()
    
    def _get_scaler(self):
        """Get or create the feature scaler (lazy)."""
        if self._scaler is None and self._normalize:
            self._scaler = _sklearn_scaler()
        return self._scaler
    
    def extract_project_features(self, 
                                  als_path: Path,
                                  project_id: Optional[int] = None,
                                  audio_paths: Optional[List[Path]] = None
                                  ) -> Optional[ProjectFeatureVector]:
        """Extract all features from an Ableton project.
        
        Args:
            als_path: Path to the .als project file.
            project_id: Optional database ID for the project.
            audio_paths: Optional list of audio file paths to analyze.
            
        Returns:
            ProjectFeatureVector containing all extracted features.
        """
        if not als_path.exists():
            return None
        
        # Check cache
        cache_key = f"{als_path}_{als_path.stat().st_mtime}"
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]
        
        result = ProjectFeatureVector(
            project_id=project_id,
            project_path=str(als_path)
        )
        
        # Extract ALS features
        metadata = self._als_parser.parse(als_path)
        if metadata:
            result.als_features = self._als_parser.generate_feature_vector(metadata)
        
        # Extract ASD features from project directory
        project_dir = als_path.parent
        asd_files = find_asd_files(project_dir)
        if asd_files:
            asd_features = self._extract_aggregated_asd_features(asd_files)
            result.asd_features = asd_features
        
        # Extract audio features if enabled
        if self._extract_audio and audio_paths:
            audio_feats = self._extract_aggregated_audio_features(audio_paths)
            result.audio_features = audio_feats
        
        # Combine all features into a single vector
        result.combined_vector = self._combine_features(result)
        result.feature_names = self.get_combined_feature_names()
        
        # Cache result
        self._feature_cache[cache_key] = result
        
        return result
    
    def _extract_aggregated_asd_features(self, asd_files: List[Path]) -> List[float]:
        """Extract and aggregate features from multiple ASD files.
        
        Aggregates clip-level features into project-level statistics.
        """
        all_clip_features = []
        
        for asd_path in asd_files[:50]:  # Limit to avoid too many files
            analysis = self._asd_parser.parse(asd_path)
            if analysis:
                clip_feats = self._asd_parser.generate_feature_vector(analysis)
                all_clip_features.append(clip_feats)
        
        if not all_clip_features:
            # Return zeros if no ASD data
            return [0.0] * len(ASDParser.get_feature_names())
        
        # Aggregate: compute mean across all clips
        np = _get_numpy()
        feature_array = np.array(all_clip_features)
        return feature_array.mean(axis=0).tolist()
    
    def _extract_aggregated_audio_features(self, audio_paths: List[Path]) -> List[float]:
        """Extract and aggregate features from multiple audio files.
        
        Computes audio content features using librosa and aggregates them.
        """
        if not _check_librosa():
            return []
        
        all_audio_features = []
        
        for audio_path in audio_paths[:10]:  # Limit for performance
            if audio_path.exists():
                features = self._extract_audio_features(audio_path)
                if features:
                    all_audio_features.append(self._audio_features_to_vector(features))
        
        if not all_audio_features:
            # Return zeros if no audio analyzed
            return [0.0] * len(self._get_audio_feature_names())
        
        # Aggregate: compute mean across all audio files
        np = _get_numpy()
        feature_array = np.array(all_audio_features)
        return feature_array.mean(axis=0).tolist()
    
    def _extract_audio_features(self, audio_path: Path) -> Optional[AudioFeatures]:
        """Extract audio content features from a single audio file."""
        if not _check_librosa():
            return None
        
        try:
            # Get lazy-loaded modules
            librosa = _librosa
            np = _get_numpy()
            
            # Load audio file
            y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=60.0)
            
            if len(y) == 0:
                return None
            
            features = AudioFeatures()
            features.sample_rate = sr
            features.duration = len(y) / sr
            
            # Tempo and beat analysis
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            features.tempo = float(tempo) if isinstance(tempo, (int, float)) else float(tempo[0])
            
            # Beat strength (onset strength)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            features.beat_strength = float(np.mean(onset_env))
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            features.spectral_centroid = float(np.mean(spectral_centroids))
            
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            features.spectral_bandwidth = float(np.mean(spectral_bandwidth))
            
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            features.spectral_rolloff = float(np.mean(spectral_rolloff))
            
            spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
            features.spectral_contrast = float(np.mean(spectral_contrast))
            
            # Chroma features (for key detection)
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            features.chroma_mean = float(np.mean(chroma))
            
            # Estimate key from chroma
            chroma_sum = np.sum(chroma, axis=1)
            key_idx = int(np.argmax(chroma_sum))
            features.estimated_key = self.KEY_NAMES[key_idx]
            features.key_confidence = float(chroma_sum[key_idx] / (np.sum(chroma_sum) + 1e-6))
            
            # Energy features
            rms = librosa.feature.rms(y=y)[0]
            features.rms_mean = float(np.mean(rms))
            features.rms_std = float(np.std(rms))
            
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            features.zero_crossing_rate = float(np.mean(zcr))
            
            # MFCCs
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            features.mfcc_means = [float(np.mean(mfccs[i])) for i in range(mfccs.shape[0])]
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error extracting audio features from {audio_path}: {e}", exc_info=True)
            return None
    
    def _audio_features_to_vector(self, features: AudioFeatures) -> List[float]:
        """Convert AudioFeatures to a flat vector."""
        vector = [
            features.tempo,
            features.beat_strength,
            features.spectral_centroid,
            features.spectral_bandwidth,
            features.spectral_rolloff,
            features.spectral_contrast,
            features.chroma_mean,
            features.key_confidence,
            features.rms_mean,
            features.rms_std,
            features.zero_crossing_rate,
            features.duration
        ]
        
        # Add MFCCs (pad or truncate to 13)
        mfccs = features.mfcc_means[:13]
        while len(mfccs) < 13:
            mfccs.append(0.0)
        vector.extend(mfccs)
        
        return vector
    
    def _get_audio_feature_names(self) -> List[str]:
        """Get names for audio features."""
        names = [
            'audio_tempo',
            'audio_beat_strength',
            'audio_spectral_centroid',
            'audio_spectral_bandwidth',
            'audio_spectral_rolloff',
            'audio_spectral_contrast',
            'audio_chroma_mean',
            'audio_key_confidence',
            'audio_rms_mean',
            'audio_rms_std',
            'audio_zcr',
            'audio_duration'
        ]
        names.extend([f'audio_mfcc_{i}' for i in range(13)])
        return names
    
    def _combine_features(self, pf: ProjectFeatureVector) -> Any:
        """Combine all feature sources into a single normalized vector."""
        # Concatenate all features
        all_features = []
        
        if pf.als_features:
            all_features.extend(pf.als_features)
        else:
            all_features.extend([0.0] * len(ALSParser.get_feature_names()))
        
        if pf.asd_features:
            all_features.extend(pf.asd_features)
        else:
            all_features.extend([0.0] * len(ASDParser.get_feature_names()))
        
        if pf.audio_features:
            all_features.extend(pf.audio_features)
        else:
            all_features.extend([0.0] * len(self._get_audio_feature_names()))
        
        np = _get_numpy()
        
        # Convert to numpy array and sanitize values before float32 conversion
        arr = np.array(all_features, dtype=np.float64)
        
        # Check for problematic values before sanitization
        has_nan = np.isnan(arr).any()
        has_inf = np.isinf(arr).any()
        float32_max = np.finfo(np.float32).max
        float32_min = np.finfo(np.float32).min
        has_overflow = (np.abs(arr) > float32_max).any()
        
        if has_nan or has_inf or has_overflow:
            self.logger.warning(
                f"Sanitizing feature vector: NaN={has_nan}, Inf={has_inf}, "
                f"Overflow={has_overflow}. Replacing with safe values."
            )
        
        # Replace infinity and NaN with 0.0
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Clip values to float32 range to prevent overflow
        # float32 max value is approximately 3.4028235e+38
        arr = np.clip(arr, float32_min, float32_max)
        
        # Now safe to convert to float32
        return arr.astype(np.float32)
    
    def get_combined_feature_names(self) -> List[str]:
        """Get all feature names for the combined vector."""
        names = []
        names.extend([f'als_{n}' for n in ALSParser.get_feature_names()])
        names.extend([f'asd_{n}' for n in ASDParser.get_feature_names()])
        names.extend(self._get_audio_feature_names())
        return names
    
    def normalize_features(self, features: Any, fit: bool = False) -> Any:
        """Normalize a feature vector using StandardScaler.
        
        Args:
            features: Feature vector or matrix to normalize.
            fit: If True, fit the scaler on this data.
            
        Returns:
            Normalized features.
        """
        scaler = self._get_scaler()
        if not self._normalize or scaler is None:
            return features
        
        # Ensure 2D array
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        if fit or not self._scaler_fitted:
            scaler.fit(features)
            self._scaler_fitted = True
        
        return scaler.transform(features)
    
    def extract_batch_features(self, 
                                projects: List[Tuple[Path, Optional[int], Optional[List[Path]]]]
                                ) -> List[ProjectFeatureVector]:
        """Extract features from multiple projects.
        
        Args:
            projects: List of tuples (als_path, project_id, audio_paths).
            
        Returns:
            List of ProjectFeatureVector objects.
        """
        results = []
        
        for als_path, project_id, audio_paths in projects:
            pf = self.extract_project_features(als_path, project_id, audio_paths)
            if pf:
                results.append(pf)
        
        # Fit normalizer on all data
        if results and self._normalize:
            np = _get_numpy()
            all_vectors = np.vstack([pf.combined_vector for pf in results])
            self.normalize_features(all_vectors, fit=True)
            
            # Normalize each result
            for pf in results:
                pf.combined_vector = self.normalize_features(
                    pf.combined_vector.reshape(1, -1)
                ).flatten()
        
        return results
    
    def get_feature_importance(self, feature_name: str) -> Dict[str, Any]:
        """Get information about a specific feature.
        
        Args:
            feature_name: Name of the feature.
            
        Returns:
            Dictionary with feature metadata.
        """
        all_names = self.get_combined_feature_names()
        
        if feature_name not in all_names:
            return {}
        
        idx = all_names.index(feature_name)
        
        # Categorize the feature
        if feature_name.startswith('als_'):
            category = 'project_structure'
        elif feature_name.startswith('asd_'):
            category = 'clip_analysis'
        elif feature_name.startswith('audio_'):
            category = 'audio_content'
        else:
            category = 'unknown'
        
        return {
            'name': feature_name,
            'index': idx,
            'category': category,
            'description': self._get_feature_description(feature_name)
        }
    
    def _get_feature_description(self, name: str) -> str:
        """Get a human-readable description of a feature."""
        descriptions = {
            'als_tempo': 'Project tempo in BPM',
            'als_track_count': 'Total number of tracks',
            'als_plugin_count': 'Number of VST/AU plugins used',
            'als_device_count': 'Number of Ableton devices used',
            'asd_warp_marker_count': 'Number of warp markers in clips',
            'asd_detected_bpm': 'Auto-detected BPM from audio analysis',
            'audio_tempo': 'Tempo detected from audio content',
            'audio_spectral_centroid': 'Brightness of the sound',
            'audio_rms_mean': 'Average loudness/energy',
        }
        return descriptions.get(name, f'Feature: {name}')
    
    def clear_cache(self):
        """Clear all caches."""
        self._feature_cache.clear()
        self._als_parser.clear_cache()
        self._asd_parser.clear_cache()
