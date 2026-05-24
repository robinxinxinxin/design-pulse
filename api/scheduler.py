"""
Scheduler for automatic crawling
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from crawler.zcool_crawler import crawl_zcool
from crawler.behance_crawler import crawl_behance
from crawler.puxiang_crawler import crawl_puxiang
from processor.dedup import deduplicate_projects
from db.models import get_session, Project, CollectionLog


class CrawlScheduler:
    """Scheduler for automatic crawling tasks"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            # Schedule weekly crawl - every Monday at 9:00 AM
            self.scheduler.add_job(
                self.run_weekly_crawl,
                CronTrigger(day_of_week='mon', hour=9, minute=0),
                id='weekly_crawl',
                name='Weekly Design Monitor Crawl',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            print(f"Scheduler started at {datetime.now()}")
            print("Next run:", self.scheduler.get_job('weekly_crawl').next_run_time)
    
    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print("Scheduler stopped")
    
    def run_weekly_crawl(self):
        """Run the weekly crawl for all sources"""
        print(f"\n{'='*50}")
        print(f"Starting weekly crawl at {datetime.now()}")
        print(f"{'='*50}\n")
        
        # ZCOOL
        try:
            print("Crawling ZCOOL...")
            zcool_projects = crawl_zcool(headless=True)
            new_zcool = self._save_projects(zcool_projects, 'zcool')
            print(f"ZCOOL: {len(zcool_projects)} found, {new_zcool} new added")
        except Exception as e:
            print(f"ZCOOL crawl failed: {e}")
            self._log_error('zcool', str(e))
        
        # Puxiang
        try:
            print("\nCrawling Puxiang...")
            puxiang_projects = crawl_puxiang(headless=True)
            new_puxiang = self._save_projects(puxiang_projects, 'puxiang')
            print(f"Puxiang: {len(puxiang_projects)} found, {new_puxiang} new added")
        except Exception as e:
            print(f"Puxiang crawl failed: {e}")
            self._log_error('puxiang', str(e))
        
        # Behance
        try:
            print("\nCrawling Behance...")
            behance_projects = crawl_behance(headless=True)
            new_behance = self._save_projects(behance_projects, 'behance')
            print(f"Behance: {len(behance_projects)} found, {new_behance} new added")
        except Exception as e:
            print(f"Behance crawl failed: {e}")
            self._log_error('behance', str(e))
        
        print(f"\n{'='*50}")
        print(f"Weekly crawl completed at {datetime.now()}")
        print(f"{'='*50}\n")
    
    def _save_projects(self, projects, source):
        """Save projects to database"""
        # Deduplicate
        new_projects = deduplicate_projects(projects)
        
        if not new_projects:
            # Log success with 0 new
            self._log_success(source, 0)
            return 0
        
        # Save to database
        session = get_session()
        try:
            for project_data in new_projects:
                project = Project(**project_data)
                session.add(project)
            
            session.commit()
            
            # Log success
            self._log_success(source, len(new_projects))
            
            return len(new_projects)
        finally:
            session.close()
    
    def _log_success(self, source, count):
        """Log successful crawl"""
        session = get_session()
        try:
            log = CollectionLog(
                source=source,
                status='success',
                new_count=count
            )
            session.add(log)
            session.commit()
        finally:
            session.close()
    
    def _log_error(self, source, error_msg):
        """Log failed crawl"""
        session = get_session()
        try:
            log = CollectionLog(
                source=source,
                status='failed',
                error_msg=error_msg
            )
            session.add(log)
            session.commit()
        finally:
            session.close()


# Global scheduler instance
_scheduler = None


def get_scheduler():
    """Get or create scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CrawlScheduler()
    return _scheduler


def start_scheduler():
    """Start the scheduler"""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


def stop_scheduler():
    """Stop the scheduler"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None


if __name__ == '__main__':
    import time
    
    # Test the scheduler
    scheduler = start_scheduler()
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()
        print("Scheduler stopped by user")
