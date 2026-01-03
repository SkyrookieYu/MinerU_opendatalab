# MinerU 自訂功能變更紀錄

## 版本資訊
- 基於分支: `mineru_2_7_0_custom`
- 移植日期: 2026-01-03
- 基於 MinerU 版本: 2.7.0 (從 2.6.7 移植自訂功能)
- 原始分支: `mineru_2_6_7_custom`

---

## 移植說明

本分支將 `mineru_2_6_7_custom` 分支的所有自訂功能移植到 MinerU 2.7.0 版本。2.7.0 版本的主要變化包括：

1. **新增 hybrid 後端**: 結合 pipeline 和 vlm 的優點
2. **OCR 升級到 PPOCRv5**: 支援 37+ 語言
3. **圖片載入重構**: `load_images_from_pdf` 返回格式變更為 `{'scale': float, 'img_pil': PIL.Image}`
4. **語言參數調整**: `lang` 改為可選參數，有自動偵測功能

---

## 功能總覽

| 功能 | 參數 | 說明 |
|------|------|------|
| Markdown 轉純文字 | - | `md_to_plaintext.py` 工具 |
| 純文字輸出 | `output_format="plaintext"` | 輸出 .txt 檔案 |
| 版權限制 | `disable_image_extract=True` | 不提取圖片，顯示版權提示 |
| 客戶端 JSON | `output_format="client_json"` | 分頁純文字 `{pageNo, words}` |
| 物理頁面模式 | `parse_doc_by_physical_page()` | 繞過語意合併，嚴格頁碼對應 |
| 異步 API | `api.py` | FastAPI HTTP 介面 |
| 批次 API | `batch_api.py` | 企業級 SQLite 任務佇列 |

---

## 功能一：Markdown 轉純文字工具

### 功能說明
MinerU 輸出的 Markdown 包含圖片連結、數學公式、HTML 表格等格式。此工具將 Markdown 轉換為純文字格式，適合後續文字處理和 RAG 應用。

### 新增檔案

#### `demo/md_to_plaintext.py`

```python
"""
Markdown to Plain Text Converter for MinerU output.
Removes all Markdown formatting and returns pure text content.
"""
import re
from pathlib import Path


def md_to_plaintext(md_content: str, keep_formulas: bool = False) -> str:
    """
    Convert MinerU Markdown output to plain text.

    Args:
        md_content: Markdown content string
        keep_formulas: If True, keep LaTeX formulas as-is; if False, remove them

    Returns:
        Plain text string
    """
    text = md_content

    # 1. Remove HTML tables
    text = re.sub(r'<table>.*?</table>', '', text, flags=re.DOTALL)

    # 2. Remove images: ![alt](path) or ![](path)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 2.1 Remove copyright notice for restricted images
    text = re.sub(r'\[此內容因版權原因無法顯示\]', '', text)

    # 3. Handle formulas
    if not keep_formulas:
        text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
        text = re.sub(r'\$[^$\n]+?\$', '', text)

    # 4-14. Various markdown cleanup...
    # (完整實作請見原始檔案)

    return text.strip()


def convert_file(input_path: str, output_path: str = None, keep_formulas: bool = False) -> str:
    """Convert a Markdown file to plain text."""
    # ...

def batch_convert(input_dir: str, output_dir: str = None, keep_formulas: bool = False) -> list:
    """Batch convert all .md files in a directory."""
    # ...
```

### 使用方式

```bash
# 命令列使用
python md_to_plaintext.py output/demo1/auto/demo1.md
python md_to_plaintext.py input.md -o output.txt
python md_to_plaintext.py output/ -o plaintext_output/
python md_to_plaintext.py demo1.md --keep-formulas
```

```python
# 程式碼中使用
from md_to_plaintext import md_to_plaintext, convert_file

plain_text = md_to_plaintext(markdown_string)
convert_file('demo1.md', 'demo1.txt')
```

---

## 功能二：版權限制功能 (disable_image_extract)

### 功能說明
針對有版權限制的 PDF 文件，提供選項禁止提取圖片到 images 目錄，並在 Markdown 和 JSON 輸出中顯示版權提示文字。

### 修改的檔案清單

