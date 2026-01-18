"""Tests for database models and operations."""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile

from src.database.db import get_engine, init_database, session_scope, close_database
from src.database.models import (
    Base, Project, Location, Collection, Tag,
    ProjectCollection, Export, LinkDevice,
    LocationType, ProjectStatus, CollectionType
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    init_database(db_path)
    yield db_path
    
    close_database()
    db_path.unlink()


class TestLocationModel:
    """Tests for the Location model."""
    
    def test_create_location(self, temp_db):
        """Test creating a location."""
        with session_scope() as session:
            location = Location(
                name="Test Location",
                path="/test/path",
                location_type=LocationType.LOCAL,
                is_active=True
            )
            session.add(location)
        
        with session_scope() as session:
            loc = session.query(Location).filter(Location.name == "Test Location").first()
            assert loc is not None
            assert loc.path == "/test/path"
            assert loc.location_type == LocationType.LOCAL
    
    def test_location_types(self, temp_db):
        """Test different location types."""
        for loc_type in LocationType:
            with session_scope() as session:
                location = Location(
                    name=f"Test {loc_type.value}",
                    path=f"/test/{loc_type.value}",
                    location_type=loc_type
                )
                session.add(location)
            
            with session_scope() as session:
                loc = session.query(Location).filter(
                    Location.location_type == loc_type
                ).first()
                assert loc is not None


class TestProjectModel:
    """Tests for the Project model."""
    
    def test_create_project(self, temp_db):
        """Test creating a project."""
        with session_scope() as session:
            location = Location(name="Test", path="/test")
            session.add(location)
            session.flush()
            
            project = Project(
                name="Test Project",
                file_path="/test/project.als",
                location_id=location.id,
                file_size=1024,
                status=ProjectStatus.LOCAL
            )
            session.add(project)
        
        with session_scope() as session:
            proj = session.query(Project).filter(Project.name == "Test Project").first()
            assert proj is not None
            assert proj.file_size == 1024
            assert proj.status == ProjectStatus.LOCAL
    
    def test_project_tags_json(self, temp_db):
        """Test storing tags as JSON."""
        with session_scope() as session:
            project = Project(
                name="Tagged Project",
                file_path="/test/tagged.als",
                tags=[1, 2, 3]
            )
            session.add(project)
        
        with session_scope() as session:
            proj = session.query(Project).filter(Project.name == "Tagged Project").first()
            assert proj.tags == [1, 2, 3]
            assert proj.tag_list == [1, 2, 3]


class TestCollectionModel:
    """Tests for the Collection model."""
    
    def test_create_collection(self, temp_db):
        """Test creating a collection."""
        with session_scope() as session:
            collection = Collection(
                name="Test Album",
                collection_type=CollectionType.ALBUM,
                description="A test album"
            )
            session.add(collection)
        
        with session_scope() as session:
            coll = session.query(Collection).filter(Collection.name == "Test Album").first()
            assert coll is not None
            assert coll.collection_type == CollectionType.ALBUM
    
    def test_project_collection_relationship(self, temp_db):
        """Test adding projects to collections."""
        with session_scope() as session:
            project = Project(name="Track 1", file_path="/test/track1.als")
            collection = Collection(name="Album", collection_type=CollectionType.ALBUM)
            session.add_all([project, collection])
            session.flush()
            
            pc = ProjectCollection(
                project_id=project.id,
                collection_id=collection.id,
                track_number=1
            )
            session.add(pc)
        
        with session_scope() as session:
            coll = session.query(Collection).filter(Collection.name == "Album").first()
            assert len(coll.project_collections) == 1
            assert coll.projects[0].name == "Track 1"


class TestTagModel:
    """Tests for the Tag model."""
    
    def test_create_tag(self, temp_db):
        """Test creating a tag."""
        with session_scope() as session:
            tag = Tag(
                name="WIP",
                color="#ff0000",
                category="Status"
            )
            session.add(tag)
        
        with session_scope() as session:
            t = session.query(Tag).filter(Tag.name == "WIP").first()
            assert t is not None
            assert t.color == "#ff0000"
            assert t.category == "Status"


class TestExportModel:
    """Tests for the Export model."""
    
    def test_create_export(self, temp_db):
        """Test creating an export."""
        with session_scope() as session:
            project = Project(name="Source", file_path="/test/source.als")
            session.add(project)
            session.flush()
            
            export = Export(
                project_id=project.id,
                export_path="/exports/song.wav",
                export_name="song",
                format="wav",
                file_size=10240
            )
            session.add(export)
        
        with session_scope() as session:
            exp = session.query(Export).filter(Export.export_name == "song").first()
            assert exp is not None
            assert exp.format == "wav"
            assert exp.project is not None


class TestLinkDeviceModel:
    """Tests for the LinkDevice model."""
    
    def test_create_link_device(self, temp_db):
        """Test creating a Link device."""
        with session_scope() as session:
            device = LinkDevice(
                device_name="Ableton Live",
                ip_address="192.168.1.100",
                port=20808,
                is_active=True
            )
            session.add(device)
        
        with session_scope() as session:
            dev = session.query(LinkDevice).filter(
                LinkDevice.device_name == "Ableton Live"
            ).first()
            assert dev is not None
            assert dev.ip_address == "192.168.1.100"
            assert dev.is_active is True
