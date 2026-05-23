"""
ZCOOL crawler for product rendering works
"""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from crawler.base_crawler import BaseCrawler
from processor.filter import CategoryFilter


class ZcoolCrawler(BaseCrawler):
    """Crawler for zcool.com.cn"""
    
    def __init__(self, headless: bool = True):
        super().__init__(source='zcool', headless=headless)
        self.base_url = 'https://www.zcool.com.cn'
        self.filter = CategoryFilter()
        
    def crawl(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Crawl ZCOOL for product rendering works
        
        Args:
            max_pages: Maximum number of search pages to crawl
        
        Returns:
            List of project dictionaries
        """
        all_projects = []
        keywords = self.load_keywords()
        search_keywords = keywords.get('zcool', {}).get('search_keywords', ['产品渲染'])
        
        try:
            self.init_browser()
            
            for keyword in search_keywords[:3]:  # Limit to first 3 keywords
                print(f"Searching ZCOOL for: {keyword}")
                projects = self.retry_action(
                    lambda kw=keyword: self._search_keyword(kw, max_pages)
                )
                all_projects.extend(projects)
                self.random_delay(3, 6)
                
        except Exception as e:
            print(f"Error crawling ZCOOL: {e}")
        finally:
            self.close_browser()
        
        # Filter for consumer electronics
        filtered_projects = self.filter.filter_projects(all_projects, source='zcool')
        print(f"ZCOOL: Found {len(all_projects)} total, {len(filtered_projects)} consumer electronics")
        
        return filtered_projects
    
    def _search_keyword(self, keyword: str, max_pages: int) -> List[Dict[str, Any]]:
        """Search for a specific keyword"""
        projects = []
        
        for page in range(1, max_pages + 1):
            # 使用 recommendLevel=1 获取推荐作品
            url = f"{self.base_url}/search/content?word={keyword}&sort=7&page={page}&recommendLevel=1"
            print(f"  Fetching page {page}: {url}")
            
            try:
                # 先等待页面加载
                self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                # 等待内容加载
                self.page.wait_for_load_state('networkidle', timeout=30000)
                # 额外等待确保动态内容渲染
                self.random_delay(5, 8)
                
                # 使用 Playwright locator 获取动态内容
                work_cards = self.page.locator('section.content-box_card').all()
                
                print(f"    Found {len(work_cards)} work cards")
                
                for card in work_cards:
                    project = self._parse_work_card_playwright(card)
                    if project:
                        projects.append(project)
                
                # Check if we should continue to next page
                if len(work_cards) == 0:
                    break
                    
                self.random_delay(2, 5)
                
            except Exception as e:
                print(f"    Error on page {page}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return projects
    
    def _parse_work_card_playwright(self, card) -> Optional[Dict[str, Any]]:
        """Parse a work card element using Playwright locator"""
        try:
            # 获取卡片内的所有文本
            card_text = card.inner_text()
            lines = [line.strip() for line in card_text.split('\n') if line.strip()]
            
            if not lines:
                return None
            
            # 第一行通常是标题
            title = lines[0] if lines else ''
            
            # 查找链接 - 通常是标题链接
            try:
                link_elem = card.locator('a').first
                href = link_elem.get_attribute('href') or ''
                if href:
                    source_url = href if href.startswith('http') else f"{self.base_url}{href}"
                else:
                    source_url = ''
            except:
                source_url = ''
            
            # 查找图片
            try:
                img_elem = card.locator('img').first
                cover_url = img_elem.get_attribute('src') or ''
                if not cover_url:
                    cover_url = img_elem.get_attribute('data-src') or ''
            except:
                cover_url = ''
            
            # 作者通常是第二行或包含特定关键词的行
            author = 'Unknown'
            for line in lines[1:]:
                if '设计师' in line or '人气' in line or '浏览' in line:
                    continue
                if line and line != title:
                    author = line
                    break
            
            # 日期解析 - 从文本中找日期格式
            published_at = None
            for line in lines:
                date = self._parse_zcool_date(line)
                if date:
                    published_at = date
                    break

            # 如果解析不出日期，跳过该作品
            if published_at is None:
                return None
            
            # 只保留本周的作品
            if not self.is_within_this_week(published_at):
                return None
            
            return {
                'title': title,
                'cover_url': cover_url,
                'author': author,
                'author_type': 'individual',
                'source': 'zcool',
                'source_url': source_url,
                'published_at': published_at,
                'category': None
            }
            
        except Exception as e:
            print(f"    Error parsing card: {e}")
            return None
    
    def _parse_work_card(self, card) -> Optional[Dict[str, Any]]:
        """Parse a work card element (legacy method for BeautifulSoup)"""
        try:
            # Try multiple selectors for title
            title_elem = (
                card.find('a', class_=re.compile('title|work-title')) or
                card.find('h3') or
                card.find('a', title=True)
            )
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # Try multiple selectors for link
            link_elem = (
                card.find('a', href=re.compile('/work/|/article/')) or
                title_elem
            )
            relative_url = link_elem.get('href', '') if link_elem else ''
            source_url = relative_url if relative_url.startswith('http') else f"{self.base_url}{relative_url}"
            
            # Try multiple selectors for cover image
            img_elem = (
                card.find('img', class_=re.compile('cover|lazy|work-img')) or
                card.find('img')
            )
            cover_url = img_elem.get('src', '') if img_elem else ''
            if not cover_url:
                cover_url = img_elem.get('data-src', '') if img_elem else ''
            
            # Try multiple selectors for author
            author_elem = (
                card.find('a', class_=re.compile('author|user|nickname')) or
                card.find('span', class_=re.compile('author|user'))
            )
            author = author_elem.get_text(strip=True) if author_elem else 'Unknown'
            
            # Try multiple selectors for date
            date_elem = (
                card.find('span', class_=re.compile('time|date')) or
                card.find('time')
            )
            date_str = date_elem.get_text(strip=True) if date_elem else ''
            published_at = self._parse_zcool_date(date_str)
            
            # Only include if within this week
            if not published_at or not self.is_within_this_week(published_at):
                return None
            
            return {
                'title': title,
                'cover_url': cover_url,
                'author': author,
                'author_type': 'individual',
                'source': 'zcool',
                'source_url': source_url,
                'published_at': published_at,
                'category': None
            }
            
        except Exception as e:
            print(f"    Error parsing card: {e}")
            return None
    
    def _parse_zcool_date(self, date_str: str) -> Optional[datetime]:
        """Parse ZCOOL date string"""
        if not date_str:
            return None
        
        # Common ZCOOL date formats
        patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
            (r'(\d{4})/(\d{2})/(\d{2})', '%Y/%m/%d'),
            (r'(\d{2})-(\d{2})', '%m-%d'),  # Current year assumed
            (r'(\d{2})/(\d{2})', '%m/%d'),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if len(match.groups()) == 2:
                        # Month-day only, assume current year
                        date_str_full = f"{datetime.now().year}-{match.group(1)}-{match.group(2)}"
                        return datetime.strptime(date_str_full, '%Y-%m-%d')
                    else:
                        return datetime.strptime(match.group(0), fmt)
                except ValueError:
                    continue
        
        # If no pattern matches, return None
        return None


def crawl_zcool(headless: bool = True) -> List[Dict[str, Any]]:
    """Convenience function to crawl ZCOOL"""
    crawler = ZcoolCrawler(headless=headless)
    return crawler.crawl()


if __name__ == '__main__':
    # Test the crawler
    projects = crawl_zcool(headless=False)
    print(f"\nTotal projects found: {len(projects)}")
    for p in projects[:5]:
        print(f"  - {p['title']} by {p['author']}")