| 檔案路徑 | 修改類型 | 說明 |
|----------|----------|------|
| `mineru/utils/cut_image.py` | 修改 | 新增版權限制標記常量和參數 |
| `mineru/backend/pipeline/model_json_to_middle_json.py` | 修改 | 傳遞 disable_image_extract 參數 |
| `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py` | 修改 | 處理版權限制，顯示提示文字 |
| `mineru/backend/vlm/vlm_middle_json_mkcontent.py` | 修改 | 處理版權限制，顯示提示文字 |
| `demo/demo.py` | 修改 | 新增 disable_image_extract 參數 |

### 核心修改詳情

#### 1. `mineru/utils/cut_image.py`

```python
# 版權限制標記常量 (新增)
COPYRIGHT_RESTRICTED_MARKER = "__COPYRIGHT_RESTRICTED__"


def cut_image_and_table(span, page_pil_img, page_img_md5, page_id, image_writer,
                        scale=2, disable_image_extract=False):  # 新增參數
    # ...
    if disable_image_extract:
        # 版權限制模式：不提取圖片，設定特殊標記
        span["image_path"] = COPYRIGHT_RESTRICTED_MARKER
    # ...
```

#### 2. `mineru/backend/pipeline/model_json_to_middle_json.py`

```python
# 函數簽名新增參數
def result_to_middle_json(model_list, images_list, pdf_doc, image_writer,
                          lang=None, ocr_enable=False, formula_enabled=True,
                          disable_image_extract=False):  # 新增
    # ...
```

#### 3. `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py`

```python
from mineru.utils.cut_image import COPYRIGHT_RESTRICTED_MARKER

COPYRIGHT_NOTICE = "此內容因版權原因無法顯示"

# 在 make_blocks_to_markdown 函數中處理版權限制
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_text += f"[{COPYRIGHT_NOTICE}]"
elif img_path:
    para_text += f"![]({img_buket_path}/{img_path})"
```

### 使用方式

```python
from demo import parse_doc

parse_doc(
    doc_path_list,
    output_dir,
    backend="pipeline",
    disable_image_extract=True  # 啟用版權限制
)
```

### 輸出效果

#### Markdown 輸出
```markdown
# 啟用前
![](images/xxxx.jpg)
Fig. 1. Description...

# 啟用後
[此內容因版權原因無法顯示]
Fig. 1. Description...
```

#### content_list.json 輸出
```json
{
    "type": "image",
    "img_path": "",
    "copyright_restricted": true,
    "copyright_notice": "此內容因版權原因無法顯示"
}
```

---

## 功能三：統一輸出介面 (output_format)

### 功能說明
透過 `output_format` 參數統一控制輸出格式，支援 Markdown、純文字、客戶端 JSON 三種格式。

### 支援的格式

| 格式值 | 輸出檔案 | 說明 |
|--------|----------|------|
| `"markdown"` | `.md` | 預設，標準 Markdown |
| `"plaintext"` | `.txt` | 純文字，移除所有格式 |
| `"client_json"` | `.json` | 分頁 JSON：`[{pageNo, words}, ...]` |

### 使用方式

```python
from demo import parse_doc

# Markdown 輸出 (預設)
parse_doc(doc_path_list, output_dir)

# 純文字輸出
parse_doc(doc_path_list, output_dir, output_format="plaintext")

# 客戶端 JSON 輸出
parse_doc(doc_path_list, output_dir, output_format="client_json")

# 組合使用：版權限制 + JSON 輸出
parse_doc(
    doc_path_list,
    output_dir,
    disable_image_extract=True,
    output_format="client_json"
)
```

---

## 功能四：客戶端 JSON 輸出格式 (client_json)

### 功能說明
根據客戶端需求，提供分頁的純文字 JSON 輸出格式。

### 輸出格式

```json
[
  {"pageNo": 1, "words": "第一頁的純文字內容..."},
  {"pageNo": 2, "words": "第二頁的純文字內容..."},
  ...
]
```

### 核心實作

#### `demo/demo.py` - `make_client_json` 函數

