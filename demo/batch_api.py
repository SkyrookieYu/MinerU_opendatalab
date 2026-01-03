#!/usr/bin/env python3
"""
MinerU Batch PDF Parsing API

Enterprise-grade PDF parsing API with:
- SQLite-based persistent task queue
- Configurable worker pool
- Priority-based task scheduling
- Automatic stale task recovery

Reference: mineru_tianshu project architecture

Usage:
    # Start with default settings (4 workers)
    python batch_api.py

    # Custom worker count
    python batch_api.py --workers 8

    # With uvicorn (production)
    uvicorn batch_api:app --host 0.0.0.0 --port 8000 --workers 1
"""

import json
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from task_db import TaskDB

# Import MinerU parsing function
from demo import parse_doc_by_physical_page


# =============================================================================
# Configuration
# =============================================================================

# Database and storage paths
DB_PATH = Path(__file__).parent / "mineru_batch.db"
TEMP_DIR = Path(tempfile.gettempdir()) / "mineru_batch_api"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Worker configuration
DEFAULT_WORKERS = 4
WORKER_POLL_INTERVAL = 0.5  # seconds

# Task configuration
STALE_TASK_TIMEOUT = 60  # minutes
CLEANUP_INTERVAL = 3600  # seconds (1 hour)


# =============================================================================
# Global State
# =============================================================================

db: Optional[TaskDB] = None
workers: list[threading.Thread] = []
worker_running = threading.Event()


# =============================================================================
# Response Models
# =============================================================================

class SubmitResponse(BaseModel):
    success: bool
    task_id: str
    status: str
    message: str = ""


class TaskResponse(BaseModel):
    task_id: str
    status: str
    file_name: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    worker_id: Optional[str] = None
    result: Optional[list] = None
    error: Optional[str] = None


class QueueStatsResponse(BaseModel):
    success: bool
    stats: dict
    total: int
    workers: int
    timestamp: str


# =============================================================================
# Worker Implementation
# =============================================================================

class Worker:
    """
    Background worker that continuously polls for and processes tasks.

    Each worker runs in a separate thread and uses atomic database
    operations to claim tasks, preventing duplicate processing.
    """

    def __init__(
        self,
        worker_id: str,
        db: TaskDB,
        poll_interval: float = WORKER_POLL_INTERVAL,
    ):
        self.worker_id = worker_id
        self.db = db
        self.poll_interval = poll_interval
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the worker thread"""
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Worker {self.worker_id} started")

    def stop(self):
        """Stop the worker thread"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"Worker {self.worker_id} stopped")

    def _loop(self):
        """Main worker loop"""
        idle_logged = False

        while self.running:
            try:
                # Try to claim a task
                task = self.db.get_next_task(self.worker_id)

                if task:
                    idle_logged = False
                    self._process_task(task)
                else:
                    if not idle_logged:
                        logger.debug(f"Worker {self.worker_id} idle, waiting for tasks...")
                        idle_logged = True
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.exception(f"Worker {self.worker_id} error: {e}")
                time.sleep(self.poll_interval)

    def _process_task(self, task: dict):
        """Process a single task"""
        task_id = task['task_id']
        file_name = task['file_name']
        file_path = task['file_path']

        logger.info(f"Worker {self.worker_id} processing: {task_id} - {file_name}")
        start_time = time.time()

        try:
            # Create output directory
            output_dir = TEMP_DIR / task_id / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Parse options
            options = json.loads(task.get('options', '{}'))

            # Execute parsing
            result = parse_doc_by_physical_page(
                pdf_path=Path(file_path),
                output_dir=str(output_dir),
                lang=options.get('lang', 'ch'),
                backend=task.get('backend', 'hybrid'),
                method=options.get('method', 'auto'),
                disable_image_extract=options.get('disable_image_extract', True),
            )

            # Update status to completed
            elapsed = time.time() - start_time
            self.db.update_task_status(
                task_id,
                status='completed',
                result=result,
                worker_id=self.worker_id,
            )
            logger.info(
                f"Worker {self.worker_id} completed: {task_id} - "
                f"{len(result)} pages in {elapsed:.1f}s"
            )

        except Exception as e:
            # Update status to failed
            self.db.update_task_status(
                task_id,
                status='failed',
                error_message=str(e),
                worker_id=self.worker_id,
            )
            logger.exception(f"Worker {self.worker_id} failed: {task_id} - {e}")


# =============================================================================
# Maintenance Tasks
# =============================================================================

