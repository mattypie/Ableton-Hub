"""Duplicate detection service for finding duplicate projects."""

from collections import defaultdict
from difflib import SequenceMatcher

from ..database import Project, get_session


class DuplicateDetector:
    """Service for detecting duplicate projects."""

    @staticmethod
    def find_exact_duplicates() -> list[tuple[int, list[int]]]:
        """Find projects with identical file hashes (exact duplicates).

        Returns:
            List of tuples (hash, [project_ids]) for each duplicate group.
        """
        session = get_session()
        try:
            # Get all projects with hashes
            projects = session.query(Project).filter(Project.file_hash.isnot(None)).all()

            # Group by hash
            hash_groups = defaultdict(list)
            for project in projects:
                if project.file_hash:
                    hash_groups[project.file_hash].append(project.id)

            # Return groups with more than one project
            duplicates = []
            for file_hash, project_ids in hash_groups.items():
                if len(project_ids) > 1:
                    duplicates.append((file_hash, project_ids))

            return duplicates
        finally:
            session.close()

    @staticmethod
    def find_similar_names(threshold: float = 0.85) -> list[tuple[int, int, float]]:
        """Find projects with similar names (potential duplicates).

        Args:
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            List of tuples (project_id1, project_id2, similarity_score).
        """
        session = get_session()
        try:
            projects = session.query(Project).all()

            similar = []
            project_list = list(projects)

            for i, project1 in enumerate(project_list):
                for project2 in project_list[i + 1 :]:
                    # Skip if same project or different locations (might be intentional)
                    if project1.id == project2.id:
                        continue

                    # Calculate similarity
                    similarity = SequenceMatcher(
                        None, project1.name.lower(), project2.name.lower()
                    ).ratio()

                    if similarity >= threshold:
                        similar.append((project1.id, project2.id, similarity))

            # Sort by similarity (highest first)
            similar.sort(key=lambda x: x[2], reverse=True)
            return similar
        finally:
            session.close()

    @staticmethod
    def find_location_duplicates() -> list[tuple[str, list[int]]]:
        """Find projects with same name in different locations (potential duplicates).

        Returns:
            List of tuples (name, [project_ids]) for each duplicate name group.
        """
        session = get_session()
        try:
            projects = session.query(Project).all()

            # Group by normalized name
            name_groups = defaultdict(list)
            for project in projects:
                # Normalize name (lowercase, strip whitespace)
                normalized = project.name.lower().strip()
                name_groups[normalized].append(project.id)

            # Return groups with more than one project in different locations
            duplicates = []
            for name, project_ids in name_groups.items():
                if len(project_ids) > 1:
                    # Check if they're in different locations
                    locations = set()
                    for pid in project_ids:
                        project = session.query(Project).get(pid)
                        if project and project.location_id:
                            locations.add(project.location_id)

                    if len(locations) > 1:
                        duplicates.append((name, project_ids))

            return duplicates
        finally:
            session.close()

    @staticmethod
    def get_all_duplicates() -> dict[str, list]:
        """Get all types of duplicates.

        Returns:
            Dictionary with 'exact', 'similar_names', and 'location_duplicates' keys.
        """
        return {
            "exact": DuplicateDetector.find_exact_duplicates(),
            "similar_names": DuplicateDetector.find_similar_names(),
            "location_duplicates": DuplicateDetector.find_location_duplicates(),
        }
