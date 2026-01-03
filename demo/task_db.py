"""
SQLite Task Database Manager

Provides thread-safe task queue management with atomic operations.
Reference: mineru_tianshu/task_db.py

Features:
- SQLite-based persistent storage
- Atomic task claiming (prevents duplicate processing)
- Priority-based ordering
- Stale task recovery
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


class TaskDB:
    """
    Thread-safe SQLite task database manager.

    Usage:
        db = TaskDB("tasks.db")
        task_id = db.create_task("document.pdf", "/path/to/file.pdf")
        task = db.get_next_task("worker-1")  # Atomic claim
        db.update_task_status(task_id, "completed", result_path="/output")
    """

    def __init__(self, db_path: str = "mineru_batch.db"):
        self.db_path = Path(db_path)
        self._init_db()
        logger.info(f"TaskDB initialized: {self.db_path}")

    def _init_db(self):
        """Initialize database schema"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    backend TEXT DEFAULT 'pipeline',
                    options TEXT,
                    result TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    worker_id TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            ''')

            # Create indexes for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tasks(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_id ON tasks(worker_id)')

    @contextmanager
    def get_cursor(self):
        """
        Context manager for database operations.

        Automatically commits on success, rollbacks on error.
        Each call creates a new connection (thread-safe).
        """
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # =========================================================================
    # Task CRUD Operations
    # =========================================================================

    def create_task(
        self,
        file_name: str,
        file_path: str,
        backend: str = "pipeline",
        options: Optional[dict] = None,
        priority: int = 0,
    ) -> str:
        """
        Create a new task in the queue.

        Args:
            file_name: Original file name
            file_path: Path to uploaded file
            backend: Processing backend ("pipeline" or "vlm")
            options: Additional options (JSON serializable)
            priority: Task priority (higher = processed first)

        Returns:
            task_id: Unique task identifier
        """
        task_id = str(uuid.uuid4())
        options_json = json.dumps(options) if options else "{}"

        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks (task_id, file_name, file_path, backend, options, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, file_name, file_path, backend, options_json, priority))

        logger.info(f"Task created: {task_id} - {file_name} (priority: {priority})")
        return task_id

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task details by ID"""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_task(self, worker_id: str, max_retries: int = 3) -> Optional[dict]:
        """
        Atomically claim the next pending task.

        Uses BEGIN IMMEDIATE to acquire write lock immediately,
        preventing multiple workers from claiming the same task.

        Args:
            worker_id: Identifier of the claiming worker
            max_retries: Number of retry attempts if task is claimed by another worker

        Returns:
            Task dict if available, None otherwise
        """
        for attempt in range(max_retries):
            try:
                with self.get_cursor() as cursor:
                    # Acquire write lock immediately
                    cursor.execute('BEGIN IMMEDIATE')

                    # Get highest priority pending task
                    cursor.execute('''
                        SELECT * FROM tasks
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    ''')
                    row = cursor.fetchone()

                    if not row:
                        return None

                    task = dict(row)
                    task_id = task['task_id']

                    # Atomically update status (only if still pending)
                    cursor.execute('''
                        UPDATE tasks
                        SET status = 'processing',
                            started_at = CURRENT_TIMESTAMP,
                            worker_id = ?
                        WHERE task_id = ? AND status = 'pending'
                    ''', (worker_id, task_id))

                    # Check if update was successful
                    if cursor.rowcount == 0:
                        # Task was claimed by another worker, retry
                        logger.debug(f"Task {task_id} claimed by another worker, retrying...")
                        continue

                    logger.info(f"Worker {worker_id} claimed task {task_id}")
                    return task

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    logger.warning(f"Database locked, retry {attempt + 1}/{max_retries}")
                    continue
                raise

        return None

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[list] = None,
        error_message: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        Update task status.

        Args:
            task_id: Task identifier
            status: New status ("pending", "processing", "completed", "failed")
            result: Parsing result (for completed tasks)
            error_message: Error message (for failed tasks)
            worker_id: Worker that processed the task

        Returns:
            True if update was successful
        """
        with self.get_cursor() as cursor:
            if status == "completed":
                cursor.execute('''
                    UPDATE tasks
                    SET status = ?,
                        result = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        worker_id = COALESCE(?, worker_id)
                    WHERE task_id = ?
                ''', (status, json.dumps(result) if result else None, worker_id, task_id))
            elif status == "failed":
                cursor.execute('''
                    UPDATE tasks
                    SET status = ?,
                        error_message = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        worker_id = COALESCE(?, worker_id)
                    WHERE task_id = ?
                ''', (status, error_message, worker_id, task_id))
            else:
                cursor.execute('''
                    UPDATE tasks
                    SET status = ?,
                        worker_id = COALESCE(?, worker_id)
                    WHERE task_id = ?
                ''', (status, worker_id, task_id))

            success = cursor.rowcount > 0

        if success:
            logger.info(f"Task {task_id} status updated to {status}")
        else:
            logger.warning(f"Task {task_id} not found for status update")

        return success

    def delete_task(self, task_id: str) -> bool:
        """Delete a task from the database"""
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # Queue Statistics
    # =========================================================================

    def get_queue_stats(self) -> dict:
        """
        Get queue statistics by status.

        Returns:
            {
                "pending": 5,
                "processing": 2,
                "completed": 10,
                "failed": 1
            }
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            ''')
            stats = {row['status']: row['count'] for row in cursor.fetchall()}

        return {
            "pending": stats.get("pending", 0),
            "processing": stats.get("processing", 0),
            "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0),
        }

    def get_all_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Get all tasks with optional status filter.

        Args:
            status: Filter by status (None = all)
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of task dicts
        """
        with self.get_cursor() as cursor:
            if status:
                cursor.execute('''
                    SELECT * FROM tasks
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', (status, limit, offset))
            else:
                cursor.execute('''
                    SELECT * FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))

            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Maintenance Operations
    # =========================================================================

    def reset_stale_tasks(self, timeout_minutes: int = 60) -> int:
        """
        Reset tasks stuck in 'processing' status.

        Tasks that have been processing for longer than timeout_minutes
        are reset to 'pending' for retry.

        Args:
            timeout_minutes: Processing timeout threshold

        Returns:
            Number of reset tasks
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE tasks
                SET status = 'pending',
                    worker_id = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing'
                AND started_at < datetime('now', '-' || ? || ' minutes')
            ''', (timeout_minutes,))
            reset_count = cursor.rowcount

        if reset_count > 0:
            logger.warning(f"Reset {reset_count} stale tasks (timeout: {timeout_minutes} min)")

        return reset_count

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Delete completed/failed tasks older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of deleted tasks
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM tasks
                WHERE status IN ('completed', 'failed')
                AND completed_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            deleted_count = cursor.rowcount

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old tasks (older than {days} days)")

        return deleted_count

    def cancel_pending_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Only pending tasks can be cancelled.

        Returns:
            True if task was cancelled
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE tasks
                SET status = 'failed',
                    error_message = 'Cancelled by user',
                    completed_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND status = 'pending'
            ''', (task_id,))
            return cursor.rowcount > 0


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Task Database CLI")
    parser.add_argument("--db", default="mineru_batch.db", help="Database path")
    parser.add_argument("--stats", action="store_true", help="Show queue stats")
    parser.add_argument("--list", action="store_true", help="List all tasks")
    parser.add_argument("--reset-stale", type=int, metavar="MINUTES",
                        help="Reset stale tasks older than MINUTES")
    parser.add_argument("--cleanup", type=int, metavar="DAYS",
                        help="Cleanup tasks older than DAYS")
    args = parser.parse_args()

    db = TaskDB(args.db)

    if args.stats:
        stats = db.get_queue_stats()
        print("Queue Statistics:")
        for status, count in stats.items():
            print(f"  {status}: {count}")
        print(f"  total: {sum(stats.values())}")

    elif args.list:
        tasks = db.get_all_tasks(limit=20)
        print(f"Recent Tasks (showing {len(tasks)}):")
        for t in tasks:
            print(f"  [{t['status']:10}] {t['task_id'][:8]}... - {t['file_name']}")

    elif args.reset_stale:
        count = db.reset_stale_tasks(args.reset_stale)
        print(f"Reset {count} stale tasks")

    elif args.cleanup:
        count = db.cleanup_old_tasks(args.cleanup)
        print(f"Cleaned up {count} old tasks")

    else:
        parser.print_help()
