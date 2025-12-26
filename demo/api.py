"""
MinerU Async PDF Parsing API

Provides asynchronous PDF parsing with task-based workflow:
1. POST /api/v1/parse - Submit PDF, get task_id
2. GET /api/v1/result/{task_id} - Get parsing result (auto-delete after download)

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000
    # or
    python api.py
"""

import os
import uuid
import shutil
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

# Import MinerU parsing function
from demo import parse_doc_by_physical_page


# =============================================================================
# Configuration
# =============================================================================

TEMP_DIR = Path(tempfile.gettempdir()) / "mineru_api"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Thread pool for background PDF processing
# Using 2 workers to avoid memory issues with large models
executor = ThreadPoolExecutor(max_workers=2)


# =============================================================================
# Models
# =============================================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskData:
    """Internal task data structure"""
    def __init__(self, task_id: str, pdf_path: Path):
        self.task_id = task_id
        self.status = TaskStatus.PENDING
        self.pdf_path = pdf_path
        self.output_dir = TEMP_DIR / task_id / "output"
        self.result: Optional[list] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now()

    def cleanup(self):
        """Remove all temporary files for this task"""
        task_dir = TEMP_DIR / self.task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
            logger.info(f"Cleaned up task directory: {task_dir}")


# Task storage (in-memory)
tasks: dict[str, TaskData] = {}


# =============================================================================
# Response Models
# =============================================================================

class ParseResponse(BaseModel):
    task_id: str
    status: str


class ResultResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[list] = None
    error: Optional[str] = None


# =============================================================================
# Background Task Execution
# =============================================================================

def execute_parsing(task_id: str):
    """Execute PDF parsing in background thread"""
    task = tasks.get(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return

    try:
        # Update status to processing
        task.status = TaskStatus.PROCESSING
        logger.info(f"Task {task_id}: Started processing {task.pdf_path}")

        # Create output directory
        task.output_dir.mkdir(parents=True, exist_ok=True)

        # Execute parsing (physical page mode)
        result = parse_doc_by_physical_page(
            pdf_path=task.pdf_path,
            output_dir=str(task.output_dir),
            lang="ch",
            backend="pipeline",
            method="auto",
            disable_image_extract=True,  # Default: no image extraction
        )

        # Store result
        task.result = result
        task.status = TaskStatus.COMPLETED
        logger.info(f"Task {task_id}: Completed successfully with {len(result)} pages")

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        logger.exception(f"Task {task_id}: Failed with error: {e}")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="MinerU PDF Parsing API",
    description="Async PDF to text extraction API using MinerU",
    version="1.0.0",
)


@app.post("/api/v1/parse", response_model=ParseResponse, status_code=201)
async def parse_pdf(file: UploadFile = File(...)):
    """
    Submit a PDF file for parsing.

    Returns a task_id that can be used to check the parsing status and retrieve results.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Create task directory and save PDF
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = task_dir / file.filename

    try:
        # Save uploaded file
        content = await file.read()
        with open(pdf_path, "wb") as f:
            f.write(content)

        logger.info(f"Task {task_id}: Saved PDF to {pdf_path} ({len(content)} bytes)")

        # Create task
        task = TaskData(task_id=task_id, pdf_path=pdf_path)
        tasks[task_id] = task

        # Submit to background executor
        executor.submit(execute_parsing, task_id)

        return ParseResponse(task_id=task_id, status=TaskStatus.PENDING)

    except Exception as e:
        # Cleanup on error
        shutil.rmtree(task_dir, ignore_errors=True)
        logger.exception(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")


@app.get("/api/v1/result/{task_id}")
async def get_result(task_id: str):
    """
    Get the parsing result for a task.

    - If processing: returns status "pending" or "processing"
    - If completed: returns result and automatically deletes task data
    - If failed: returns error message
    - If not found: returns 404
    """
    task = tasks.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatus.PENDING:
        return JSONResponse(
            status_code=202,
            content={"task_id": task_id, "status": "pending"}
        )

    if task.status == TaskStatus.PROCESSING:
        return JSONResponse(
            status_code=202,
            content={"task_id": task_id, "status": "processing"}
        )

    if task.status == TaskStatus.FAILED:
        # Cleanup failed task
        task.cleanup()
        del tasks[task_id]

        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": "failed",
                "error": task.error
            }
        )

    if task.status == TaskStatus.COMPLETED:
        result = task.result

        # Cleanup after successful retrieval
        task.cleanup()
        del tasks[task_id]

        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": "completed",
                "result": result
            }
        )

    # Should not reach here
    raise HTTPException(status_code=500, detail="Unknown task status")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "pending_tasks": len([t for t in tasks.values() if t.status == TaskStatus.PENDING]),
        "processing_tasks": len([t for t in tasks.values() if t.status == TaskStatus.PROCESSING]),
    }


@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down, cleaning up tasks...")
    executor.shutdown(wait=False)

    # Cleanup all task directories
    for task in tasks.values():
        task.cleanup()

    logger.info("Shutdown complete")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