def maintenance_loop():
    """
    Background maintenance loop for:
    - Resetting stale tasks
    - Cleaning up old task data
    """
    while worker_running.is_set():
        try:
            # Reset stale tasks (processing for > 60 minutes)
            reset_count = db.reset_stale_tasks(STALE_TASK_TIMEOUT)
            if reset_count > 0:
                logger.warning(f"Maintenance: Reset {reset_count} stale tasks")

            # Cleanup old completed/failed tasks (older than 7 days)
            cleanup_count = db.cleanup_old_tasks(days=7)
            if cleanup_count > 0:
                logger.info(f"Maintenance: Cleaned up {cleanup_count} old tasks")

        except Exception as e:
            logger.exception(f"Maintenance error: {e}")

        # Wait for next maintenance cycle
        for _ in range(CLEANUP_INTERVAL):
            if not worker_running.is_set():
                break
            time.sleep(1)


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="MinerU Batch PDF Parsing API",
    description="Enterprise-grade async PDF parsing with SQLite task queue",
    version="2.0.0",
)


def preload_mineru_model():
    """
    Preload MinerU model in main thread to avoid race condition.

    MinerU's model loading uses meta tensors that can't be safely loaded
    in multiple threads simultaneously. By loading once in main thread,
    subsequent worker threads can reuse the cached model.
    """
    logger.info("Preloading MinerU model (this may take a moment)...")
    try:
        # Import and trigger model initialization
        from mineru.backend.pipeline.pipeline_analyze import (
            batch_image_analyze,
            ModelSingleton,
        )
        from mineru.backend.pipeline.model_init import AtomModelSingleton
        from PIL import Image
        import numpy as np

        # Create a dummy image to trigger model loading
        dummy_image = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        dummy_batch = [(dummy_image, False, 'ch')]

        # This triggers the full model loading pipeline
        batch_image_analyze(dummy_batch, formula_enable=True, table_enable=True)

        logger.info("MinerU model preloaded successfully")
    except Exception as e:
        logger.warning(f"Model preload failed (will retry on first task): {e}")


@app.on_event("startup")
def startup_event():
    """Initialize database and start workers on startup"""
    global db, workers

    # Initialize database
    db = TaskDB(str(DB_PATH))
    logger.info(f"Database initialized: {DB_PATH}")

    # Preload model before starting workers to avoid race condition
    preload_mineru_model()

    # Get worker count from environment or use default
    num_workers = int(os.environ.get("MINERU_WORKERS", DEFAULT_WORKERS))

    # Start workers
    worker_running.set()
    for i in range(num_workers):
        worker = Worker(f"worker-{i+1}", db)
        worker.start()
        workers.append(worker._thread)

    logger.info(f"Started {num_workers} workers")

    # Start maintenance thread
    maintenance_thread = threading.Thread(target=maintenance_loop, daemon=True)
    maintenance_thread.start()


@app.on_event("shutdown")
def shutdown_event():
    """Stop workers and cleanup on shutdown"""
    logger.info("Shutting down...")

    # Signal workers to stop
    worker_running.clear()

    # Wait for workers to finish
    for worker_thread in workers:
        if worker_thread and worker_thread.is_alive():
            worker_thread.join(timeout=5)

    logger.info("Shutdown complete")


# =============================================================================
# API Endpoints
# =============================================================================