```python
def make_client_json(pdf_info, make_func, f_make_md_mode, image_dir):
    """
    Generate client-requested JSON format with page-by-page plain text.
    """
    result = []
    for page_idx, page_info in enumerate(pdf_info):
        single_page_info = [page_info]
        page_md_content = make_func(single_page_info, f_make_md_mode, image_dir)

        if isinstance(page_md_content, list):
            page_md_str = '\n'.join(page_md_content)
        else:
            page_md_str = str(page_md_content)

        page_plaintext = md_to_plaintext(page_md_str)
        result.append({
            "pageNo": page_idx + 1,
            "words": page_plaintext
        })
    return result
```

### 輸出範例

處理 `small_ocr.pdf` (8 頁) 的輸出：

```json
[
  {
    "pageNo": 1,
    "words": "史的事情。(3)为有用物的量找到社会尺度，也是这样..."
  },
  {
    "pageNo": 2,
    "words": "某种特殊的商品，例如一夸特小麦..."
  }
]
```

---

## 功能五：物理頁面模式 (parse_doc_by_physical_page)

### 功能說明

MinerU 預設會進行**語意合併**（跨頁內容合併到前一頁），這對 RAG chunking 有利，但可能導致某些物理頁面在輸出中為空。

物理頁面模式逐頁解析 PDF，繞過語意合併機制，確保每個物理頁的內容獨立輸出。

### 使用場景對比

| 模式 | 頁碼對應 | 跨頁合併 | 適用場景 |
|------|----------|----------|----------|
| `parse_doc` + `client_json` | 邏輯頁 | 會發生 | RAG chunking |
| `parse_doc_by_physical_page` | 物理頁 | 不會 | 頁面文字搜尋、PDF 頁碼對照 |

### 新增函數

```python
def parse_doc_by_physical_page(
    pdf_path: Path,
    output_dir,
    lang="ch",
    backend="pipeline",
    method="auto",
    server_url=None,
    disable_image_extract=False,
) -> list:
    """
    Parse PDF page by page, bypassing MinerU's semantic merging mechanism.

    Returns:
        List of dictionaries: [{"pageNo": 1, "words": "..."}, ...]
    """
```

### 使用方式

```python
from demo import parse_doc_by_physical_page
from pathlib import Path

result = parse_doc_by_physical_page(
    pdf_path=Path("document.pdf"),
    output_dir="output_dir",
    backend="pipeline",
    disable_image_extract=True,
)

# 輸出檔案: output_dir/document_physical_pages.json
```

### 輸出範例

```json
[
  {"pageNo": 1, "words": "第一頁的純文字內容..."},
  {"pageNo": 2, "words": "第二頁的純文字內容..."},
  {"pageNo": 3, "words": "第三頁的純文字內容...（不會為空）"}
]
```

---

## 功能六：異步 PDF 解析 API (FastAPI)

### 功能說明

提供 RESTful API 介面，採用異步任務模式處理 PDF 解析請求。

### 架構流程

```
Client                     API Server              Background Worker
  │                            │                          │
  │  POST /api/v1/parse        │                          │
  │  (上傳 PDF)                │                          │
  ├───────────────────────────>│                          │
  │                            │  生成 task_id            │
  │                            ├─────────────────────────>│
  │  返回 {"task_id": "xxx"}   │                          │
  │<───────────────────────────┤                          │
  │                            │                          │ 處理 PDF
  │  GET /result/{task_id}     │                          │
  ├───────────────────────────>│                          │
  │  返回 {"status": "processing"}                        │
  │<───────────────────────────┤                          │
  │                            │                          │ 完成
  │  GET /result/{task_id}     │                          │
  ├───────────────────────────>│                          │
  │  返回結果 + 自動清理        │                          │
  │<───────────────────────────┤                          │
```

### 新增檔案

#### `demo/api.py`

```python
"""
MinerU Async PDF Parsing API

Endpoints:
    POST /api/v1/parse          - Submit PDF for parsing
    GET  /api/v1/result/{id}    - Get parsing result
    GET  /api/v1/health         - Health check
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from concurrent.futures import ThreadPoolExecutor
import uuid

app = FastAPI(title="MinerU PDF Parsing API")
executor = ThreadPoolExecutor(max_workers=2)
tasks = {}  # 記憶體任務儲存


@app.post("/api/v1/parse", status_code=201)
async def parse_pdf(file: UploadFile = File(...)):
    """Submit PDF for async parsing."""
    task_id = str(uuid.uuid4())
    # 提交到背景執行緒處理
    executor.submit(process_pdf, task_id, pdf_bytes)
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/v1/result/{task_id}")
async def get_result(task_id: str):
    """Get parsing result by task ID."""
    # 返回結果後自動刪除
    # ...


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

### 使用方式

```bash
# 啟動 API 服務器
cd demo
uvicorn api:app --host 0.0.0.0 --port 8000

