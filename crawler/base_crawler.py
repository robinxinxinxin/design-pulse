"""
Base crawler class with common functionality
"""
import json
import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page, Browser


class BaseCrawler(ABC):
    """Base class for all crawlers"""
    
    def __init__(self, source: str, headless: bool = True):
        self.source = source
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        
    def init_browser(self):
        """Initialize browser with stealth options"""
        playwright = sync_playwright().start()
        
        browser = playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        context = browser.new_context(
            user_agent=random.choice(self.user_agents),
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )

        # Load saved cookies if available
        cookies_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'cookies'
        )
        cookies_file = os.path.join(cookies_dir, f'{self.source}_cookies.json')
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    saved_cookies = json.load(f)
                if saved_cookies:
                    context.add_cookies(saved_cookies)
                    print(f"Loaded {len(saved_cookies)} cookies for {self.source}")
            except Exception as e:
                print(f"Failed to load cookies for {self.source}: {e}")
        
        # Add stealth scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
        """)
        
        self.browser = browser
        self.page = context.new_page()
        self.context = context
        self.playwright = playwright
        
    def save_cookies(self):
        """Save current browser cookies to JSON file"""
        if not hasattr(self, 'context') or self.context is None:
            return
        try:
            cookies_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'cookies'
            )
            os.makedirs(cookies_dir, exist_ok=True)
            cookies_file = os.path.join(cookies_dir, f'{self.source}_cookies.json')
            cookies = self.context.cookies()
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"Saved {len(cookies)} cookies for {self.source}")
        except Exception as e:
            print(f"Failed to save cookies for {self.source}: {e}")

    def close_browser(self):
        """Close browser and save cookies"""
        self.save_cookies()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
            
    def random_delay(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        """Random delay to avoid being blocked"""
        time.sleep(random.uniform(min_seconds, max_seconds))
        
    def load_keywords(self) -> Dict[str, Any]:
        """Load keywords configuration"""
        keywords_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'keywords.json'
        )
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def is_within_this_week(self, date: datetime, weeks: int = 1) -> bool:
        """Check if date is within recent weeks
        
        Args:
            date: The date to check
            weeks: Number of weeks to look back (default 1 = this week only)
        """
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        if weeks > 1:
            week_start -= timedelta(weeks=weeks - 1)
        return date >= week_start
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d',
            '%Y.%m.%d',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def retry_action(self, action_fn, max_retries: int = 3, delay: float = 2):
        """Execute an action with retry on failure
        
        Args:
            action_fn: Callable to execute
            max_retries: Maximum number of retry attempts
            delay: Seconds to wait between retries
            
        Returns:
            The return value of action_fn on success
            
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                return action_fn()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    print(f"Retrying ({attempt}/{max_retries})...")
                    time.sleep(delay)
                else:
                    print(f"Max retries ({max_retries}) exceeded.")
        raise last_exception
    
    @abstractmethod
    def crawl(self) -> List[Dict[str, Any]]:
        """Main crawl method - to be implemented by subclasses"""
        pass
    
    def __enter__(self):
        self.init_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_browser()
