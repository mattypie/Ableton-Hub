"""Smart collection service for dynamic rule-based collections."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

from ..database import get_session, Collection, Project, ProjectCollection, Tag, Location


class SmartCollectionService:
    """Service for managing smart collections."""
    
    @staticmethod
    def evaluate_smart_collection(collection_id: int) -> List[int]:
        """Evaluate a smart collection and return list of matching project IDs.
        
        Args:
            collection_id: ID of the smart collection.
            
        Returns:
            List of project IDs that match the collection rules.
        """
        session = get_session()
        try:
            collection = session.query(Collection).get(collection_id)
            if not collection or not collection.is_smart or not collection.smart_rules:
                return []
            
            rules = collection.smart_rules
            query = session.query(Project.id)
            
            # Apply filters based on rules
            conditions = []
            
            # Tag filters
            if 'tags' in rules:
                tag_ids = rules['tags']
                if tag_ids:
                    # Projects that have any of these tags
                    if rules.get('tags_mode', 'any') == 'all':
                        # All tags must be present
                        for tag_id in tag_ids:
                            query = query.filter(Project.tags.contains([tag_id]))
                    else:
                        # Any tag present
                        tag_conditions = [Project.tags.contains([tag_id]) for tag_id in tag_ids]
                        conditions.append(or_(*tag_conditions))
            
            # Location filters
            if 'locations' in rules:
                location_ids = rules['locations']
                if location_ids:
                    conditions.append(Project.location_id.in_(location_ids))
            
            # Date filters
            if 'date_range' in rules:
                date_range = rules['date_range']
                if 'start_date' in date_range:
                    start = datetime.fromisoformat(date_range['start_date'])
                    conditions.append(Project.modified_date >= start)
                if 'end_date' in date_range:
                    end = datetime.fromisoformat(date_range['end_date'])
                    conditions.append(Project.modified_date <= end)
            
            # Relative date filters (e.g., "last 30 days")
            if 'days_ago' in rules:
                days = rules['days_ago']
                cutoff = datetime.utcnow() - timedelta(days=days)
                conditions.append(Project.modified_date >= cutoff)
            
            # Rating filters
            if 'min_rating' in rules:
                conditions.append(Project.rating >= rules['min_rating'])
            
            # Favorite filter
            if 'favorites_only' in rules and rules['favorites_only']:
                conditions.append(Project.is_favorite == True)
            
            # Export status
            if 'has_export' in rules:
                has_export = rules['has_export']
                if has_export:
                    # Projects with exports
                    query = query.join(Project.exports).distinct()
                else:
                    # Projects without exports
                    subquery = session.query(Project.id).join(Project.exports).subquery()
                    conditions.append(~Project.id.in_(session.query(subquery.c.id)))
            
            # Collection membership
            if 'in_collections' in rules:
                collection_ids = rules['in_collections']
                if collection_ids:
                    subquery = session.query(ProjectCollection.project_id).filter(
                        ProjectCollection.collection_id.in_(collection_ids)
                    ).subquery()
                    conditions.append(Project.id.in_(session.query(subquery.c.project_id)))
            
            # File size filters
            if 'min_size' in rules:
                conditions.append(Project.file_size >= rules['min_size'])
            if 'max_size' in rules:
                conditions.append(Project.file_size <= rules['max_size'])
            
            # Status filters
            if 'status' in rules:
                from ..database import ProjectStatus
                status = ProjectStatus(rules['status'])
                conditions.append(Project.status == status)
            
            # Tempo range filters
            if 'tempo_min' in rules:
                tempo_min = rules['tempo_min']
                if tempo_min > 0:
                    conditions.append(Project.tempo >= tempo_min)
                    conditions.append(Project.tempo.isnot(None))
            
            if 'tempo_max' in rules:
                tempo_max = rules['tempo_max']
                if tempo_max > 0 and tempo_max < 999:
                    conditions.append(Project.tempo <= tempo_max)
                    conditions.append(Project.tempo.isnot(None))
            
            # Apply all conditions
            if conditions:
                query = query.filter(and_(*conditions))
            
            # Exclude projects already in this collection (to avoid duplicates)
            existing_pc_ids = session.query(ProjectCollection.project_id).filter(
                ProjectCollection.collection_id == collection_id
            ).subquery()
            query = query.filter(~Project.id.in_(session.query(existing_pc_ids.c.project_id)))
            
            # Execute query
            result = query.all()
            return [row[0] for row in result]
            
        finally:
            session.close()
    
    @staticmethod
    def update_smart_collection(collection_id: int) -> int:
        """Update a smart collection by evaluating rules and adding matching projects.
        
        Args:
            collection_id: ID of the smart collection.
            
        Returns:
            Number of projects added.
        """
        session = get_session()
        try:
            collection = session.query(Collection).get(collection_id)
            if not collection or not collection.is_smart:
                return 0
            
            # Get matching project IDs
            matching_ids = SmartCollectionService.evaluate_smart_collection(collection_id)
            
            if not matching_ids:
                return 0
            
            # Get existing project IDs in collection
            existing_ids = set(
                pc.project_id for pc in session.query(ProjectCollection).filter(
                    ProjectCollection.collection_id == collection_id
                ).all()
            )
            
            # Add new projects
            added_count = 0
            for project_id in matching_ids:
                if project_id not in existing_ids:
                    # Get next track number
                    max_track = session.query(ProjectCollection).filter(
                        ProjectCollection.collection_id == collection_id
                    ).count()
                    
                    pc = ProjectCollection(
                        project_id=project_id,
                        collection_id=collection_id,
                        track_number=max_track + 1
                    )
                    session.add(pc)
                    added_count += 1
            
            session.commit()
            return added_count
            
        finally:
            session.close()
    
    @staticmethod
    def update_all_smart_collections() -> Dict[int, int]:
        """Update all smart collections.
        
        Returns:
            Dictionary mapping collection_id to number of projects added.
        """
        session = get_session()
        try:
            smart_collections = session.query(Collection).filter(
                Collection.is_smart == True
            ).all()
            
            results = {}
            for collection in smart_collections:
                count = SmartCollectionService.update_smart_collection(collection.id)
                results[collection.id] = count
            
            return results
        finally:
            session.close()