# 健康檢查
curl http://localhost:8000/api/v1/health

# 提交 PDF
curl -X POST http://localhost:8000/api/v1/parse \
    -F "file=@document.pdf"
# 返回: {"task_id": "xxx-xxx-xxx", "status": "pending"}

# 查詢結果
curl http://localhost:8000/api/v1/result/{task_id}
# 返回: {"task_id": "xxx", "status": "completed", "result": [...]}
```

### 回應格式

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": [
    {"pageNo": 1, "words": "第一頁內容..."},
    {"pageNo": 2, "words": "第二頁內容..."}
  ]
}
```

---

## 功能七：企業級批次 API (batch_api.py + task_db.py)

### 功能說明

提供基於 SQLite 的持久化任務佇列，支援多 Worker、優先級排序、失敗重試等企業級功能。

### 架構設計

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────>│  FastAPI     │────>│   SQLite DB     │
│             │     │  (batch_api) │     │   (task_db)     │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                      │
                    ┌──────┴──────┐               │
                    │   Worker    │<──────────────┘
                    │   Pool      │  (原子任務認領)
                    └─────────────┘
```

### 新增檔案

#### `demo/task_db.py`

```python
"""
SQLite-based persistent task queue with atomic operations.
"""
import sqlite3
from threading import Lock


class TaskDB:
    def __init__(self, db_path: str = "mineru_batch.db"):
        self.db_path = db_path
        self._lock = Lock()
        self._init_db()

    def create_task(self, pdf_name: str, pdf_bytes: bytes, priority: int = 0) -> str:
        """Create a new task and return task_id."""
        # ...

    def get_next_task(self, worker_id: str, max_retries: int = 3) -> Optional[dict]:
        """
        Atomically claim the next pending task.
        Uses BEGIN IMMEDIATE for write lock.
        """
        cursor.execute('BEGIN IMMEDIATE')
        cursor.execute('''
            SELECT * FROM tasks
            WHERE status = 'pending' AND retry_count < ?
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        ''', (max_retries,))
        # ...

    def update_task_status(self, task_id: str, status: str,
                          result: dict = None, error: str = None):
        """Update task status with result or error."""
        # ...
```

#### `demo/batch_api.py`

```python
"""
Enterprise-grade batch PDF parsing API with SQLite task queue.
"""
from fastapi import FastAPI
from task_db import TaskDB

app = FastAPI(title="MinerU Batch API")
task_db = TaskDB()


@app.post("/api/v1/parse")
async def submit_task(file: UploadFile, priority: int = 0):
    """Submit PDF with optional priority."""
    task_id = task_db.create_task(file.filename, pdf_bytes, priority)
    return {"task_id": task_id}


@app.get("/api/v1/queue/stats")
async def queue_stats():
    """Get queue statistics."""
    return task_db.get_stats()


@app.post("/api/v1/admin/reset-stale")
async def reset_stale_tasks(timeout_minutes: int = 30):
    """Reset stale processing tasks."""
    # ...
```

### 資料庫結構

```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    pdf_name TEXT NOT NULL,
    pdf_data BLOB NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending/processing/completed/failed
    priority INTEGER DEFAULT 0,
    worker_id TEXT,
    retry_count INTEGER DEFAULT 0,
    result TEXT,  -- JSON string
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 使用方式

```bash
# 啟動批次 API
uvicorn batch_api:app --host 0.0.0.0 --port 8000

# 提交高優先級任務
curl -X POST http://localhost:8000/api/v1/parse \
    -F "file=@urgent.pdf" \
    -F "priority=10"

# 查看佇列狀態
curl http://localhost:8000/api/v1/queue/stats
# 返回: {"pending": 5, "processing": 2, "completed": 100, "failed": 1}

# 重設卡住的任務
curl -X POST http://localhost:8000/api/v1/admin/reset-stale?timeout_minutes=30
```

