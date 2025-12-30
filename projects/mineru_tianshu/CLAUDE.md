# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MinerU Tianshu (天枢) is an enterprise-grade multi-GPU document parsing service built on top of MinerU. It combines SQLite task queues with LitServe GPU load balancing for high-performance document processing.

**Key Features:**
- Worker-initiated task pulling (0.5s response time)
- Multi-GPU isolation via CUDA_VISIBLE_DEVICES
- Dual parser system: MinerU (PDF/images) + MarkItDown (Office/HTML/text)
- Async task processing with SQLite persistence

## Commands

### Installation
```bash
# Activate the conda environment (REQUIRED for both server and client)
conda activate mineru_tianshu

cd projects/mineru_tianshu
pip install -r requirements.txt
```

> **Important**: Always activate the `mineru_tianshu` conda environment before running the server (`start_all.py`) or client (`client_example.py`).

### Running
```bash
# Start all services (recommended)
python start_all.py

# Custom configuration
python start_all.py --workers-per-device 2 --devices 0,1

# CPU mode (no GPU)
python start_all.py --accelerator cpu

# Enable optional scheduler for monitoring
python start_all.py --enable-scheduler --monitor-interval 300
```

### Testing
```bash
# Run client example
python client_example.py

# Test specific scenarios
python client_example.py single    # Single task
python client_example.py batch     # Batch processing
python client_example.py priority  # Priority queue
```

### API Access
```bash
# Swagger UI documentation
open http://localhost:8000/docs

# Submit task via curl
curl -X POST http://localhost:8000/api/v1/tasks/submit \
  -F "file=@document.pdf" -F "lang=ch"

# Query task status
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## Architecture

```
Client Request → FastAPI Server (immediate task_id return)
                       ↓
               SQLite Task Queue (concurrent-safe atomic ops)
                       ↓
          LitServe Worker Pool (pull-based + GPU auto-balancing)
                       ↓
               MinerU / MarkItDown Parsing
```

### Core Components

| File | Purpose |
|------|---------|
| `start_all.py` | Entry point - spawns API server, workers, optional scheduler |
| `api_server.py` | FastAPI server with task CRUD, MinIO upload support |
| `litserve_worker.py` | GPU workers with pull-based task acquisition |
| `task_db.py` | SQLite operations with atomic transactions |
| `task_scheduler.py` | Optional monitoring/health-check component |
| `client_example.py` | Reference implementation for API consumers |

### Task Flow

1. **Submit**: `POST /api/v1/tasks/submit` → stores file, creates pending task → returns `task_id`
2. **Pull**: Workers continuously poll `task_db.get_next_pending_task()` (atomic claim)
3. **Process**: Worker routes to MinerU (PDF/images) or MarkItDown (others)
4. **Complete**: Result stored → status set to `completed` → files auto-cleaned after 7 days

### Concurrency Model

- Workers use `BEGIN IMMEDIATE` transactions to prevent duplicate task processing
- Each worker process is isolated to a single GPU via `CUDA_VISIBLE_DEVICES`
- LitServe manages GPU memory and request distribution within each worker

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tasks/submit` | Submit file for parsing |
| GET | `/api/v1/tasks/{task_id}` | Get status (auto-returns content when complete) |
| GET | `/api/v1/tasks/{task_id}/download` | Download ZIP file (Markdown + images) |
| GET | `/api/v1/queue/stats` | Queue statistics |
| DELETE | `/api/v1/tasks/{task_id}` | Cancel pending task |
| POST | `/api/v1/admin/reset-stale` | Reset timed-out tasks |
| POST | `/api/v1/admin/cleanup` | Manual cleanup trigger |

## Environment Variables

- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`: MinIO configuration for image uploads
- `MINERU_VIRTUAL_VRAM_SIZE`: Limit VRAM per worker (GB)
- `CUDA_VISIBLE_DEVICES`: Auto-set by start_all.py for GPU isolation

## Key Design Notes

- Task results are auto-returned in API response when status is `completed` (no separate download step)
- Result files are cleaned after 7 days by default but database records persist
- The scheduler is **optional** - workers operate independently with pull-based model
- Default poll interval is 0.5s for fast task pickup