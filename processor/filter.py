"""
Category filter for consumer electronics products
"""
import json
import os
from typing import Dict, List, Any


class CategoryFilter:
    """Filter projects by consumer electronics category"""
    
    def __init__(self):
        self.keywords = self._load_keywords()
        
    def _load_keywords(self) -> Dict[str, Any]:
        """Load keywords from configuration file"""
        keywords_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'keywords.json'
        )
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def is_consumer_electronics(self, title: str, description: str = "", source: str = "zcool") -> bool:
        """
        Check if project is consumer electronics based on title and description
        
        Args:
            title: Project title
            description: Project description (optional)
            source: 'zcool', 'behance', or 'puxiang'
        
        Returns:
            True if project is consumer electronics
        """
        text = f"{title} {description}".lower()
        
        # Get keywords for the source
        if source in self.keywords and 'category_keywords' in self.keywords[source]:
            include_keywords = self.keywords.get(source, {}).get('category_keywords', {}).get('include', [])
            exclude_keywords = self.keywords.get(source, {}).get('category_keywords', {}).get('exclude', [])
        else:
            # Fallback to zcool keywords if source not found
            include_keywords = self.keywords.get('zcool', {}).get('category_keywords', {}).get('include', [])
            exclude_keywords = self.keywords.get('zcool', {}).get('category_keywords', {}).get('exclude', [])
        
        # Check exclude keywords first
        for keyword in exclude_keywords:
            if keyword.lower() in text:
                return False
        
        # Check include keywords
        for keyword in include_keywords:
            if keyword.lower() in text:
                return True
        
        return False
    
    def filter_projects(self, projects: List[Dict[str, Any]], source: str = "zcool") -> List[Dict[str, Any]]:
        """
        Filter a list of projects
        
        Args:
            projects: List of project dictionaries
            source: 'zcool', 'behance', or 'puxiang'
        
        Returns:
            Filtered list of consumer electronics projects
        """
        filtered = []
        for project in projects:
            title = project.get('title', '')
            description = project.get('description', '')
            
            if self.is_consumer_electronics(title, description, source):
                project['category'] = 'consumer_electronics'
                filtered.append(project)
        
        return filtered


if __name__ == '__main__':
    # Test the filter
    filter_obj = CategoryFilter()
    
    test_cases = [
        {"title": "智能手表产品渲染", "source": "zcool"},
        {"title": "手机APP界面设计", "source": "zcool"},
        {"title": "Wireless Headphone Design", "source": "behance"},
        {"title": "Brand Logo Design", "source": "behance"},
    ]
    
    for test in test_cases:
        result = filter_obj.is_consumer_electronics(test['title'], source=test['source'])
        print(f"'{test['title']}' -> {result}")
