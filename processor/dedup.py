"""
Deduplication logic for projects
"""
from typing import List, Dict, Any, Set
from db.models import get_session, Project


class Deduplicator:
    """Handle project deduplication"""
    
    def __init__(self):
        self.session = get_session()
        self.existing_urls: Set[str] = set()
        self._load_existing_urls()
    
    def _load_existing_urls(self):
        """Load all existing project URLs from database"""
        projects = self.session.query(Project.source_url).all()
        self.existing_urls = {p[0] for p in projects}
        print(f"Loaded {len(self.existing_urls)} existing project URLs")
    
    def is_duplicate(self, source_url: str) -> bool:
        """Check if URL already exists"""
        return source_url in self.existing_urls
    
    def filter_duplicates(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out duplicate projects
        
        Args:
            projects: List of project dictionaries
        
        Returns:
            List of new (non-duplicate) projects
        """
        new_projects = []
        for project in projects:
            source_url = project.get('source_url')
            if source_url and not self.is_duplicate(source_url):
                new_projects.append(project)
                # Add to existing set to avoid duplicates within the same batch
                self.existing_urls.add(source_url)
        
        return new_projects
    
    def close(self):
        """Close database session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def deduplicate_projects(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to deduplicate projects
    
    Args:
        projects: List of project dictionaries
    
    Returns:
        List of new (non-duplicate) projects
    """
    with Deduplicator() as dedup:
        return dedup.filter_duplicates(projects)


if __name__ == '__main__':
    # Test deduplication
    test_projects = [
        {'title': 'Project 1', 'source_url': 'https://example.com/1'},
        {'title': 'Project 2', 'source_url': 'https://example.com/2'},
        {'title': 'Project 3', 'source_url': 'https://example.com/1'},  # Duplicate
    ]
    
    with Deduplicator() as dedup:
        new_projects = dedup.filter_duplicates(test_projects)
        print(f"Original: {len(test_projects)}, New: {len(new_projects)}")
        for p in new_projects:
            print(f"  - {p['title']}: {p['source_url']}")
