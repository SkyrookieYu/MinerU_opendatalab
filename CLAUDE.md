# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MinerU is a PDF-to-Markdown conversion tool developed by OpenDataLab. It supports two backends:
- **pipeline**: Traditional ML pipeline using layout detection, OCR, formula recognition, and table parsing
- **vlm**: Vision-Language Model backend using the MinerU2.5 model (1.2B parameters)

## 環境設定

此專案使用 conda 環境：
```bash
conda activate mineru_2_6_7
```

> **注意**: `projects/mineru_tianshu` 子專案使用獨立的 `mineru_tianshu` conda 環境。

## Commands

### Installation
```bash
# Development installation
pip install -e .

# With specific backends
pip install -e ".[pipeline]"     # Traditional ML pipeline
pip install -e ".[vlm]"          # VLM with transformers
pip install -e ".[core]"         # All backends
pip install -e ".[all]"          # Everything including vllm/lmdeploy
```

### Running
```bash
# CLI usage
mineru -p input.pdf -o output_dir -b pipeline
mineru -p input.pdf -o output_dir -b vlm-transformers

# Download models
mineru-models-download

# Start API server
mineru-api

# Start Gradio UI
mineru-gradio

# VLM inference servers
mineru-vllm-server
mineru-lmdeploy-server
```

### Testing
```bash
# Run all tests with coverage
pytest tests/unittest/test_e2e.py -s --cov=mineru --cov-report html

# Run single test
pytest tests/unittest/test_e2e.py::test_function_name -s
```

## Architecture

### Core Processing Flow
1. **Input**: PDF bytes → `load_images_from_pdf()` → PIL Images
2. **Analysis**: Images → Backend (pipeline/vlm) → `model_json` (raw detection)
3. **Conversion**: `model_json` → `result_to_middle_json()` → `middle_json` (unified format)
4. **Output**: `middle_json` → `union_make()` → Markdown/JSON/content_list

### Key Source Locations
- `mineru/backend/pipeline/pipeline_analyze.py` - Pipeline backend entry point
- `mineru/backend/pipeline/model_json_to_middle_json.py` - Model output conversion
- `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py` - Markdown/content generation
- `mineru/backend/vlm/vlm_analyze.py` - VLM backend entry point
- `mineru/cli/fast_api.py` - Official API server
- `mineru/cli/client.py` - CLI main entry point

### Backend Selection
- `pipeline`: General-purpose, works offline, supports 37+ languages via PPOCRv5
- `vlm-transformers`: Slower but accurate, uses transformers
- `vlm-vllm-engine`: Fastest, requires vllm (Linux)
- `vlm-lmdeploy-engine`: Fast, requires lmdeploy (Windows)
- `vlm-http-client`: Connect to external OpenAI-compatible servers

### Output Formats
- `middle_json`: Intermediate unified format (cross-backend compatible)
- `content_list.json`: Structured content with bbox coordinates
- `*.md`: Markdown with images/tables/formulas
- Layout/span visualization images

## Subprojects

### `projects/mineru_tianshu/`
Enterprise-grade multi-GPU document parsing service with:
- SQLite task queue + LitServe GPU load balancing
- Worker-based architecture with 0.5s response time
- RESTful API with async processing
- Supports both MinerU (PDF/images) and MarkItDown (Office/HTML)

```bash
cd projects/mineru_tianshu
pip install -r requirements.txt
python start_all.py --workers-per-device 2 --devices 0,1
```

### `projects/mcp/`
Model Context Protocol server for LLM integration.

## Custom Branch Features (mineru_2_6_7_custom)

This branch adds custom features for specific client needs. See `demo/CHANGELOG_CUSTOM.md` for full details.

| Feature | Parameter | Description |
|---------|-----------|-------------|
| Plaintext output | `output_format="plaintext"` | Strips all Markdown formatting, outputs `.txt` |
| Copyright restriction | `disable_image_extract=True` | Prevents image extraction, shows copyright notice |
| Client JSON | `output_format="client_json"` | Page-by-page `{pageNo, words}` format |
| Physical page mode | `parse_doc_by_physical_page()` | Bypasses semantic merging for strict page correspondence |

```python
from demo.demo import parse_doc
parse_doc(
    doc_path_list,
    output_dir,
    backend="pipeline",
    disable_image_extract=True,
    output_format="client_json"
)
```

### Custom API Server
```bash
cd demo
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Environment Variables

- `MINERU_MIN_BATCH_INFERENCE_SIZE`: Batch size for inference (default: 384)
- `MINERU_PDF_RENDER_TIMEOUT`: PDF rendering timeout in seconds (default: 300)
- `MINERU_FORMULA_CH_SUPPORT`: Enable Chinese formula support (experimental)
- `MINERU_TABLE_MERGE_ENABLE`: Enable cross-page table merging (default: 1)
- `MINERU_API_MAX_CONCURRENT_REQUESTS`: Max concurrent API requests

## Key Design Notes

- MinerU performs **semantic page merging** - cross-page content (e.g., references spanning pages) is merged into the preceding page. This is intentional for better RAG chunking.
- The `middle_json` format is the canonical intermediate representation, enabling cross-backend compatibility.
- Models are downloaded automatically on first use via `auto_download_and_get_model_root_path()`.
- Python version requirement: 3.10-3.13