@app.post("/api/v1/parse", response_model=SubmitResponse, status_code=201)
async def submit_task(
    file: UploadFile = File(...),
    backend: str = Form("hybrid"),
    lang: str = Form("ch"),
    priority: int = Form(0),
    disable_image_extract: bool = Form(True),
):
    """
    Submit a PDF file for parsing.

    The file is saved to disk and a task is created in the queue.
    Workers will process tasks in priority order (higher = first).

    Args:
        file: PDF file to parse
        backend: Processing backend ("pipeline" or "vlm")
        lang: Language code (default: "ch")
        priority: Task priority (default: 0, higher = processed first)
        disable_image_extract: Whether to disable image extraction (default: True)

    Returns:
        task_id for tracking the parsing progress
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        # Read file content
        content = await file.read()

        # Create task directory and save file
        task_id = None  # Will be set after task creation
        temp_task_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        task_dir = TEMP_DIR / temp_task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        file_path = task_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        # Create task in database
        task_id = db.create_task(
            file_name=file.filename,
            file_path=str(file_path),
            backend=backend,
            options={
                "lang": lang,
                "disable_image_extract": disable_image_extract,
            },
            priority=priority,
        )

        # Rename task directory to actual task_id
        new_task_dir = TEMP_DIR / task_id
        task_dir.rename(new_task_dir)

        # Update file path in database
        new_file_path = new_task_dir / file.filename
        with db.get_cursor() as cursor:
            cursor.execute(
                'UPDATE tasks SET file_path = ? WHERE task_id = ?',
                (str(new_file_path), task_id)
            )

        logger.info(f"Task submitted: {task_id} - {file.filename} ({len(content)} bytes)")

        return SubmitResponse(
            success=True,
            task_id=task_id,
            status="pending",
            message="Task submitted successfully",
        )

    except Exception as e:
        logger.exception(f"Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")


@app.get("/api/v1/result/{task_id}")
async def get_result(task_id: str):
    """
    Get the parsing result for a task.

    This endpoint is compatible with the original api.py interface.

    Returns:
        - status: "pending", "processing", "completed", or "failed"
        - result: List of {pageNo, words} when completed
        - error: Error message when failed
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    status = task['status']

    if status in ('pending', 'processing'):
        return JSONResponse(
            status_code=202,
            content={
                "task_id": task_id,
                "status": status,
            }
        )

    if status == 'failed':
        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": "failed",
                "error": task.get('error_message', 'Unknown error'),
            }
        )

    if status == 'completed':
        # Parse result from JSON string
        result = json.loads(task['result']) if task['result'] else []

        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": "completed",
                "result": result,
            }
        )

    raise HTTPException(status_code=500, detail="Unknown task status")


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task_details(task_id: str):
    """
    Get detailed task information.

    Includes timing information, worker assignment, and result/error.
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Parse result if available
    result = None
    if task['result']:
        result = json.loads(task['result'])

    return TaskResponse(
        task_id=task_id,
        status=task['status'],
        file_name=task['file_name'],
        created_at=task['created_at'],
        started_at=task['started_at'],
        completed_at=task['completed_at'],
        worker_id=task['worker_id'],
        result=result,
        error=task.get('error_message'),
    )


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a pending task.

    Only tasks with status "pending" can be cancelled.
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task['status'] != 'pending':
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status '{task['status']}'"
        )

    success = db.cancel_pending_task(task_id)

    if success:
        # Cleanup task files
        task_dir = TEMP_DIR / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)

        return {"success": True, "message": "Task cancelled"}

    raise HTTPException(status_code=500, detail="Failed to cancel task")


@app.get("/api/v1/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """
    Get queue statistics.

    Returns counts for each task status and total.
    """
    stats = db.get_queue_stats()

    return QueueStatsResponse(
        success=True,
        stats=stats,
        total=sum(stats.values()),
        workers=len(workers),
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/v1/queue/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max tasks to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List tasks in the queue.

    Supports filtering by status and pagination.
    """
    tasks = db.get_all_tasks(status=status, limit=limit, offset=offset)

    # Parse results for completed tasks
    for task in tasks:
        if task.get('result'):
            task['result'] = json.loads(task['result'])

    return {
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
    }


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint (compatible with original api.py)"""
    stats = db.get_queue_stats()

    return {
        "status": "healthy",
        "pending_tasks": stats.get("pending", 0),
        "processing_tasks": stats.get("processing", 0),
        "workers": len(workers),
    }


@app.post("/api/v1/admin/reset-stale")
async def admin_reset_stale(timeout_minutes: int = Query(60, ge=1)):
    """
    Reset stale tasks (admin endpoint).

    Tasks stuck in 'processing' for longer than timeout are reset to 'pending'.
    """
    count = db.reset_stale_tasks(timeout_minutes)

    return {
        "success": True,
        "reset_count": count,
        "message": f"Reset {count} stale tasks (timeout: {timeout_minutes} minutes)",
    }


@app.post("/api/v1/admin/cleanup")
async def admin_cleanup(days: int = Query(7, ge=1)):
    """
    Cleanup old tasks (admin endpoint).

    Delete completed/failed tasks older than specified days.
    """
    count = db.cleanup_old_tasks(days)

    return {
        "success": True,
        "deleted_count": count,
        "message": f"Deleted {count} tasks older than {days} days",
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="MinerU Batch PDF Parsing API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Number of processing workers (default: {DEFAULT_WORKERS})")
    args = parser.parse_args()

    # Set worker count via environment variable
    os.environ["MINERU_WORKERS"] = str(args.workers)

    print(f"Starting MinerU Batch API on {args.host}:{args.port} with {args.workers} workers")
    uvicorn.run(app, host=args.host, port=args.port)
