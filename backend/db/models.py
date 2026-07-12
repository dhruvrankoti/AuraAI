import uuid
import json
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, JSON, func
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from db.session import Base

class SafeVector(TypeDecorator):
    impl = TEXT

    def __init__(self, dimensions):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        else:
            return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        try:
            return json.loads(value)
        except Exception:
            return value

class Photo(Base):
    __tablename__ = "photos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_type = Column(String(20), nullable=False)  # 'local' or 'google_photos'
    file_path = Column(String, unique=True, index=True, nullable=False)
    sha256 = Column(String(64), unique=True, index=True, nullable=True)
    phash = Column(String(64), index=True, nullable=True)
    category = Column(String(50), index=True, nullable=True)  # 'document', 'receipt', 'prescription', 'travel', 'pets', 'people', 'other'
    caption = Column(Text, nullable=True)
    ocr_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    taken_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)  # Location, camera details, etc.
    clip_embedding = Column(SafeVector(512), nullable=True)
    ocr_embedding = Column(SafeVector(384), nullable=True)

    # Relationships
    faces = relationship("Face", back_populates="photo", cascade="all, delete-orphan")

class Face(Base):
    __tablename__ = "faces"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    photo_id = Column(String, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    face_embedding = Column(SafeVector(512), nullable=True)
    bounding_box = Column(JSON, nullable=True)  # {x1, y1, x2, y2}
    person_cluster_id = Column(String, ForeignKey("person_clusters.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    photo = relationship("Photo", back_populates="faces")
    person_cluster = relationship("PersonCluster", back_populates="faces")

class PersonCluster(Base):
    __tablename__ = "person_clusters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), default="Unknown", nullable=False)
    cover_face_id = Column(String, nullable=True)  # Face ID used as thumbnail

    # Relationships
    faces = relationship("Face", back_populates="person_cluster")
