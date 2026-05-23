"""
Main entry point for design monitor system
Usage: python run.py [command]

Commands:
    api       - Start the FastAPI server
    scheduler - Start the scheduler (runs weekly crawl)
    crawl     - Run crawl manually
    init      - Initialize database
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.models import init_db
from api.scheduler import start_scheduler, stop_scheduler
from crawler.zcool_crawler import crawl_zcool
from crawler.behance_crawler import crawl_behance
from processor.dedup import deduplicate_projects
from db.models import get_session, Project, CollectionLog


def run_api():
    """Start FastAPI server"""
    import uvicorn
    from api.main import app
    
    print("Starting Design Monitor API server...")
    print("API docs available at: http://localhost:8000/docs")
    print("Dashboard available at: http://localhost:8000/")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_scheduler():
    """Start scheduler"""
    import time
    
    print("Starting scheduler...")
    scheduler = start_scheduler()
    
    try:
        print("Scheduler is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()
        print("\nScheduler stopped.")


def run_crawl():
    """Run manual crawl"""
    print("Starting manual crawl...\n")
    
    # ZCOOL
    print("=" * 50)
    print("Crawling ZCOOL...")
    print("=" * 50)
    try:
        zcool_projects = crawl_zcool(headless=True)
        new_zcool = save_projects(zcool_projects, 'zcool')
        print(f"\nZCOOL: {len(zcool_projects)} found, {new_zcool} new added")
    except Exception as e:
        print(f"ZCOOL crawl failed: {e}")
        log_error('zcool', str(e))
    
    # Behance
    print("\n" + "=" * 50)
    print("Crawling Behance...")
    print("=" * 50)
    try:
        behance_projects = crawl_behance(headless=True)
        new_behance = save_projects(behance_projects, 'behance')
        print(f"\nBehance: {len(behance_projects)} found, {new_behance} new added")
    except Exception as e:
        print(f"Behance crawl failed: {e}")
        log_error('behance', str(e))
    
    print("\n" + "=" * 50)
    print("Crawl completed!")
    print("=" * 50)


def save_projects(projects, source):
    """Save projects to database"""
    # Deduplicate
    new_projects = deduplicate_projects(projects)
    
    if not new_projects:
        log_success(source, 0)
        return 0
    
    # Save to database
    session = get_session()
    try:
        for project_data in new_projects:
            project = Project(**project_data)
            session.add(project)
        
        session.commit()
        log_success(source, len(new_projects))
        
        return len(new_projects)
    finally:
        session.close()


def log_success(source, count):
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


def log_error(source, error_msg):
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


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'api':
        run_api()
    elif command == 'scheduler':
        run_scheduler()
    elif command == 'crawl':
        run_crawl()
    elif command == 'init':
        init_db()
        print("Database initialized successfully!")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
