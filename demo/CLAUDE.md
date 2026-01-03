# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 目錄說明

這是 MinerU 專案的 `demo/` 目錄，包含自訂功能擴展和測試腳本。此目錄基於 MinerU 2.7.0，新增了客戶端需要的特殊輸出格式。

## 快速開始

### 啟動 API 服務器

```bash
# 單一 API 服務器（簡易模式）
uvicorn api:app --host 0.0.0.0 --port 8000

# 批次 API 服務器（企業級，含 SQLite 任務隊列）
python batch_api.py --workers 4
```

### 使用 Python API

```python
from demo import parse_doc, parse_doc_by_physical_page
from pathlib import Path

# 標準解析（有語意合併）
parse_doc(
    [Path("document.pdf")],
    "output_dir",
    backend="pipeline",
    disable_image_extract=True,
    output_format="client_json"
)

# 物理頁面模式（無語意合併，嚴格對應 PDF 頁碼）
parse_doc_by_physical_page(
    pdf_path=Path("document.pdf"),
    output_dir="output_dir",
    disable_image_extract=True,
)
```

### 使用客戶端

```bash
# 簡易客戶端：測試 pdfs/ 目錄下所有 PDF
python simple_client.py --url http://localhost:8000

# 批次客戶端：並行處理多個 PDF
python batch_client.py --url http://localhost:8000 --max-concurrent 5
```

## 核心檔案

| 檔案 | 說明 |
|------|------|
| `demo.py` | 核心解析函數，包含 `parse_doc` 和 `parse_doc_by_physical_page` |
| `api.py` | FastAPI 異步 API 服務器（簡易模式） |
| `batch_api.py` | 企業級批次 API，含 SQLite 任務隊列和多 worker |
| `task_db.py` | SQLite 任務資料庫管理器 |
| `simple_client.py` | 簡易客戶端腳本（連接遠端 API） |
| `batch_client.py` | 批次客戶端（並行處理多個 PDF） |
| `md_to_plaintext.py` | Markdown 轉純文字工具 |
| `test_api.py` | API 測試腳本（含時間統計） |
| `test_production.py` | 產品線測試腳本 |

## 自訂功能

### 輸出格式選項 (`output_format` 參數)

| 格式 | 輸出檔案 | 說明 |
|------|----------|------|
| `"markdown"` | `.md` | 預設，標準 Markdown |
| `"plaintext"` | `.txt` | 純文字，移除所有格式 |
| `"client_json"` | `.json` | 分頁 JSON：`[{pageNo: 1, words: "..."}, ...]` |

### 版權限制 (`disable_image_extract=True`)

不提取圖片到 images 目錄，在 Markdown 中顯示 `[此內容因版權原因無法顯示]`。

### 物理頁面模式 vs 語意合併

| 函數 | 頁碼對應 | 跨頁合併 | 適用場景 |
|------|----------|----------|----------|
| `parse_doc` + `client_json` | 邏輯頁 | 會發生 | RAG chunking |
| `parse_doc_by_physical_page` | 物理頁 | 不會 | 頁面文字搜尋 |

**注意**：MinerU 預設會進行語意合併（跨頁內容合併到前一頁），這對 RAG 有利但會導致某些頁面為空。

## API 端點

### 簡易 API (`api.py`)

```
POST /api/v1/parse          # 提交 PDF，返回 task_id
GET  /api/v1/result/{id}    # 查詢結果（完成後自動刪除）
GET  /api/v1/health         # 健康檢查
```

### 批次 API (`batch_api.py`)

```
POST /api/v1/parse              # 提交 PDF，返回 task_id（支援優先級）
GET  /api/v1/result/{id}        # 查詢結果
GET  /api/v1/tasks/{id}         # 查詢任務詳情
DELETE /api/v1/tasks/{id}       # 取消待處理任務
GET  /api/v1/queue/stats        # 隊列統計
GET  /api/v1/queue/tasks        # 列出所有任務
GET  /api/v1/health             # 健康檢查
POST /api/v1/admin/reset-stale  # 重置卡住的任務
POST /api/v1/admin/cleanup      # 清理舊任務
```

回應格式：
```json
{
  "task_id": "xxx",
  "status": "completed",
  "result": [
    {"pageNo": 1, "words": "第一頁內容..."},
    {"pageNo": 2, "words": "第二頁內容..."}
  ]
}
```

## 測試

```bash
# 測試 API
python test_api.py --url http://localhost:8000

# 產品線測試
python test_production.py

# 任務資料庫 CLI
python task_db.py --stats
```

## 目錄結構

```
demo/
├── demo.py                 # 核心解析 API
├── api.py                  # FastAPI 服務器（簡易模式）
├── batch_api.py            # 批次 API 服務器
├── task_db.py              # SQLite 任務資料庫
├── simple_client.py        # 簡易客戶端
├── batch_client.py         # 批次客戶端
├── md_to_plaintext.py      # Markdown → 純文字
├── test_*.py               # 測試腳本
├── pdfs/                   # 測試用 PDF 檔案
└── output_*/               # 各種測試輸出目錄
```

## 環境設定

此專案使用 conda 環境：
```bash
conda activate mineru_2_7_0
```

主專案 MinerU 需先安裝（包含所有後端依賴）：
```bash
cd /home/cobra/projects/MinerU_opendatalab
pip install -e ".[all]"
```

> **注意**：MinerU 2.7.0 預設 backend 從 `pipeline` 改為 `hybrid`，建議安裝 `[all]` 以支援所有後端。

API 服務器額外需要：
```bash
pip install fastapi uvicorn python-multipart aiohttp
```
