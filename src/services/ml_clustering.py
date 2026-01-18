"""ML Clustering Service for Ableton Projects.

This service provides clustering capabilities to group similar projects:
1. K-Means clustering for predefined number of groups
2. DBSCAN for automatic cluster discovery
3. Hierarchical clustering for dendrograms
4. Cluster analysis and labeling

The clustering results can be used for:
- Auto-organizing large project libraries
- Discovering project patterns
- Smart collection suggestions
- Workflow analysis

NOTE: Heavy imports (numpy, sklearn) are deferred until first use
to avoid slowing down application startup.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime

# Type checking imports (not loaded at runtime)
if TYPE_CHECKING:
    import numpy as np

# Lazy import cache
_np = None
_sklearn_modules = None
_SKLEARN_AVAILABLE = None


def _get_numpy():
    """Lazy-load numpy."""
    global _np
    if _np is None:
        import numpy
        _np = numpy
    return _np


def _check_sklearn():
    """Check if sklearn is available and load modules (lazy)."""
    global _SKLEARN_AVAILABLE, _sklearn_modules
    if _SKLEARN_AVAILABLE is None:
        try:
            from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import silhouette_score, calinski_harabasz_score
            from sklearn.decomposition import PCA
            _sklearn_modules = {
                'KMeans': KMeans,
                'DBSCAN': DBSCAN,
                'AgglomerativeClustering': AgglomerativeClustering,
                'StandardScaler': StandardScaler,
                'silhouette_score': silhouette_score,
                'calinski_harabasz_score': calinski_harabasz_score,
                'PCA': PCA
            }
            _SKLEARN_AVAILABLE = True
        except ImportError:
            _SKLEARN_AVAILABLE = False
    return _SKLEARN_AVAILABLE


# Import feature extraction (deferred - only imported when this module is used)
from .ml_feature_extractor import MLFeatureExtractor, ProjectFeatureVector


@dataclass
class ClusterInfo:
    """Information about a single cluster."""
    cluster_id: int
    project_ids: List[int] = field(default_factory=list)
    project_count: int = 0
    
    # Centroid characteristics
    avg_tempo: float = 0.0
    avg_track_count: float = 0.0
    avg_plugin_count: float = 0.0
    
    # Common elements
    common_plugins: List[str] = field(default_factory=list)
    common_devices: List[str] = field(default_factory=list)
    
    # Suggested label based on characteristics
    suggested_label: str = ""
    
    # Quality metrics
    cohesion: float = 0.0  # How tight the cluster is
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cluster_id': self.cluster_id,
            'project_ids': self.project_ids,
            'project_count': self.project_count,
            'avg_tempo': self.avg_tempo,
            'avg_track_count': self.avg_track_count,
            'avg_plugin_count': self.avg_plugin_count,
            'common_plugins': self.common_plugins,
            'common_devices': self.common_devices,
            'suggested_label': self.suggested_label,
            'cohesion': self.cohesion
        }


@dataclass
class ClusteringResult:
    """Results from a clustering operation."""
    method: str  # 'kmeans', 'dbscan', 'hierarchical'
    clusters: List[ClusterInfo] = field(default_factory=list)
    n_clusters: int = 0
    
    # Quality metrics
    silhouette_score: float = 0.0
    calinski_harabasz_score: float = 0.0
    
    # Noise points (for DBSCAN)
    noise_project_ids: List[int] = field(default_factory=list)
    
    # Metadata
    computed_at: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def get_cluster_for_project(self, project_id: int) -> Optional[ClusterInfo]:
        """Find which cluster a project belongs to."""
        for cluster in self.clusters:
            if project_id in cluster.project_ids:
                return cluster
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'method': self.method,
            'clusters': [c.to_dict() for c in self.clusters],
            'n_clusters': self.n_clusters,
            'silhouette_score': self.silhouette_score,
            'calinski_harabasz_score': self.calinski_harabasz_score,
            'noise_project_ids': self.noise_project_ids,
            'computed_at': self.computed_at.isoformat() if self.computed_at else None,
            'parameters': self.parameters
        }


class MLClusteringService:
    """Service for clustering Ableton projects using ML algorithms.
    
    Supports multiple clustering methods:
    - K-Means: Good when you know the number of clusters
    - DBSCAN: Automatic cluster discovery, handles noise
    - Hierarchical: Creates a tree of clusters
    """
    
    # Tempo range labels
    TEMPO_LABELS = {
        (0, 80): 'slow',
        (80, 110): 'mid-tempo',
        (110, 130): 'standard',
        (130, 150): 'high-energy',
        (150, 999): 'fast'
    }
    
    def __init__(self, feature_extractor: Optional[MLFeatureExtractor] = None):
        """Initialize the clustering service.
        
        Args:
            feature_extractor: MLFeatureExtractor instance to use.
        """
        if not _check_sklearn():
            raise ImportError(
                "scikit-learn is required for clustering. "
                "Install with: pip install scikit-learn"
            )
        
        self._extractor = feature_extractor or MLFeatureExtractor()
        self._scaler = _sklearn_modules['StandardScaler']()
        self._last_result: Optional[ClusteringResult] = None
    
    def cluster_kmeans(self,
                       projects: List[Dict[str, Any]],
                       n_clusters: int = 5,
                       max_iter: int = 300,
                       n_init: int = 10
                       ) -> ClusteringResult:
        """Cluster projects using K-Means algorithm.
        
        Args:
            projects: List of project dictionaries with features.
            n_clusters: Number of clusters to create.
            max_iter: Maximum iterations for K-Means.
            n_init: Number of initializations.
            
        Returns:
            ClusteringResult with cluster assignments.
        """
        if len(projects) < n_clusters:
            n_clusters = max(1, len(projects) // 2)
        
        # Extract feature vectors
        X, project_ids = self._prepare_features(projects)
        
        if X.shape[0] < 2:
            return self._empty_result('kmeans')
        
        # Scale features
        X_scaled = self._scaler.fit_transform(X)
        
        # Run K-Means
        KMeans = _sklearn_modules['KMeans']
        kmeans = KMeans(
            n_clusters=n_clusters,
            max_iter=max_iter,
            n_init=n_init,
            random_state=42
        )
        labels = kmeans.fit_predict(X_scaled)
        
        # Build result
        result = self._build_clustering_result(
            method='kmeans',
            labels=labels,
            project_ids=project_ids,
            projects=projects,
            X_scaled=X_scaled,
            parameters={
                'n_clusters': n_clusters,
                'max_iter': max_iter,
                'n_init': n_init
            }
        )
        
        self._last_result = result
        return result
    
    def cluster_dbscan(self,
                       projects: List[Dict[str, Any]],
                       eps: float = 0.5,
                       min_samples: int = 3
                       ) -> ClusteringResult:
        """Cluster projects using DBSCAN algorithm.
        
        DBSCAN automatically discovers clusters and identifies noise points.
        
        Args:
            projects: List of project dictionaries with features.
            eps: Maximum distance between samples in a cluster.
            min_samples: Minimum samples in a neighborhood for a core point.
            
        Returns:
            ClusteringResult with cluster assignments.
        """
        # Extract feature vectors
        X, project_ids = self._prepare_features(projects)
        
        if X.shape[0] < 2:
            return self._empty_result('dbscan')
        
        # Scale features
        X_scaled = self._scaler.fit_transform(X)
        
        # Run DBSCAN
        DBSCAN = _sklearn_modules['DBSCAN']
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(X_scaled)
        
        # Build result
        result = self._build_clustering_result(
            method='dbscan',
            labels=labels,
            project_ids=project_ids,
            projects=projects,
            X_scaled=X_scaled,
            parameters={
                'eps': eps,
                'min_samples': min_samples
            }
        )
        
        # Mark noise points (label = -1 in DBSCAN)
        result.noise_project_ids = [
            project_ids[i] for i, label in enumerate(labels) if label == -1
        ]
        
        self._last_result = result
        return result
    
    def cluster_hierarchical(self,
                             projects: List[Dict[str, Any]],
                             n_clusters: int = 5,
                             linkage: str = 'ward'
                             ) -> ClusteringResult:
        """Cluster projects using hierarchical (agglomerative) clustering.
        
        Args:
            projects: List of project dictionaries with features.
            n_clusters: Number of clusters to create.
            linkage: Linkage method ('ward', 'complete', 'average', 'single').
            
        Returns:
            ClusteringResult with cluster assignments.
        """
        if len(projects) < n_clusters:
            n_clusters = max(1, len(projects) // 2)
        
        # Extract feature vectors
        X, project_ids = self._prepare_features(projects)
        
        if X.shape[0] < 2:
            return self._empty_result('hierarchical')
        
        # Scale features
        X_scaled = self._scaler.fit_transform(X)
        
        # Run Agglomerative Clustering
        AgglomerativeClustering = _sklearn_modules['AgglomerativeClustering']
        agg = AgglomerativeClustering(
            n_clusters=n_clusters,
            linkage=linkage
        )
        labels = agg.fit_predict(X_scaled)
        
        # Build result
        result = self._build_clustering_result(
            method='hierarchical',
            labels=labels,
            project_ids=project_ids,
            projects=projects,
            X_scaled=X_scaled,
            parameters={
                'n_clusters': n_clusters,
                'linkage': linkage
            }
        )
        
        self._last_result = result
        return result
    
    def find_optimal_k(self,
                       projects: List[Dict[str, Any]],
                       k_range: Tuple[int, int] = (2, 10)
                       ) -> Dict[str, Any]:
        """Find the optimal number of clusters using silhouette analysis.
        
        Args:
            projects: List of project dictionaries.
            k_range: Range of k values to try (min, max).
            
        Returns:
            Dictionary with optimal k and scores for each k.
        """
        X, _ = self._prepare_features(projects)
        
        if X.shape[0] < k_range[0]:
            return {'optimal_k': 1, 'scores': {}}
        
        X_scaled = self._scaler.fit_transform(X)
        
        scores = {}
        max_k = min(k_range[1], X.shape[0] - 1)
        
        KMeans = _sklearn_modules['KMeans']
        silhouette_score = _sklearn_modules['silhouette_score']
        
        for k in range(k_range[0], max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            
            if len(set(labels)) > 1:
                score = silhouette_score(X_scaled, labels)
                scores[k] = score
        
        if not scores:
            return {'optimal_k': 2, 'scores': {}}
        
        optimal_k = max(scores, key=scores.get)
        
        return {
            'optimal_k': optimal_k,
            'scores': scores,
            'best_score': scores[optimal_k]
        }
    
    def _prepare_features(self, 
                          projects: List[Dict[str, Any]]
                          ) -> Tuple[Any, List[int]]:
        """Prepare feature matrix from projects.
        
        Args:
            projects: List of project dictionaries.
            
        Returns:
            Tuple of (feature matrix, project IDs).
        """
        np = _get_numpy()
        feature_vectors = []
        project_ids = []
        
        for project in projects:
            vector = project.get('feature_vector')
            
            if vector is None and project.get('als_path'):
                # Extract features
                pf = self._extractor.extract_project_features(
                    Path(project['als_path']),
                    project.get('id')
                )
                if pf:
                    vector = pf.combined_vector
            
            if vector is not None:
                feature_vectors.append(vector)
                project_ids.append(project.get('id', len(project_ids)))
        
        if not feature_vectors:
            return np.array([]), []
        
        return np.array(feature_vectors), project_ids
    
    def _build_clustering_result(self,
                                  method: str,
                                  labels: Any,
                                  project_ids: List[int],
                                  projects: List[Dict[str, Any]],
                                  X_scaled: Any,
                                  parameters: Dict[str, Any]
                                  ) -> ClusteringResult:
        """Build a ClusteringResult from clustering output."""
        result = ClusteringResult(
            method=method,
            computed_at=datetime.utcnow(),
            parameters=parameters
        )
        
        # Get unique cluster labels (excluding noise label -1 for DBSCAN)
        unique_labels = set(labels)
        unique_labels.discard(-1)
        result.n_clusters = len(unique_labels)
        
        # Create project lookup by ID
        project_lookup = {p.get('id', i): p for i, p in enumerate(projects)}
        
        # Build cluster info for each cluster
        for cluster_id in unique_labels:
            cluster_mask = labels == cluster_id
            cluster_project_ids = [
                project_ids[i] for i in range(len(labels)) if cluster_mask[i]
            ]
            
            # Gather project data for this cluster
            cluster_projects = [
                project_lookup.get(pid) for pid in cluster_project_ids
                if project_lookup.get(pid) is not None
            ]
            
            cluster_info = self._analyze_cluster(
                cluster_id=int(cluster_id),
                project_ids=cluster_project_ids,
                projects=cluster_projects,
                feature_vectors=X_scaled[cluster_mask]
            )
            
            result.clusters.append(cluster_info)
        
        # Compute quality metrics
        if len(unique_labels) > 1 and len(project_ids) > len(unique_labels):
            try:
                silhouette_score_fn = _sklearn_modules['silhouette_score']
                calinski_harabasz_score_fn = _sklearn_modules['calinski_harabasz_score']
                result.silhouette_score = float(
                    silhouette_score_fn(X_scaled, labels)
                )
                result.calinski_harabasz_score = float(
                    calinski_harabasz_score_fn(X_scaled, labels)
                )
            except Exception:
                pass
        
        return result
    
    def _analyze_cluster(self,
                         cluster_id: int,
                         project_ids: List[int],
                         projects: List[Dict[str, Any]],
                         feature_vectors: Any
                         ) -> ClusterInfo:
        """Analyze a cluster and generate summary info."""
        info = ClusterInfo(
            cluster_id=cluster_id,
            project_ids=project_ids,
            project_count=len(project_ids)
        )
        
        if not projects:
            return info
        
        # Compute averages
        tempos = [p.get('tempo', 0) for p in projects if p.get('tempo')]
        track_counts = [p.get('track_count', 0) for p in projects]
        plugin_counts = [len(p.get('plugins', [])) for p in projects]
        
        np = _get_numpy()
        if tempos:
            info.avg_tempo = float(np.mean(tempos))
        if track_counts:
            info.avg_track_count = float(np.mean(track_counts))
        if plugin_counts:
            info.avg_plugin_count = float(np.mean(plugin_counts))
        
        # Find common plugins and devices
        all_plugins = []
        all_devices = []
        for p in projects:
            all_plugins.extend(p.get('plugins', []))
            all_devices.extend(p.get('devices', []))
        
        if all_plugins:
            plugin_counts = Counter(all_plugins)
            # Get plugins that appear in at least half the projects
            threshold = len(projects) / 2
            info.common_plugins = [
                plugin for plugin, count in plugin_counts.most_common(5)
                if count >= threshold
            ]
        
        if all_devices:
            device_counts = Counter(all_devices)
            threshold = len(projects) / 2
            info.common_devices = [
                device for device, count in device_counts.most_common(5)
                if count >= threshold
            ]
        
        # Compute cohesion (average distance from centroid)
        if len(feature_vectors) > 1:
            centroid = np.mean(feature_vectors, axis=0)
            distances = np.linalg.norm(feature_vectors - centroid, axis=1)
            info.cohesion = 1.0 / (1.0 + float(np.mean(distances)))  # Normalize to 0-1
        else:
            info.cohesion = 1.0
        
        # Generate suggested label
        info.suggested_label = self._generate_cluster_label(info)
        
        return info
    
    def _generate_cluster_label(self, cluster: ClusterInfo) -> str:
        """Generate a descriptive label for a cluster."""
        parts = []
        
        # Add tempo descriptor
        if cluster.avg_tempo > 0:
            for (low, high), label in self.TEMPO_LABELS.items():
                if low <= cluster.avg_tempo < high:
                    parts.append(label)
                    break
        
        # Add track count descriptor
        if cluster.avg_track_count > 20:
            parts.append("complex")
        elif cluster.avg_track_count > 10:
            parts.append("standard")
        else:
            parts.append("minimal")
        
        # Add plugin descriptor
        if cluster.common_plugins:
            parts.append(f"({cluster.common_plugins[0]})")
        
        return " ".join(parts) if parts else f"Cluster {cluster.cluster_id}"
    
    def _empty_result(self, method: str) -> ClusteringResult:
        """Create an empty clustering result."""
        return ClusteringResult(
            method=method,
            computed_at=datetime.utcnow(),
            parameters={}
        )
    
    def reduce_dimensions(self,
                          projects: List[Dict[str, Any]],
                          n_components: int = 2
                          ) -> Any:
        """Reduce feature dimensions for visualization using PCA.
        
        Args:
            projects: List of project dictionaries.
            n_components: Number of dimensions to reduce to.
            
        Returns:
            Array of shape (n_projects, n_components).
        """
        np = _get_numpy()
        X, _ = self._prepare_features(projects)
        
        if X.shape[0] < 2:
            return np.array([])
        
        X_scaled = self._scaler.fit_transform(X)
        
        PCA = _sklearn_modules['PCA']
        pca = PCA(n_components=min(n_components, X_scaled.shape[1]))
        return pca.fit_transform(X_scaled)
    
    def suggest_smart_collections(self,
                                   result: ClusteringResult,
                                   min_projects: int = 3
                                   ) -> List[Dict[str, Any]]:
        """Suggest smart collection configurations based on clustering.
        
        Args:
            result: ClusteringResult to generate suggestions from.
            min_projects: Minimum projects for a suggestion.
            
        Returns:
            List of smart collection configuration suggestions.
        """
        suggestions = []
        
        for cluster in result.clusters:
            if cluster.project_count < min_projects:
                continue
            
            suggestion = {
                'name': cluster.suggested_label.title(),
                'description': f'Auto-generated from clustering ({cluster.project_count} projects)',
                'rules': {}
            }
            
            # Add tempo rule if meaningful
            if cluster.avg_tempo > 0:
                suggestion['rules']['tempo_min'] = max(0, cluster.avg_tempo - 15)
                suggestion['rules']['tempo_max'] = cluster.avg_tempo + 15
            
            # Could add plugin-based rules if we had tag mapping
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def get_last_result(self) -> Optional[ClusteringResult]:
        """Get the result of the last clustering operation."""
        return self._last_result
