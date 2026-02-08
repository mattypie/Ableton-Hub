"""Project Similarity Analyzer Service.

This service provides similarity detection between Ableton projects using
multiple methods:
1. Cosine similarity on feature vectors
2. Jaccard similarity for categorical features (plugins, devices)
3. Weighted hybrid similarity combining multiple metrics

The similarity scores are cached in the database for performance.

NOTE: Heavy imports (numpy, sklearn) are deferred until first use
to avoid slowing down application startup.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

# Type checking imports (not loaded at runtime)
if TYPE_CHECKING:
    pass

# Lazy import cache
_np = None
_sklearn_cosine = None
_SKLEARN_AVAILABLE = None


def _get_numpy():
    """Lazy-load numpy."""
    global _np
    if _np is None:
        import numpy

        _np = numpy
    return _np


def _check_sklearn():
    """Check if sklearn is available and get cosine similarity (lazy)."""
    global _SKLEARN_AVAILABLE, _sklearn_cosine
    if _SKLEARN_AVAILABLE is None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            _sklearn_cosine = cosine_similarity
            _SKLEARN_AVAILABLE = True
        except ImportError:
            _SKLEARN_AVAILABLE = False
    return _SKLEARN_AVAILABLE


@dataclass
class SimilarityResult:
    """Result of a similarity comparison between two projects."""

    project_a_id: int
    project_b_id: int

    # Overall similarity score (0-1, higher = more similar)
    overall_similarity: float = 0.0

    # Component scores
    structural_similarity: float = 0.0  # Based on track counts, arrangement
    plugin_similarity: float = 0.0  # Jaccard similarity of plugins
    device_similarity: float = 0.0  # Jaccard similarity of devices
    tempo_similarity: float = 0.0  # Tempo proximity
    feature_similarity: float = 0.0  # Cosine similarity of feature vectors

    # Metadata
    computed_at: datetime | None = None

    # Shared elements
    shared_plugins: list[str] = field(default_factory=list)
    shared_devices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "project_a_id": self.project_a_id,
            "project_b_id": self.project_b_id,
            "overall_similarity": self.overall_similarity,
            "structural_similarity": self.structural_similarity,
            "plugin_similarity": self.plugin_similarity,
            "device_similarity": self.device_similarity,
            "tempo_similarity": self.tempo_similarity,
            "feature_similarity": self.feature_similarity,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "shared_plugins": self.shared_plugins,
            "shared_devices": self.shared_devices,
        }


@dataclass
class SimilarProject:
    """A project similar to a reference project."""

    project_id: int
    project_path: str | None = None
    project_name: str | None = None
    similarity_score: float = 0.0
    similarity_result: SimilarityResult | None = None


class SimilarityAnalyzer:
    """Service for analyzing similarity between Ableton projects.

    Uses multiple similarity metrics:
    - Feature vector cosine similarity
    - Plugin/device Jaccard similarity
    - Tempo proximity
    - Structural similarity (tracks, clips, arrangement)
    """

    # Default weights for combining similarity scores
    DEFAULT_WEIGHTS = {
        "feature": 0.35,
        "plugin": 0.20,
        "device": 0.15,
        "tempo": 0.15,
        "structural": 0.15,
    }

    # Tempo similarity threshold (BPM difference for full similarity)
    TEMPO_THRESHOLD = 5.0  # BPM
    TEMPO_MAX_DIFF = 50.0  # BPM beyond which similarity = 0

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ):
        """Initialize the similarity analyzer.

        Args:
            weights: Custom weights for similarity components.
        """
        self._weights = weights or self.DEFAULT_WEIGHTS

        # Normalize weights to sum to 1
        total = sum(self._weights.values())
        self._weights = {k: v / total for k, v in self._weights.items()}

        # Cache for similarity results
        self._similarity_cache: dict[tuple[int, int], SimilarityResult] = {}

    def compute_similarity(
        self, project_a: dict[str, Any], project_b: dict[str, Any], use_cache: bool = True
    ) -> SimilarityResult:
        """Compute similarity between two projects.

        Args:
            project_a: Dict with project data (id, path, plugins, devices, tempo, etc.)
            project_b: Dict with project data.
            use_cache: Whether to use cached results.

        Returns:
            SimilarityResult with detailed similarity scores.
        """
        id_a = project_a.get("id", 0)
        id_b = project_b.get("id", 0)

        # Check cache
        cache_key = (min(id_a, id_b), max(id_a, id_b))
        if use_cache and cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        result = SimilarityResult(
            project_a_id=id_a, project_b_id=id_b, computed_at=datetime.utcnow()
        )

        # Compute component similarities
        result.plugin_similarity = self._compute_jaccard_similarity(
            set(project_a.get("plugins", [])), set(project_b.get("plugins", []))
        )

        result.device_similarity = self._compute_jaccard_similarity(
            set(project_a.get("devices", [])), set(project_b.get("devices", []))
        )

        result.tempo_similarity = self._compute_tempo_similarity(
            project_a.get("tempo"), project_b.get("tempo")
        )

        result.structural_similarity = self._compute_structural_similarity(project_a, project_b)

        # Compute feature vector similarity
        result.feature_similarity = self._compute_feature_similarity(project_a, project_b)

        # Find shared elements
        result.shared_plugins = list(
            set(project_a.get("plugins", [])) & set(project_b.get("plugins", []))
        )
        result.shared_devices = list(
            set(project_a.get("devices", [])) & set(project_b.get("devices", []))
        )

        # Compute weighted overall similarity
        result.overall_similarity = (
            self._weights["feature"] * result.feature_similarity
            + self._weights["plugin"] * result.plugin_similarity
            + self._weights["device"] * result.device_similarity
            + self._weights["tempo"] * result.tempo_similarity
            + self._weights["structural"] * result.structural_similarity
        )

        # Cache result
        self._similarity_cache[cache_key] = result

        return result

    def _compute_jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Compute Jaccard similarity between two sets.

        Jaccard = |A ∩ B| / |A ∪ B|
        """
        if not set_a and not set_b:
            return 1.0  # Both empty = identical

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        return intersection / union if union > 0 else 0.0

    def _compute_tempo_similarity(self, tempo_a: float | None, tempo_b: float | None) -> float:
        """Compute tempo similarity based on BPM difference.

        Uses a linear decay from 1.0 (identical) to 0.0 (>50 BPM difference).
        """
        if tempo_a is None or tempo_b is None:
            return 0.5  # Unknown tempos - neutral similarity

        diff = abs(tempo_a - tempo_b)

        if diff <= self.TEMPO_THRESHOLD:
            return 1.0
        elif diff >= self.TEMPO_MAX_DIFF:
            return 0.0
        else:
            # Linear decay
            return 1.0 - (diff - self.TEMPO_THRESHOLD) / (
                self.TEMPO_MAX_DIFF - self.TEMPO_THRESHOLD
            )

    def _compute_structural_similarity(
        self, project_a: dict[str, Any], project_b: dict[str, Any]
    ) -> float:
        """Compute structural similarity based on track layout and arrangement.

        Considers:
        - Track count similarity
        - Audio/MIDI track ratio
        - Arrangement length
        """
        similarities = []

        # Track count similarity (normalized difference)
        # Use `or 0` to coerce None values from the database to 0
        tracks_a = project_a.get("track_count") or 0
        tracks_b = project_b.get("track_count") or 0
        if tracks_a > 0 or tracks_b > 0:
            max_tracks = max(tracks_a, tracks_b)
            track_sim = 1.0 - abs(tracks_a - tracks_b) / max_tracks
            similarities.append(track_sim)

        # Audio/MIDI ratio similarity
        audio_a = project_a.get("audio_tracks") or 0
        midi_a = project_a.get("midi_tracks") or 0
        audio_b = project_b.get("audio_tracks") or 0
        midi_b = project_b.get("midi_tracks") or 0

        if (audio_a + midi_a) > 0 and (audio_b + midi_b) > 0:
            ratio_a = audio_a / (audio_a + midi_a)
            ratio_b = audio_b / (audio_b + midi_b)
            ratio_sim = 1.0 - abs(ratio_a - ratio_b)
            similarities.append(ratio_sim)

        # Arrangement length similarity
        length_a = project_a.get("arrangement_length") or 0
        length_b = project_b.get("arrangement_length") or 0
        if length_a > 0 and length_b > 0:
            max_length = max(length_a, length_b)
            length_sim = 1.0 - abs(length_a - length_b) / max_length
            similarities.append(length_sim)

        if not similarities:
            return 0.5
        np = _get_numpy()
        return float(np.mean(similarities))

    def _compute_feature_similarity(
        self, project_a: dict[str, Any], project_b: dict[str, Any]
    ) -> float:
        """Compute cosine similarity between pre-computed feature vectors.

        Feature vectors should be computed and stored during project scanning.
        If a project doesn't have a stored vector, returns neutral similarity
        rather than re-parsing ALS files on the fly.
        """
        vector_a = project_a.get("feature_vector")
        vector_b = project_b.get("feature_vector")

        if vector_a is None or vector_b is None:
            return 0.5  # No stored vector - neutral similarity

        # Compute cosine similarity
        np = _get_numpy()
        return self._cosine_similarity(np.array(vector_a), np.array(vector_b))

    def _cosine_similarity(self, vec_a: Any, vec_b: Any) -> float:
        """Compute cosine similarity between two vectors."""
        np = _get_numpy()

        if _check_sklearn():
            # Use sklearn for efficiency
            similarity = _sklearn_cosine(vec_a.reshape(1, -1), vec_b.reshape(1, -1))[0][0]
            # Normalize to 0-1 (cosine can be -1 to 1)
            return (similarity + 1) / 2
        else:
            # Manual computation
            dot = np.dot(vec_a, vec_b)
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = dot / (norm_a * norm_b)
            return (similarity + 1) / 2

    def find_similar_projects(
        self,
        reference_project: dict[str, Any],
        candidate_projects: list[dict[str, Any]],
        top_n: int = 10,
        min_similarity: float = 0.3,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[SimilarProject]:
        """Find projects similar to a reference project.

        Args:
            reference_project: The project to find similar projects for.
            candidate_projects: List of projects to compare against.
            top_n: Maximum number of similar projects to return.
            min_similarity: Minimum similarity score threshold.
            cancel_check: Optional callable that returns True if the operation
                should be cancelled. Checked between each candidate comparison.

        Returns:
            List of SimilarProject objects, sorted by similarity (descending).
        """
        similar = []

        ref_id = reference_project.get("id", 0)

        for candidate in candidate_projects:
            # Check for cancellation between each candidate
            if cancel_check and cancel_check():
                return []

            cand_id = candidate.get("id", 0)

            # Skip self-comparison
            if cand_id == ref_id:
                continue

            # Compute similarity
            result = self.compute_similarity(reference_project, candidate)

            if result.overall_similarity >= min_similarity:
                similar.append(
                    SimilarProject(
                        project_id=cand_id,
                        project_path=candidate.get("als_path"),
                        project_name=candidate.get("name"),
                        similarity_score=result.overall_similarity,
                        similarity_result=result,
                    )
                )

        # Sort by similarity (descending) and take top N
        similar.sort(key=lambda x: x.similarity_score, reverse=True)
        return similar[:top_n]

    def compute_similarity_matrix(self, projects: list[dict[str, Any]]) -> Any:
        """Compute a full similarity matrix for a set of projects.

        Args:
            projects: List of project dictionaries.

        Returns:
            N x N numpy array where [i,j] is similarity between projects i and j.
        """
        np = _get_numpy()
        n = len(projects)
        matrix = np.zeros((n, n))

        for i in range(n):
            matrix[i, i] = 1.0  # Self-similarity

            for j in range(i + 1, n):
                result = self.compute_similarity(projects[i], projects[j])
                matrix[i, j] = result.overall_similarity
                matrix[j, i] = result.overall_similarity  # Symmetric

        return matrix

    def get_similarity_explanation(self, result: SimilarityResult) -> str:
        """Generate a human-readable explanation of similarity.

        Args:
            result: SimilarityResult to explain.

        Returns:
            Human-readable string explaining the similarity.
        """
        explanations = []

        score = result.overall_similarity

        if score >= 0.8:
            explanations.append("These projects are very similar.")
        elif score >= 0.6:
            explanations.append("These projects share many characteristics.")
        elif score >= 0.4:
            explanations.append("These projects have some similarities.")
        else:
            explanations.append("These projects are fairly different.")

        # Explain specific components
        if result.plugin_similarity >= 0.5:
            if result.shared_plugins:
                explanations.append(
                    f"They share {len(result.shared_plugins)} plugin(s): "
                    f"{', '.join(result.shared_plugins[:5])}"
                )

        if result.device_similarity >= 0.5:
            if result.shared_devices:
                explanations.append(
                    f"They use similar Ableton devices: " f"{', '.join(result.shared_devices[:5])}"
                )

        if result.tempo_similarity >= 0.8:
            explanations.append("They have very similar tempos.")

        if result.structural_similarity >= 0.7:
            explanations.append("They have similar project structures.")

        return " ".join(explanations)

    def update_weights(self, new_weights: dict[str, float]) -> None:
        """Update the similarity component weights.

        Args:
            new_weights: Dictionary with new weight values.
        """
        self._weights.update(new_weights)

        # Normalize
        total = sum(self._weights.values())
        self._weights = {k: v / total for k, v in self._weights.items()}

        # Clear cache since weights changed
        self._similarity_cache.clear()

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._similarity_cache.clear()