---

## 客戶端腳本

### `demo/simple_client.py`

簡易客戶端，用於快速測試 API。

```bash
# 測試 pdfs/ 目錄下所有 PDF
python simple_client.py

# 指定單一 PDF
python simple_client.py --pdf document.pdf

# 指定 API 伺服器
python simple_client.py --url http://192.168.1.100:8000
```

### `demo/batch_client.py`

異步批次客戶端，支援並發處理。

```bash
# 批次處理目錄
python batch_client.py --pdf-dir ./documents --max-concurrent 5

# 使用批次 API
python batch_client.py --pdf-dir ./documents --use-batch-api
```

---

## 測試腳本

### `demo/test_api.py`

API 測試腳本，包含時間統計。

```bash
python test_api.py --url http://localhost:8000
python test_api.py --pdf document.pdf
```

### `demo/test_production.py`

產品線測試腳本，測試所有 4 個 PDF 檔案。

```bash
python test_production.py
```

### `demo/test_plaintext.py`

純文字轉換測試腳本。

```bash
python test_plaintext.py
```

---

## 檔案變更總覽

### 新增檔案

```
demo/
├── md_to_plaintext.py      # Markdown 轉純文字工具
├── api.py                  # FastAPI 異步 API
├── batch_api.py            # 企業級批次 API
├── task_db.py              # SQLite 任務資料庫
├── simple_client.py        # 簡易客戶端
├── batch_client.py         # 異步批次客戶端
├── test_api.py             # API 測試腳本
├── test_production.py      # 產品線測試
├── test_plaintext.py       # 純文字測試
├── CLAUDE.md               # 專案文件
└── CHANGELOG_CUSTOM.md     # 本變更紀錄
```

### 修改檔案

```
demo/
└── demo.py                 # 新增自訂功能參數和函數

mineru/
├── utils/
│   └── cut_image.py        # 新增版權限制標記
│
└── backend/
    ├── pipeline/
    │   ├── model_json_to_middle_json.py      # 傳遞 disable_image_extract
    │   └── pipeline_middle_json_mkcontent.py # 處理版權提示
    │
    └── vlm/
        └── vlm_middle_json_mkcontent.py      # 處理版權提示
```

---

## 安裝與設定

### 環境需求

```bash
# 使用 conda 環境
conda activate mineru_2_7_0

# 從原始碼安裝（必須，才能使用自訂功能）
cd /home/cobra/projects/MinerU_opendatalab
pip install -e ".[pipeline]"

# API 服務器額外需要
pip install fastapi uvicorn python-multipart aiohttp
```

### 快速開始

```python
from demo import parse_doc, parse_doc_by_physical_page
from pathlib import Path

# 標準解析（推薦用於 RAG）
parse_doc(
    [Path("document.pdf")],
    "output_dir",
    backend="pipeline",
    disable_image_extract=True,
    output_format="client_json"
)

# 物理頁面模式（用於頁面搜尋）
parse_doc_by_physical_page(
    pdf_path=Path("document.pdf"),
    output_dir="output_dir",
    disable_image_extract=True,
)
```

---

## 注意事項

1. **必須從原始碼安裝**: 自訂功能修改了 mineru 核心程式碼，必須執行 `pip install -e ".[pipeline]"` 才能生效。

2. **語意合併行為**: MinerU 預設會合併跨頁內容，使用 `parse_doc_by_physical_page` 可繞過此行為。

3. **後端支援**:
   - `pipeline`: 完整支援所有自訂功能
   - `vlm`: 部分支援（版權限制、輸出格式）
   - `hybrid`: 繼承 pipeline 的功能

4. **API 模型載入**: 首次請求會載入模型（約 10 秒），後續請求使用 singleton 模式。

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 2.7.0-custom | 2026-01-03 | 移植到 MinerU 2.7.0 |
| 2.6.7-custom | 2025-12-27 | 原始自訂功能實作 |

---

## 聯絡資訊

如有問題，請參考：
- 專案 CLAUDE.md: `/home/cobra/projects/MinerU_opendatalab/CLAUDE.md`
- Demo CLAUDE.md: `/home/cobra/projects/MinerU_opendatalab/demo/CLAUDE.md`
