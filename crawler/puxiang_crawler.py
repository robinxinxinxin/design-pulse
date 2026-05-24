"""
Puxiang (普象) crawler for design portfolio monitoring
"""
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from .base_crawler import BaseCrawler
from .filter import CategoryFilter


class PuxiangCrawler(BaseCrawler):
    """Crawler for Puxiang design platform (普象网)"""
    
    def __init__(self, headless: bool = True):
        super().__init__(source='puxiang', headless=headless)
        self.base_url = 'https://www.puxiang.com'
        self.filter = CategoryFilter()
        self.monitor_list = self._load_monitor_list()
        
    def _load_monitor_list(self) -> List[Dict[str, Any]]:
        """Load monitor list from JSON file, filter for Puxiang URLs"""
        monitor_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'monitor_list.json'
        )
        try:
            with open(monitor_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Combine companies and individuals
            all_creators = []
            
            # Add companies with puxiang URLs
            for company in data.get('companies', []):
                url = company.get('profile_url', '')
                if 'puxiang.com' in url and company.get('name') != '待补充':
                    all_creators.append({
                        **company,
                        'author_type': 'company'
                    })
            
            # Add individuals with puxiang URLs
            for individual in data.get('individuals', []):
                url = individual.get('profile_url', '')
                if 'puxiang.com' in url and individual.get('name') != '待补充':
                    all_creators.append({
                        **individual,
                        'author_type': 'individual'
                    })
            
            return all_creators
        except Exception as e:
            print(f"Failed to load monitor list: {e}")
            return []
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl all monitored Puxiang profiles"""
        all_projects = []
        
        if not self.monitor_list:
            print("No Puxiang profiles to monitor")
            return all_projects
        
        print(f"Crawling {len(self.monitor_list)} Puxiang profiles...")
        
        for creator in self.monitor_list:
            try:
                projects = self._check_creator(creator)
                all_projects.extend(projects)
                self.random_delay(1.0, 3.0)
            except Exception as e:
                print(f"Error checking {creator.get('name')}: {e}")
                continue
        
        # Filter for consumer electronics
        filtered = self.filter.filter_projects(all_projects, source='puxiang')
        print(f"Found {len(all_projects)} projects, {len(filtered)} are consumer electronics")
        
        return filtered
    
    def _check_creator(self, creator: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check a single creator's profile for new projects"""
        projects = []
        profile_url = creator.get('profile_url', '')
        name = creator.get('name', 'Unknown')
        author_type = creator.get('author_type', 'company')
        
        print(f"Checking {name}: {profile_url}")
        
        try:
            self.page.goto(profile_url, timeout=30000, wait_until='networkidle')
            self.random_delay(1.0, 2.0)
            
            # Wait for project cards to load
            self.page.wait_for_selector('a[href*="/galleries/"]', timeout=10000)
            
            # Get all project links
            project_cards = self.page.locator('a[href*="/galleries/"]').all()
            
            for card in project_cards[:20]:  # Limit to first 20 projects
                try:
                    project = self._parse_project_card(card, creator)
                    if project:
                        projects.append(project)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error loading profile {profile_url}: {e}")
        
        return projects
    
    def _parse_project_card(self, card, creator: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single project card"""
        try:
            # Get project URL
            href = card.get_attribute('href')
            if not href:
                return None
            
            source_url = urljoin(self.base_url, href)
            
            # Get title - usually in a heading or text content
            title = ''
            try:
                # Try to find title in the card
                title_elem = card.locator('h4, .title, [class*="title"]').first
                if title_elem.count() > 0:
                    title = title_elem.text_content().strip()
            except:
                pass
            
            # If no title found, use text content
            if not title:
                text = card.text_content().strip()
                # First line is usually the title
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                if lines:
                    # Skip lines that look like stats
                    for line in lines:
                        if not re.match(r'^\d+', line) and '赞' not in line and '评论' not in line and '人气' not in line:
                            title = line[:100]  # Limit title length
                            break
            
            if not title:
                return None
            
            # Get cover image
            cover_url = None
            try:
                img = card.locator('img').first
                if img.count() > 0:
                    cover_url = img.get_attribute('src')
                    if cover_url and not cover_url.startswith('http'):
                        cover_url = urljoin(self.base_url, cover_url)
            except:
                pass
            
            # Get project date by visiting detail page
            published_at = self._get_project_date(source_url)
            if not published_at:
                # If can't get date, use current time but mark for filtering
                published_at = datetime.now()
            
            # Check if within this week
            if not self.is_within_this_week(published_at):
                return None
            
            return {
                'title': title,
                'cover_url': cover_url,
                'author': creator.get('name', 'Unknown'),
                'author_type': creator.get('author_type', 'company'),
                'source': 'puxiang',
                'source_url': source_url,
                'published_at': published_at,
                'category': None
            }
            
        except Exception as e:
            return None
    
    def _get_project_date(self, project_url: str) -> Optional[datetime]:
        """Get project publish date from detail page"""
        try:
            # Open in a new tab to avoid losing state
            context = self.page.context
            new_page = context.new_page()
            
            try:
                new_page.goto(project_url, timeout=15000, wait_until='domcontentloaded')
                
                # Try to find date element
                # Common patterns: time element, date class, published info
                date_selectors = [
                    'time',
                    '[class*="date"]',
                    '[class*="time"]',
                    '[class*="publish"]',
                ]
                
                date_text = None
                for selector in date_selectors:
                    try:
                        elem = new_page.locator(selector).first
                        if elem.count() > 0:
                            text = elem.text_content().strip()
                            if text and len(text) < 50:  # Reasonable date length
                                date_text = text
                                break
                    except:
                        continue
                
                if date_text:
                    parsed = self._parse_puxiang_date(date_text)
                    if parsed:
                        return parsed
                
            finally:
                new_page.close()
                
        except Exception as e:
            pass
        
        return None
    
    def _parse_puxiang_date(self, date_str: str) -> Optional[datetime]:
        """Parse Puxiang date string to datetime"""
        # Clean the string
        date_str = date_str.strip()
        
        # Try various formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d',
            '%Y.%m.%d',
            '%Y年%m月%d日',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try to extract date pattern
        # Pattern: 2024-01-15 or 2024/01/15
        match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', date_str)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except:
                pass
        
        return None


def crawl_puxiang(headless: bool = True) -> List[Dict[str, Any]]:
    """Convenience function to crawl Puxiang"""
    with PuxiangCrawler(headless=headless) as crawler:
        return crawler.crawl()
