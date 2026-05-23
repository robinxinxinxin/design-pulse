"""
FastAPI backend for design monitor system
"""
import sys
import os
import json
import time
import uuid
import threading
import queue

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from datetime import datetime, timedelta
from typing import List, Optional

from db.models import get_session, Project, CollectionLog
from crawler.zcool_crawler import crawl_zcool
from crawler.behance_crawler import crawl_behance
from processor.filter import CategoryFilter
from processor.dedup import deduplicate_projects

app = FastAPI(
    title="Design Monitor API",
    description="API for monitoring design trends from ZCOOL and Behance",
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global task storage for async crawl tasks
crawl_tasks = {}  # task_id -> {"status": str, "progress": list, "result": dict, "error": str}


# ============ Helper functions for async crawl ============

def _run_crawl_source(source: str, task_id: str, headless: bool, progress_queue: queue.Queue):
    """Run a single source crawl in a background thread, pushing progress to the queue."""
    start_time = time.time()
    try:
        progress_queue.put({
            "source": source,
            "step": f"开始采集 {source}...",
            "found": 0,
            "status": "crawling"
        })

        if source == 'zcool':
            projects = crawl_zcool(headless=headless)
        elif source == 'behance':
            projects = crawl_behance(headless=headless)
        else:
            raise ValueError(f"Unknown source: {source}")

        progress_queue.put({
            "source": source,
            "step": f"{source} 搜索完成，找到 {len(projects)} 个作品",
            "found": len(projects),
            "status": "crawling"
        })

        # Deduplicate
        new_projects = deduplicate_projects(projects)

        # Save to database
        session = get_session()
        try:
            for project_data in new_projects:
                project = Project(**project_data)
                session.add(project)

            # Calculate duration
            duration = round(time.time() - start_time, 2)

            # Log the collection
            log = CollectionLog(
                source=source,
                status='success',
                new_count=len(new_projects),
                duration_seconds=duration
            )
            session.add(log)
            session.commit()

            progress_queue.put({
                "source": source,
                "step": f"{source} 采集完成",
                "found": len(projects),
                "new_added": len(new_projects),
                "status": "done"
            })

            crawl_tasks[task_id]["result"] = {
                "source": source,
                "status": "success",
                "found": len(projects),
                "new_added": len(new_projects)
            }
        finally:
            session.close()

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        # Log failure
        session = get_session()
        try:
            log = CollectionLog(
                source=source,
                status='failed',
                error_msg=str(e),
                duration_seconds=duration
            )
            session.add(log)
            session.commit()
        finally:
            session.close()

        progress_queue.put({
            "source": source,
            "step": f"{source} 采集失败: {str(e)}",
            "found": 0,
            "status": "error"
        })

        crawl_tasks[task_id]["error"] = f"{source}: {str(e)}"


def _run_all_crawls(task_id: str, headless: bool):
    """Run all source crawls sequentially in a background thread."""
    progress_queue = queue.Queue()
    crawl_tasks[task_id]["progress_queue"] = progress_queue

    sources = ['zcool', 'behance']
    for source in sources:
        _run_crawl_source(source, task_id, headless, progress_queue)

    # Final summary
    total_found = 0
    total_new = 0
    for src in sources:
        result = crawl_tasks[task_id].get("result", {})
        if isinstance(result, dict) and result.get("source") == src:
            total_found += result.get("found", 0)
            total_new += result.get("new_added", 0)

    progress_queue.put({
        "source": "all",
        "step": "采集完成",
        "found": total_found,
        "new_added": total_new,
        "status": "done"
    })

    crawl_tasks[task_id]["status"] = "done"


def _run_single_crawl(source: str, task_id: str, headless: bool):
    """Run a single source crawl in a background thread."""
    progress_queue = queue.Queue()
    crawl_tasks[task_id]["progress_queue"] = progress_queue

    _run_crawl_source(source, task_id, headless, progress_queue)

    crawl_tasks[task_id]["status"] = "done"


# ============ API Routes ============

@app.get("/api/projects")
def get_projects(
    source: Optional[str] = Query(None, description="Filter by source: zcool or behance"),
    author_type: Optional[str] = Query(None, description="Filter by author type: company or individual"),
    keyword: Optional[str] = Query(None, description="Search by title (fuzzy match)"),
    weeks: int = Query(1, ge=1, le=52, description="Number of weeks to look back (default 1 = this week)"),
    limit: int = Query(50, ge=1, le=200, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get projects with optional filters"""
    session = get_session()

    try:
        # Calculate week_start based on weeks parameter
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        if weeks > 1:
            week_start -= timedelta(weeks=weeks - 1)

        query = session.query(Project).filter(Project.published_at >= week_start)

        if source:
            query = query.filter(Project.source == source)

        if author_type:
            query = query.filter(Project.author_type == author_type)

        if keyword:
            query = query.filter(Project.title.like(f'%{keyword}%'))

        # Order by published date descending
        query = query.order_by(Project.published_at.desc())

        total = query.count()
        projects = query.offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "weeks": weeks,
            "week_start": week_start.isoformat(),
            "projects": [p.to_dict() for p in projects]
        }
    finally:
        session.close()


@app.get("/api/projects/stats")
def get_stats(weeks: int = Query(1, ge=1, le=52)):
    """Get statistics for projects within the given number of weeks"""
    session = get_session()

    try:
        # Get start of current week
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        # Go back (weeks - 1) additional weeks
        week_start = week_start - timedelta(weeks=weeks - 1)

        # Total this week
        total_this_week = session.query(Project).filter(
            Project.published_at >= week_start
        ).count()

        # By source
        zcool_count = session.query(Project).filter(
            Project.source == 'zcool',
            Project.published_at >= week_start
        ).count()

        behance_count = session.query(Project).filter(
            Project.source == 'behance',
            Project.published_at >= week_start
        ).count()

        # By author type
        company_count = session.query(Project).filter(
            Project.author_type == 'company',
            Project.published_at >= week_start
        ).count()

        individual_count = session.query(Project).filter(
            Project.author_type == 'individual',
            Project.published_at >= week_start
        ).count()

        return {
            "total_this_week": total_this_week,
            "by_source": {
                "zcool": zcool_count,
                "behance": behance_count
            },
            "by_author_type": {
                "company": company_count,
                "individual": individual_count
            },
            "week_start": week_start.isoformat()
        }
    finally:
        session.close()


@app.get("/api/logs")
def get_logs(limit: int = Query(10, ge=1, le=50)):
    """Get recent collection logs (including duration_seconds)"""
    session = get_session()

    try:
        logs = session.query(CollectionLog).order_by(
            CollectionLog.ran_at.desc()
        ).limit(limit).all()

        return {
            "logs": [log.to_dict() for log in logs]
        }
    finally:
        session.close()


@app.get("/api/status")
def get_status():
    """Get system status including last crawl time"""
    session = get_session()

    try:
        last_log = session.query(CollectionLog).order_by(
            CollectionLog.ran_at.desc()
        ).first()

        last_crawl = None
        if last_log:
            last_crawl = last_log.ran_at.isoformat() if last_log.ran_at else None

        return {
            "last_crawl": last_crawl,
            "next_scheduled": None,
            "version": "1.1.0"
        }
    finally:
        session.close()


# ============ SSE Progress Endpoint ============

@app.get("/api/crawl/progress")
def crawl_progress(task_id: str = Query(..., description="Task ID to monitor")):
    """SSE endpoint for crawl progress updates"""

    if task_id not in crawl_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    def event_generator():
        task = crawl_tasks[task_id]
        progress_queue = task.get("progress_queue")

        if progress_queue:
            # Drain existing messages first
            while not progress_queue.empty():
                try:
                    msg = progress_queue.get_nowait()
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    break

            # Wait for new messages with timeout
            while task["status"] not in ("done",):
                try:
                    msg = progress_queue.get(timeout=30)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    if msg.get("status") == "done":
                        break
                except queue.Empty:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
        else:
            # No queue available, just report current status
            yield f"data: {json.dumps({'source': 'all', 'step': '任务已结束', 'status': task['status']}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============ Async Crawl Endpoints ============

@app.post("/api/crawl/zcool")
def trigger_zcool_crawl(headless: bool = True):
    """Manually trigger ZCOOL crawl as async background task"""
    task_id = str(uuid.uuid4())[:8]
    crawl_tasks[task_id] = {
        "status": "started",
        "progress_queue": None,
        "result": None,
        "error": None
    }

    thread = threading.Thread(
        target=_run_single_crawl,
        args=('zcool', task_id, headless),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "started"}


@app.post("/api/crawl/behance")
def trigger_behance_crawl(headless: bool = True):
    """Manually trigger Behance crawl as async background task"""
    task_id = str(uuid.uuid4())[:8]
    crawl_tasks[task_id] = {
        "status": "started",
        "progress_queue": None,
        "result": None,
        "error": None
    }

    thread = threading.Thread(
        target=_run_single_crawl,
        args=('behance', task_id, headless),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "started"}


@app.post("/api/crawl/all")
def trigger_all_crawls(headless: bool = True):
    """Manually trigger all crawls as async background task"""
    task_id = str(uuid.uuid4())[:8]
    crawl_tasks[task_id] = {
        "status": "started",
        "progress_queue": None,
        "result": None,
        "error": None
    }

    thread = threading.Thread(
        target=_run_all_crawls,
        args=(task_id, headless),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "started"}


# Mount static files for dashboard
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard')
dashboard_path = os.path.join(dashboard_dir, 'index.html')


@app.get("/")
def root():
    """Root endpoint - serve dashboard if available"""
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {
        "message": "Design Monitor API",
        "version": "1.1.0",
        "docs": "/docs",
        "endpoints": [
            "/api/projects",
            "/api/projects/stats",
            "/api/logs",
            "/api/status",
            "/api/crawl/progress",
            "/api/crawl/zcool",
            "/api/crawl/behance",
            "/api/crawl/all"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
