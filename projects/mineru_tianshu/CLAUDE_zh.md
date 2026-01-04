# CLAUDE.md

此檔案為 Claude Code (claude.ai/code) 提供在此程式碼庫中工作的指引。

## 專案概述

MinerU Tianshu (天樞) 是建構於 MinerU 之上的企業級多 GPU 文件解析服務。結合 SQLite 任務佇列與 LitServe GPU 負載均衡，實現高效能文件處理。

**核心特性：**
- Worker 主動拉取任務（0.5 秒響應時間）
- 透過 CUDA_VISIBLE_DEVICES 實現多 GPU 隔離
- 雙解析器系統：MinerU（PDF/圖片）+ MarkItDown（Office/HTML/文字）
- SQLite 持久化的非同步任務處理

## 指令

### 安裝
```bash
# 啟用 conda 虛擬環境（伺服器端與客戶端都必須使用）
conda activate tianshu_2_7_0

cd projects/mineru_tianshu
pip install -r requirements.txt
```

> **重要**: 執行伺服器 (`start_all.py`) 或客戶端 (`client_example.py`) 之前，務必先啟用 `tianshu_2_7_0` conda 虛擬環境。

### 執行
```bash
# 啟動所有服務（建議方式）
python start_all.py

# 自訂配置
python start_all.py --workers-per-device 2 --devices 0,1

# CPU 模式（無 GPU）
python start_all.py --accelerator cpu

# 啟用可選的排程器進行監控
python start_all.py --enable-scheduler --monitor-interval 300
```

### 測試
```bash
# 執行客戶端範例
python client_example.py

# 測試特定情境
python client_example.py single    # 單一任務
python client_example.py batch     # 批次處理
python client_example.py priority  # 優先順序佇列
```

### API 存取
```bash
# Swagger UI 文件
open http://localhost:8000/docs

# 透過 curl 提交任務
curl -X POST http://localhost:8000/api/v1/tasks/submit \
  -F "file=@document.pdf" -F "lang=ch"

# 查詢任務狀態
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## 架構

```
客戶端請求 → FastAPI 伺服器（立即回傳 task_id）
                    ↓
              SQLite 任務佇列（並行安全的原子操作）
                    ↓
         LitServe Worker Pool（拉取模式 + GPU 自動負載均衡）
                    ↓
              MinerU / MarkItDown 解析
```

### 核心元件

| 檔案 | 用途 |
|------|------|
| `start_all.py` | 進入點 - 啟動 API 伺服器、workers、可選的排程器 |
| `api_server.py` | FastAPI 伺服器，支援任務 CRUD 及 MinIO 上傳 |
| `litserve_worker.py` | GPU workers，採用拉取式任務取得 |
| `task_db.py` | SQLite 操作，使用原子交易 |
| `task_scheduler.py` | 可選的監控/健康檢查元件 |
| `client_example.py` | API 使用者的參考實作 |

### 任務流程

1. **提交**：`POST /api/v1/tasks/submit` → 儲存檔案、建立待處理任務 → 回傳 `task_id`
2. **拉取**：Workers 持續輪詢 `task_db.get_next_pending_task()`（原子認領）
3. **處理**：Worker 導向 MinerU（PDF/圖片）或 MarkItDown（其他格式）
4. **完成**：儲存結果 → 狀態設為 `completed` → 檔案 7 天後自動清理

### 並行模型

- Workers 使用 `BEGIN IMMEDIATE` 交易防止重複處理任務
- 每個 worker 程序透過 `CUDA_VISIBLE_DEVICES` 隔離至單一 GPU
- LitServe 管理每個 worker 內的 GPU 記憶體與請求分配

## API 端點

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/v1/tasks/submit` | 提交檔案進行解析 |
| GET | `/api/v1/tasks/{task_id}` | 取得狀態（完成時自動回傳內容） |
| GET | `/api/v1/tasks/{task_id}/download` | 下載 ZIP 檔案（Markdown + 圖片） |
| GET | `/api/v1/queue/stats` | 佇列統計 |
| DELETE | `/api/v1/tasks/{task_id}` | 取消待處理任務 |
| POST | `/api/v1/admin/reset-stale` | 重置逾時任務 |
| POST | `/api/v1/admin/cleanup` | 手動觸發清理 |

## 環境變數

- `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET`：MinIO 圖片上傳配置
- `MINERU_VIRTUAL_VRAM_SIZE`：限制每個 worker 的 VRAM（GB）
- `CUDA_VISIBLE_DEVICES`：由 start_all.py 自動設定以實現 GPU 隔離

## 重要設計說明

- 當狀態為 `completed` 時，任務結果會自動在 API 回應中回傳（無需額外下載步驟）
- 結果檔案預設 7 天後清理，但資料庫記錄會保留
- 排程器為**可選元件** - workers 以拉取模式獨立運作
- 預設輪詢間隔為 0.5 秒，確保快速取得任務

## MinerU JSON 輸出格式

MinerU 解析 PDF 時會產生三種 JSON 檔案，代表不同處理階段：

```
PDF 輸入
    ↓
┌─────────────────────────────────────────────────────────────┐
│  ① model.json (原始模型輸出)                                 │
│     Layout Detection + OCR + Formula + Table 的原始偵測結果  │
└─────────────────────────────────────────────────────────────┘
    ↓  result_to_middle_json()
┌─────────────────────────────────────────────────────────────┐
│  ② middle.json (統一中間格式)                                │
│     跨 backend 的標準化格式，包含結構化內容                   │
└─────────────────────────────────────────────────────────────┘
    ↓  union_make()
┌─────────────────────────────────────────────────────────────┐
│  ③ content_list.json (最終結構化輸出)                        │
│     簡化的內容列表，適合 RAG/搜尋等下游應用                   │
└─────────────────────────────────────────────────────────────┘
    ↓
Markdown 輸出
```

| 檔案 | 階段 | 資料粒度 | 主要用途 |
|------|------|----------|----------|
| `xxx_model.json` | 原始 | 偵測框 + 座標 | 除錯、視覺化 |
| `xxx_middle.json` | 中間 | 行/片段級 | 後處理、跨頁合併 |
| `xxx_content_list.json` | 最終 | 區塊級 | RAG、搜尋、API 回傳 |

### content_list.json 類型說明

| type | 說明 |
|------|------|
| `text` | 正文內容 |
| `title` | 標題 |
| `table` | 表格 (含 HTML) |
| `image` | 圖片路徑 |
| `equation` | 公式 (LaTeX) |
| `discarded` | 頁首/頁尾/浮水印等被丟棄的內容 |
