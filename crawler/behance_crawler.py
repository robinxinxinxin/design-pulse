"""
Behance crawler for design companies and individuals
"""
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from crawler.base_crawler import BaseCrawler
from processor.filter import CategoryFilter


class BehanceCrawler(BaseCrawler):
    """Crawler for behance.net"""
    
    def __init__(self, headless: bool = True):
        super().__init__(source='behance', headless=headless)
        self.base_url = 'https://www.behance.net'
        self.filter = CategoryFilter()
        self.monitor_list = self._load_monitor_list()
        
    def _load_monitor_list(self) -> List[Dict[str, Any]]:
        """Load monitor list from configuration"""
        monitor_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'monitor_list.json'
        )
        with open(monitor_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Combine companies and individuals
        all_creators = []
        for company in data.get('companies', []):
            if company.get('profile_url'):
                all_creators.append({
                    'name': company['name'],
                    'type': 'company',
                    'profile_url': company['profile_url']
                })
        
        for individual in data.get('individuals', []):
            if individual.get('profile_url') and individual['name'] != '待补充':
                all_creators.append({
                    'name': individual['name'],
                    'type': 'individual',
                    'profile_url': individual['profile_url']
                })
        
        return all_creators
    
    def crawl(self) -> List[Dict[str, Any]]:
        """
        Crawl Behance for projects from monitored creators
        
        Returns:
            List of project dictionaries
        """
        all_projects = []
        
        if not self.monitor_list:
            print("Warning: No creators in monitor list. Please update data/monitor_list.json")
            return all_projects
        
        try:
            self.init_browser()
            
            for creator in self.monitor_list:
                print(f"Checking Behance creator: {creator['name']}")
                projects = self._check_creator(creator)
                all_projects.extend(projects)
                self.random_delay(5, 10)
                
        except Exception as e:
            print(f"Error crawling Behance: {e}")
        finally:
            self.close_browser()
        
        # Filter for consumer electronics
        filtered_projects = self.filter.filter_projects(all_projects, source='behance')
        print(f"Behance: Found {len(all_projects)} total, {len(filtered_projects)} consumer electronics")
        
        return filtered_projects
    
    def _check_creator(self, creator: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check a creator's profile for new projects"""
        projects = []
        profile_url = creator['profile_url']
        
        try:
            # Ensure URL has protocol
            if not profile_url.startswith('http'):
                profile_url = f"{self.base_url}/{profile_url}"
            
            print(f"  Fetching profile: {profile_url}")
            self.page.goto(profile_url, wait_until='networkidle', timeout=30000)
            self.random_delay(3, 5)
            
            # Parse the page
            html = self.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find project cards - Behance uses various selectors
            project_cards = soup.find_all('div', class_=re.compile('ProjectCover-root|ProjectCoverNeue|project-cover'))
            
            if not project_cards:
                # Try alternative selectors
                project_cards = soup.select('[class*="ProjectCover"], [class*="project-cover"]')
            
            print(f"    Found {len(project_cards)} project cards")
            
            for card in project_cards:
                project = self._parse_project_card(card, creator)
                if project:
                    projects.append(project)
                    
        except Exception as e:
            print(f"    Error checking creator {creator['name']}: {e}")
        
        return projects
    
    def _parse_project_card(self, card, creator: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a project card element"""
        try:
            # Try multiple selectors for title
            title_elem = (
                card.find('div', class_=re.compile('Title|title|project-title')) or
                card.find('h3') or
                card.find('a', title=True)
            )
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # Try multiple selectors for link
            link_elem = (
                card.find('a', href=re.compile('/gallery/|/projects/')) or
                card.find_parent('a', href=re.compile('/gallery/')) or
                title_elem.find_parent('a') if title_elem else None
            )
            relative_url = link_elem.get('href', '') if link_elem else ''
            source_url = relative_url if relative_url.startswith('http') else f"{self.base_url}{relative_url}"
            
            # Try multiple selectors for cover image
            img_elem = (
                card.find('img', class_=re.compile('cover|Cover|image')) or
                card.find('img')
            )
            cover_url = img_elem.get('src', '') if img_elem else ''
            if not cover_url:
                cover_url = img_elem.get('data-src', '') if img_elem else ''
            
            # Try to get published date from the card or project page
            # Behance often doesn't show date on the card, so we check the project page
            published_at = self._get_project_date(source_url)
            
            # Only include if within this week
            if not published_at or not self.is_within_this_week(published_at):
                return None
            
            return {
                'title': title,
                'cover_url': cover_url,
                'author': creator['name'],
                'author_type': creator['type'],
                'source': 'behance',
                'source_url': source_url,
                'published_at': published_at,
                'category': None
            }
            
        except Exception as e:
            print(f"    Error parsing project card: {e}")
            return None
    
    def _get_project_date(self, project_url: str) -> Optional[datetime]:
        """Get project published date by visiting project page"""
        try:
            # Open project page in new tab to avoid losing current page
            new_page = self.browser.new_page()
            new_page.goto(project_url, wait_until='networkidle', timeout=20000)
            
            html = new_page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try multiple selectors for date
            date_elem = (
                soup.find('time') or
                soup.find('span', class_=re.compile('date|Date|published')) or
                soup.find('div', class_=re.compile('date|Date|published'))
            )
            
            date_str = date_elem.get_text(strip=True) if date_elem else ''
            
            # Close the new tab
            new_page.close()
            
            return self._parse_behance_date(date_str)
            
        except Exception as e:
            print(f"      Error getting project date: {e}")
            # Return today as fallback
            return datetime.now()
    
    def _parse_behance_date(self, date_str: str) -> Optional[datetime]:
        """Parse Behance date string"""
        if not date_str:
            return datetime.now()
        
        # Common Behance date formats
        patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
            (r'(\d{4})/(\d{2})/(\d{2})', '%Y/%m/%d'),
            (r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', None),  # e.g., "January 15, 2024"
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if fmt:
                        return datetime.strptime(match.group(0), fmt)
                    else:
                        # Handle text month
                        from dateutil import parser
                        return parser.parse(match.group(0))
                except (ValueError, ImportError):
                    continue
        
        # If no pattern matches, assume today
        return datetime.now()


def crawl_behance(headless: bool = True) -> List[Dict[str, Any]]:
    """Convenience function to crawl Behance"""
    crawler = BehanceCrawler(headless=headless)
    return crawler.crawl()


if __name__ == '__main__':
    # Test the crawler
    projects = crawl_behance(headless=False)
    print(f"\nTotal projects found: {len(projects)}")
    for p in projects[:5]:
        print(f"  - {p['title']} by {p['author']}")
