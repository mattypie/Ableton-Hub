"""Repository for project data access."""

from datetime import datetime, timedelta

from sqlalchemy import String, nullsfirst, nullslast
from sqlalchemy.orm import joinedload

from ...utils.logging import get_logger
from ..db import get_session
from ..models import Location, Project, ProjectCollection, ProjectTag


class ProjectRepository:
    """Repository for project queries and operations."""

    def __init__(self):
        """Initialize the repository."""
        self.logger = get_logger(__name__)

    def get_all(
        self,
        location_id: int | None = None,
        collection_id: int | None = None,
        tag_id: int | None = None,
        search_query: str | None = None,
        date_filter: str | None = None,
        tempo_min: int | None = None,
        tempo_max: int | None = None,
        sort_by: str = "modified_desc",
        arrangement_length: float | None = None,
    ) -> list[Project]:
        """Get projects with optional filtering and sorting.

        Args:
            location_id: Filter by location ID.
            collection_id: Filter by collection ID.
            tag_id: Filter by tag ID.
            search_query: Search query string.
            date_filter: Date filter type.
            tempo_min: Minimum tempo filter.
            tempo_max: Maximum tempo filter.
            sort_by: Sort field and direction.
            arrangement_length: Optional arrangement length filter.

        Returns:
            List of Project objects.
        """
        session = get_session()
        try:
            # Eagerly load relationships
            query = session.query(Project).options(
                joinedload(Project.location),
                joinedload(Project.exports),
                joinedload(Project.project_tags),
            )

            # Apply filters
            if location_id:
                query = query.filter(Project.location_id == location_id)

            if collection_id:
                query = query.join(ProjectCollection).filter(
                    ProjectCollection.collection_id == collection_id
                )

            if tag_id:
                # Use junction table for tag filtering
                query = query.join(ProjectTag).filter(ProjectTag.tag_id == tag_id).distinct()

            # Apply date filter
            if date_filter and date_filter != "clear":
                now = datetime.utcnow()
                if date_filter == "today":
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    query = query.filter(Project.modified_date >= start_date)
                elif date_filter in ("week", "7days"):
                    start_date = now - timedelta(days=7)
                    query = query.filter(Project.modified_date >= start_date)
                elif date_filter in ("month", "30days"):
                    start_date = now - timedelta(days=30)
                    query = query.filter(Project.modified_date >= start_date)

                query = query.filter(Project.modified_date.isnot(None))

            # Apply tempo filter
            if tempo_min and tempo_min > 0:
                query = query.filter(Project.tempo >= tempo_min)
            if tempo_max and tempo_max > 0 and tempo_max < 999:
                query = query.filter(Project.tempo <= tempo_max)

            if (tempo_min and tempo_min > 0) or (tempo_max and tempo_max > 0 and tempo_max < 999):
                query = query.filter(Project.tempo.isnot(None))

            # Apply arrangement length filter
            if arrangement_length is not None:
                query = query.filter(Project.arrangement_length >= arrangement_length)

            # Apply search
            if search_query:
                from ..db import search_projects_fts

                project_ids = search_projects_fts(search_query)
                if project_ids:
                    query = query.filter(Project.id.in_(project_ids))
                else:
                    search_pattern = f"%{search_query}%"
                    query = query.filter(
                        Project.name.ilike(search_pattern)
                        | Project.export_song_name.ilike(search_pattern)
                        | Project.notes.ilike(search_pattern)
                        | Project.plugins.cast(String).ilike(search_pattern)
                        | Project.devices.cast(String).ilike(search_pattern)
                    )

            # Apply sorting
            sort_parts = sort_by.split("_")
            if len(sort_parts) == 2:
                field, direction = sort_parts
                if field == "modified":
                    order_by = (
                        Project.modified_date.desc()
                        if direction == "desc"
                        else Project.modified_date.asc()
                    )
                elif field == "name":
                    order_by = Project.name.asc() if direction == "asc" else Project.name.desc()
                elif field == "tempo":
                    order_by = (
                        nullslast(Project.tempo.desc())
                        if direction == "desc"
                        else nullslast(Project.tempo.asc())
                    )
                elif field == "length":
                    order_by = (
                        nullslast(Project.arrangement_length.desc())
                        if direction == "desc"
                        else nullslast(Project.arrangement_length.asc())
                    )
                elif field == "location":
                    order_by = (
                        Location.name.asc()
                        if direction == "asc"
                        else nullsfirst(Location.name.desc())
                    )
                    query = query.outerjoin(Location)
                else:
                    order_by = Project.modified_date.desc()

                query = query.order_by(order_by)
            else:
                query = query.order_by(Project.modified_date.desc())

            return query.all()
        finally:
            session.close()

    def get_by_id(self, project_id: int) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: Project ID.

        Returns:
            Project object or None.
        """
        session = get_session()
        try:
            return (
                session.query(Project)
                .options(
                    joinedload(Project.location),
                    joinedload(Project.exports),
                    joinedload(Project.project_tags),
                )
                .filter(Project.id == project_id)
                .first()
            )
        finally:
            session.close()

    def count(self, location_id: int | None = None) -> int:
        """Get project count.

        Args:
            location_id: Optional location filter.

        Returns:
            Total count.
        """
        session = get_session()
        try:
            query = session.query(Project)
            if location_id:
                query = query.filter(Project.location_id == location_id)
            return query.count()
        finally:
            session.close()
