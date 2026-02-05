"""Project health calculation service."""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import Project, ProjectStatus, get_session


class HealthCalculator:
    """Service for calculating project health metrics."""

    @staticmethod
    def calculate_health_score(project_id: int) -> dict[str, Any]:
        """Calculate health score and metrics for a project.

        Args:
            project_id: ID of the project.

        Returns:
            Dictionary with health score (0-100) and detailed metrics.
        """
        session = get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project:
                return {"score": 0, "issues": [], "warnings": []}

            score = 100
            issues = []
            warnings = []

            # Check if file exists
            if not Path(project.file_path).exists():
                score -= 50
                issues.append("File missing")

            # Check for exports
            if not project.exports:
                score -= 15
                warnings.append("No exports found")

            # Check modification date (stale projects)
            if project.modified_date:
                days_since_modification = (datetime.utcnow() - project.modified_date).days
                if days_since_modification > 365:
                    score -= 10
                    warnings.append(f"Not modified in {days_since_modification} days")

            # Check for metadata
            if not project.notes and not project.export_song_name:
                score -= 5
                warnings.append("No metadata")

            # Check for tags
            if not project.tags or len(project.tags) == 0:
                score -= 5
                warnings.append("No tags")

            # Check for collections
            if not project.project_collections:
                score -= 5
                warnings.append("Not in any collection")

            # Check file size (very large might indicate issues)
            if project.file_size > 100 * 1024 * 1024:  # > 100MB
                score -= 5
                warnings.append("Large file size")

            # Check status
            if project.status == ProjectStatus.MISSING:
                score -= 30
                issues.append("Marked as missing")
            elif project.status == ProjectStatus.OFFLINE:
                score -= 20
                issues.append("Location offline")

            # Ensure score doesn't go below 0
            score = max(0, score)

            # Determine health level
            if score >= 80:
                level = "excellent"
            elif score >= 60:
                level = "good"
            elif score >= 40:
                level = "fair"
            else:
                level = "poor"

            return {
                "score": score,
                "level": level,
                "issues": issues,
                "warnings": warnings,
                "has_exports": len(project.exports) > 0,
                "days_since_modification": (
                    days_since_modification if project.modified_date else None
                ),
                "file_exists": Path(project.file_path).exists() if project.file_path else False,
                "has_metadata": bool(project.notes or project.export_song_name),
                "has_tags": bool(project.tags and len(project.tags) > 0),
                "in_collections": len(project.project_collections) > 0,
            }
        finally:
            session.close()

    @staticmethod
    def get_health_summary() -> dict[str, Any]:
        """Get overall health summary for all projects.

        Returns:
            Dictionary with summary statistics.
        """
        session = get_session()
        try:
            all_projects = session.query(Project).all()

            total = len(all_projects)
            if total == 0:
                return {
                    "total": 0,
                    "excellent": 0,
                    "good": 0,
                    "fair": 0,
                    "poor": 0,
                    "missing_files": 0,
                    "no_exports": 0,
                    "stale_projects": 0,
                }

            excellent = 0
            good = 0
            fair = 0
            poor = 0
            missing_files = 0
            no_exports = 0
            stale_projects = 0

            for project in all_projects:
                health = HealthCalculator.calculate_health_score(project.id)

                if health["level"] == "excellent":
                    excellent += 1
                elif health["level"] == "good":
                    good += 1
                elif health["level"] == "fair":
                    fair += 1
                else:
                    poor += 1

                if not health["file_exists"]:
                    missing_files += 1

                if not health["has_exports"]:
                    no_exports += 1

                if health["days_since_modification"] and health["days_since_modification"] > 365:
                    stale_projects += 1

            return {
                "total": total,
                "excellent": excellent,
                "good": good,
                "fair": fair,
                "poor": poor,
                "missing_files": missing_files,
                "no_exports": no_exports,
                "stale_projects": stale_projects,
                "excellent_percent": (excellent / total * 100) if total > 0 else 0,
                "good_percent": (good / total * 100) if total > 0 else 0,
                "fair_percent": (fair / total * 100) if total > 0 else 0,
                "poor_percent": (poor / total * 100) if total > 0 else 0,
            }
        finally:
            session.close()

    @staticmethod
    def get_projects_by_health(level: str | None = None) -> list[int]:
        """Get project IDs filtered by health level.

        Args:
            level: Health level to filter by ('excellent', 'good', 'fair', 'poor').
                  If None, returns all projects sorted by health.

        Returns:
            List of project IDs.
        """
        session = get_session()
        try:
            projects = session.query(Project).all()

            project_health = []
            for project in projects:
                health = HealthCalculator.calculate_health_score(project.id)
                if level is None or health["level"] == level:
                    project_health.append((project.id, health["score"]))

            # Sort by score (highest first)
            project_health.sort(key=lambda x: x[1], reverse=True)
            return [pid for pid, _ in project_health]
        finally:
            session.close()
