"""Recommendation Engine for Ableton Projects.

This service provides intelligent recommendations based on:
1. Content-based filtering (project features and metadata)
2. Plugin/device co-occurrence patterns
3. Workflow patterns and user behavior

Use cases:
- "Projects similar to this one"
- "You might also like" suggestions
- Plugin recommendations based on project context
- Auto-tagging suggestions

NOTE: Heavy imports (numpy) are deferred until first use
to avoid slowing down application startup.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Lazy import cache
_np = None


def _get_numpy():
    """Lazy-load numpy."""
    global _np
    if _np is None:
        import numpy

        _np = numpy
    return _np


# Import ML services (deferred - only imported when this module is used)
from .ml_feature_extractor import MLFeatureExtractor
from .similarity_analyzer import SimilarityAnalyzer


@dataclass
class Recommendation:
    """A single recommendation."""

    item_id: int  # Project ID, plugin name hash, etc.
    item_type: str  # 'project', 'plugin', 'device', 'tag'
    item_name: str
    score: float  # Recommendation score (0-1)
    reason: str  # Human-readable explanation
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationSet:
    """A set of recommendations for a given context."""

    context_type: str  # 'project', 'plugin', 'workflow'
    context_id: int | None = None
    context_name: str | None = None

    recommendations: list[Recommendation] = field(default_factory=list)
    generated_at: datetime | None = None

    def top_n(self, n: int = 5) -> list[Recommendation]:
        """Get top N recommendations by score."""
        sorted_recs = sorted(self.recommendations, key=lambda r: r.score, reverse=True)
        return sorted_recs[:n]

    def filter_by_type(self, item_type: str) -> list[Recommendation]:
        """Filter recommendations by item type."""
        return [r for r in self.recommendations if r.item_type == item_type]


class RecommendationEngine:
    """Engine for generating recommendations for Ableton projects.

    Supports multiple recommendation strategies:
    - Content-based: Similar projects based on features
    - Collaborative: Based on plugin/device co-occurrence
    - Contextual: Based on workflow patterns
    """

    def __init__(
        self,
        similarity_analyzer: SimilarityAnalyzer | None = None,
        feature_extractor: MLFeatureExtractor | None = None,
    ):
        """Initialize the recommendation engine.

        Args:
            similarity_analyzer: SimilarityAnalyzer instance.
            feature_extractor: MLFeatureExtractor instance.
        """
        self._similarity = similarity_analyzer or SimilarityAnalyzer()
        self._extractor = feature_extractor or MLFeatureExtractor()

        # Co-occurrence matrices (built from project data)
        self._plugin_cooccurrence: dict[str, Counter] = defaultdict(Counter)
        self._device_cooccurrence: dict[str, Counter] = defaultdict(Counter)
        self._plugin_tempo_affinity: dict[str, list[float]] = defaultdict(list)

        # Cache for recommendations
        self._cache: dict[str, RecommendationSet] = {}

        # All projects (for recommendation pool)
        self._project_pool: list[dict[str, Any]] = []

    def update_project_pool(self, projects: list[dict[str, Any]]) -> None:
        """Update the pool of projects used for recommendations.

        This also builds co-occurrence matrices for collaborative filtering.

        Args:
            projects: List of project dictionaries.
        """
        self._project_pool = projects
        self._build_cooccurrence_matrices(projects)

    def _build_cooccurrence_matrices(self, projects: list[dict[str, Any]]) -> None:
        """Build plugin and device co-occurrence matrices."""
        self._plugin_cooccurrence.clear()
        self._device_cooccurrence.clear()
        self._plugin_tempo_affinity.clear()

        for project in projects:
            plugins = project.get("plugins", [])
            devices = project.get("devices", [])
            tempo = project.get("tempo")

            # Plugin co-occurrence
            for i, plugin_a in enumerate(plugins):
                for plugin_b in plugins[i + 1 :]:
                    self._plugin_cooccurrence[plugin_a][plugin_b] += 1
                    self._plugin_cooccurrence[plugin_b][plugin_a] += 1

                # Plugin-tempo affinity
                if tempo:
                    self._plugin_tempo_affinity[plugin_a].append(tempo)

            # Device co-occurrence
            for i, device_a in enumerate(devices):
                for device_b in devices[i + 1 :]:
                    self._device_cooccurrence[device_a][device_b] += 1
                    self._device_cooccurrence[device_b][device_a] += 1

    def recommend_similar_projects(
        self,
        project: dict[str, Any],
        n_recommendations: int = 10,
        exclude_ids: set[int] | None = None,
    ) -> RecommendationSet:
        """Recommend projects similar to a given project.

        Args:
            project: Reference project dictionary.
            n_recommendations: Number of recommendations to generate.
            exclude_ids: Project IDs to exclude from recommendations.

        Returns:
            RecommendationSet with similar project recommendations.
        """
        exclude = exclude_ids or set()
        exclude.add(project.get("id", -1))

        # Filter pool
        candidates = [p for p in self._project_pool if p.get("id") not in exclude]

        # Find similar projects
        similar = self._similarity.find_similar_projects(
            reference_project=project,
            candidate_projects=candidates,
            top_n=n_recommendations,
            min_similarity=0.2,
        )

        # Convert to recommendations
        recommendations = []
        for sim in similar:
            reason = (
                self._similarity.get_similarity_explanation(sim.similarity_result)
                if sim.similarity_result
                else "Similar project structure"
            )

            recommendations.append(
                Recommendation(
                    item_id=sim.project_id,
                    item_type="project",
                    item_name=sim.project_name or f"Project {sim.project_id}",
                    score=sim.similarity_score,
                    reason=reason,
                    metadata={
                        "path": sim.project_path,
                        "similarity_breakdown": (
                            sim.similarity_result.to_dict() if sim.similarity_result else {}
                        ),
                    },
                )
            )

        return RecommendationSet(
            context_type="project",
            context_id=project.get("id"),
            context_name=project.get("name"),
            recommendations=recommendations,
            generated_at=datetime.utcnow(),
        )

    def recommend_plugins(
        self,
        current_plugins: list[str],
        project_context: dict[str, Any] | None = None,
        n_recommendations: int = 5,
    ) -> RecommendationSet:
        """Recommend plugins based on current project context.

        Uses co-occurrence patterns to suggest plugins that are often
        used together with the current plugins.

        Args:
            current_plugins: List of plugins currently in the project.
            project_context: Optional project dictionary for context.
            n_recommendations: Number of recommendations.

        Returns:
            RecommendationSet with plugin recommendations.
        """
        recommendations = []

        # Get co-occurring plugins
        cooccurrence_scores: Counter = Counter()

        for plugin in current_plugins:
            if plugin in self._plugin_cooccurrence:
                cooccurrence_scores.update(self._plugin_cooccurrence[plugin])

        # Remove plugins already in the project
        for plugin in current_plugins:
            if plugin in cooccurrence_scores:
                del cooccurrence_scores[plugin]

        # Score by co-occurrence frequency
        if cooccurrence_scores:
            max_score = max(cooccurrence_scores.values())

            for plugin, count in cooccurrence_scores.most_common(n_recommendations):
                score = count / max_score  # Normalize to 0-1

                # Build reason
                common_with = [
                    p for p in current_plugins if self._plugin_cooccurrence[p].get(plugin, 0) > 0
                ][:3]

                reason = f"Often used with: {', '.join(common_with)}"

                # Check tempo affinity
                if project_context and project_context.get("tempo"):
                    project_tempo = project_context["tempo"]
                    if plugin in self._plugin_tempo_affinity:
                        plugin_tempos = self._plugin_tempo_affinity[plugin]
                        np = _get_numpy()
                        avg_tempo = float(np.mean(plugin_tempos))
                        if abs(avg_tempo - project_tempo) < 15:
                            reason += f" (commonly used at ~{avg_tempo:.0f} BPM)"
                            score *= 1.1  # Boost for tempo match

                recommendations.append(
                    Recommendation(
                        item_id=hash(plugin) % (10**8),
                        item_type="plugin",
                        item_name=plugin,
                        score=min(score, 1.0),
                        reason=reason,
                    )
                )

        return RecommendationSet(
            context_type="plugin",
            context_name=f"{len(current_plugins)} plugins",
            recommendations=recommendations,
            generated_at=datetime.utcnow(),
        )

    def recommend_devices(
        self, current_devices: list[str], n_recommendations: int = 5
    ) -> RecommendationSet:
        """Recommend Ableton devices based on current project.

        Args:
            current_devices: List of devices currently in the project.
            n_recommendations: Number of recommendations.

        Returns:
            RecommendationSet with device recommendations.
        """
        recommendations = []

        # Get co-occurring devices
        cooccurrence_scores: Counter = Counter()

        for device in current_devices:
            if device in self._device_cooccurrence:
                cooccurrence_scores.update(self._device_cooccurrence[device])

        # Remove devices already in the project
        for device in current_devices:
            if device in cooccurrence_scores:
                del cooccurrence_scores[device]

        if cooccurrence_scores:
            max_score = max(cooccurrence_scores.values())

            for device, count in cooccurrence_scores.most_common(n_recommendations):
                score = count / max_score

                common_with = [
                    d for d in current_devices if self._device_cooccurrence[d].get(device, 0) > 0
                ][:3]

                reason = f"Often used with: {', '.join(common_with)}"

                recommendations.append(
                    Recommendation(
                        item_id=hash(device) % (10**8),
                        item_type="device",
                        item_name=device,
                        score=score,
                        reason=reason,
                    )
                )

        return RecommendationSet(
            context_type="device",
            context_name=f"{len(current_devices)} devices",
            recommendations=recommendations,
            generated_at=datetime.utcnow(),
        )

    def recommend_tags(
        self,
        project: dict[str, Any],
        available_tags: list[dict[str, Any]],
        n_recommendations: int = 5,
    ) -> RecommendationSet:
        """Recommend tags for a project based on its characteristics.

        Uses rule-based and pattern-based tag suggestions.

        Args:
            project: Project dictionary.
            available_tags: List of available tags in the system.
            n_recommendations: Number of recommendations.

        Returns:
            RecommendationSet with tag recommendations.
        """
        recommendations = []
        existing_tags = set(project.get("tags", []))

        # Build tag name to tag mapping
        tag_lookup = {t.get("name", ""): t for t in available_tags}

        # Rule-based tag suggestions
        tempo = project.get("tempo")
        if tempo:
            # Tempo-based tags
            tempo_tags = self._suggest_tempo_tags(tempo, tag_lookup)
            recommendations.extend(tempo_tags)

        # Plugin-based tags
        plugins = project.get("plugins", [])
        if plugins:
            plugin_tags = self._suggest_plugin_tags(plugins, tag_lookup)
            recommendations.extend(plugin_tags)

        # Structure-based tags
        track_count = project.get("track_count", 0)
        structure_tags = self._suggest_structure_tags(track_count, tag_lookup)
        recommendations.extend(structure_tags)

        # Filter out existing tags and duplicates
        seen = set()
        filtered = []
        for rec in recommendations:
            if rec.item_name not in existing_tags and rec.item_name not in seen:
                seen.add(rec.item_name)
                filtered.append(rec)

        # Sort by score and take top N
        filtered.sort(key=lambda r: r.score, reverse=True)

        return RecommendationSet(
            context_type="tag",
            context_id=project.get("id"),
            context_name=project.get("name"),
            recommendations=filtered[:n_recommendations],
            generated_at=datetime.utcnow(),
        )

    def _suggest_tempo_tags(
        self, tempo: float, tag_lookup: dict[str, dict]
    ) -> list[Recommendation]:
        """Suggest tags based on tempo."""
        recommendations = []

        # Genre/style suggestions based on tempo ranges
        tempo_suggestions = {
            (60, 80): [("ambient", 0.7), ("downtempo", 0.8), ("chill", 0.6)],
            (80, 100): [("hip-hop", 0.7), ("r&b", 0.6), ("lo-fi", 0.5)],
            (100, 120): [("house", 0.7), ("pop", 0.6), ("indie", 0.5)],
            (120, 130): [("house", 0.8), ("techno", 0.6), ("dance", 0.7)],
            (130, 145): [("techno", 0.8), ("trance", 0.6), ("progressive", 0.5)],
            (145, 160): [("drum-and-bass", 0.7), ("jungle", 0.6)],
            (160, 200): [("drum-and-bass", 0.8), ("hardcore", 0.6)],
        }

        for (low, high), suggestions in tempo_suggestions.items():
            if low <= tempo < high:
                for tag_name, score in suggestions:
                    if tag_name in tag_lookup:
                        recommendations.append(
                            Recommendation(
                                item_id=tag_lookup[tag_name].get("id", 0),
                                item_type="tag",
                                item_name=tag_name,
                                score=score,
                                reason=f"Common for {tempo:.0f} BPM tracks",
                            )
                        )
                break

        return recommendations

    def _suggest_plugin_tags(
        self, plugins: list[str], tag_lookup: dict[str, dict]
    ) -> list[Recommendation]:
        """Suggest tags based on plugins used."""
        recommendations = []

        # Plugin patterns to tag suggestions
        plugin_patterns = {
            "serum": [("synth", 0.8), ("electronic", 0.6)],
            "massive": [("synth", 0.8), ("electronic", 0.6)],
            "guitar": [("guitar", 0.9), ("rock", 0.5)],
            "bass": [("bass", 0.8)],
            "drum": [("drums", 0.7)],
            "vocal": [("vocals", 0.8)],
            "reverb": [("ambient", 0.4)],
        }

        plugins_lower = [p.lower() for p in plugins]

        for pattern, suggestions in plugin_patterns.items():
            if any(pattern in p for p in plugins_lower):
                for tag_name, score in suggestions:
                    if tag_name in tag_lookup:
                        recommendations.append(
                            Recommendation(
                                item_id=tag_lookup[tag_name].get("id", 0),
                                item_type="tag",
                                item_name=tag_name,
                                score=score,
                                reason=f"Detected '{pattern}' plugin",
                            )
                        )

        return recommendations

    def _suggest_structure_tags(
        self, track_count: int, tag_lookup: dict[str, dict]
    ) -> list[Recommendation]:
        """Suggest tags based on project structure."""
        recommendations = []

        if track_count <= 4:
            suggestions = [("minimal", 0.6), ("simple", 0.5), ("sketch", 0.5)]
        elif track_count <= 10:
            suggestions = [("standard", 0.4)]
        else:
            suggestions = [("complex", 0.6), ("full-production", 0.5)]

        for tag_name, score in suggestions:
            if tag_name in tag_lookup:
                recommendations.append(
                    Recommendation(
                        item_id=tag_lookup[tag_name].get("id", 0),
                        item_type="tag",
                        item_name=tag_name,
                        score=score,
                        reason=f"Based on {track_count} tracks",
                    )
                )

        return recommendations

    def get_workflow_insights(self, projects: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate workflow insights from project history.

        Analyzes patterns in project creation and usage.

        Args:
            projects: List of project dictionaries with timestamps.

        Returns:
            Dictionary with workflow insights.
        """
        insights = {
            "most_used_plugins": [],
            "most_used_devices": [],
            "avg_tempo": 0.0,
            "avg_tracks": 0.0,
            "plugin_trends": {},
            "productivity_pattern": None,
        }

        if not projects:
            return insights

        # Count plugin/device usage
        plugin_counter: Counter[str] = Counter()
        device_counter: Counter[str] = Counter()
        tempos = []
        track_counts = []

        for project in projects:
            plugin_counter.update(project.get("plugins", []))
            device_counter.update(project.get("devices", []))

            if project.get("tempo"):
                tempos.append(project["tempo"])
            if project.get("track_count"):
                track_counts.append(project["track_count"])

        insights["most_used_plugins"] = plugin_counter.most_common(10)
        insights["most_used_devices"] = device_counter.most_common(10)

        if tempos:
            np = _get_numpy()
            insights["avg_tempo"] = float(np.mean(tempos))
        if track_counts:
            np = _get_numpy()
            insights["avg_tracks"] = float(np.mean(track_counts))

        return insights

    def clear_cache(self) -> None:
        """Clear recommendation cache."""
        self._cache.clear()
