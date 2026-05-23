"""
Database models for design monitor system
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

class Project(Base):
    """Design project model"""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    cover_url = Column(Text, nullable=True)
    author = Column(String(200), nullable=False)
    author_type = Column(String(50), nullable=False, default='individual')  # 'company' or 'individual'
    source = Column(String(50), nullable=False)  # 'zcool' or 'behance'
    source_url = Column(Text, nullable=False, unique=True)  # For deduplication
    published_at = Column(DateTime, nullable=False)
    collected_at = Column(DateTime, default=datetime.now)
    category = Column(String(100), nullable=True)  # Product category tag
    
    def __repr__(self):
        return f"<Project({self.source}: {self.title[:30]}...)>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'cover_url': self.cover_url,
            'author': self.author,
            'author_type': self.author_type,
            'source': self.source,
            'source_url': self.source_url,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
            'category': self.category
        }


class MonitorList(Base):
    """List of creators to monitor on Behance"""
    __tablename__ = 'monitor_list'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # Creator name
    type = Column(String(50), nullable=False, default='company')  # 'company' or 'individual'
    source = Column(String(50), nullable=False, default='behance')  # Platform
    profile_url = Column(Text, nullable=False)  # Behance profile URL
    is_active = Column(Boolean, default=True)  # Whether to monitor this creator
    
    def __repr__(self):
        return f"<MonitorList({self.name}: {self.profile_url})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'source': self.source,
            'profile_url': self.profile_url,
            'is_active': self.is_active
        }


class CollectionLog(Base):
    """Collection execution logs"""
    __tablename__ = 'collection_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # 'zcool' or 'behance'
    status = Column(String(50), nullable=False)  # 'success' or 'failed'
    new_count = Column(Integer, default=0)  # Number of new projects added
    error_msg = Column(Text, nullable=True)  # Error message if failed
    duration_seconds = Column(Float, nullable=True)  # Crawl duration in seconds
    ran_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<CollectionLog({self.source}: {self.status}, {self.new_count} new)>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source,
            'status': self.status,
            'new_count': self.new_count,
            'error_msg': self.error_msg,
            'duration_seconds': self.duration_seconds,
            'ran_at': self.ran_at.isoformat() if self.ran_at else None
        }


# Database setup
def get_db_path():
    """Get database file path"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'data', 'design_monitor.db')


def get_engine():
    """Create database engine"""
    db_path = get_db_path()
    return create_engine(f'sqlite:///{db_path}', echo=False)


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Database initialized at: {get_db_path()}")


def get_session():
    """Get database session"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    init_db()
