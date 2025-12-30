# MinerU Tianshu 測試報告

**測試日期**: 2025-12-28
**測試環境**: WSL2 Linux, CUDA GPU
**虛擬環境**: mineru_tianshu (conda)

---

## 測試概要

使用 4 個 PDF 檔案測試天樞服務的完整流程，包括：
- API 伺服器啟動
- Worker 任務處理
- 結果查詢與回傳

---

## 測試檔案

| 檔案 | 大小 | 來源 |
|------|------|------|
| demo1.pdf | 337 KB | demo/pdfs/ |
| demo2.pdf | 1.8 MB | demo/pdfs/ |
| demo3.pdf | 433 KB | demo/pdfs/ |
| small_ocr.pdf | 454 KB | demo/pdfs/ |

---

## 測試結果

### 任務處理結果

| 檔案 | Task ID | 狀態 | Markdown 長度 | 圖片數 |
|------|---------|------|---------------|--------|
| demo1.pdf | 2993811d-7e3a-41d2-9d9a-ef4d4557c319 | completed | 51,128 字元 | 17 張 |
| demo2.pdf | 0a4b5a75-30ce-4c6a-9b10-5103ddd0e9b1 | completed | 31,131 字元 | 16 張 |
| demo3.pdf | b2be063b-3539-4468-bf80-b02d32cf905a | completed | 45,875 字元 | 18 張 |
| small_ocr.pdf | 009547dd-df23-451e-9cb4-06649fbd6d20 | completed | 4,470 字元 | 0 張 |
| **合計** | | | **132,604 字元** | **51 張** |

### 輸出位置

```
/tmp/mineru_tianshu_output/
├── 009547dd-df23-451e-9cb4-06649fbd6d20/small_ocr/auto/
├── 0a4b5a75-30ce-4c6a-9b10-5103ddd0e9b1/demo2/auto/
├── 2993811d-7e3a-41d2-9d9a-ef4d4557c319/demo1/auto/
└── b2be063b-3539-4468-bf80-b02d32cf905a/demo3/auto/
```

每個任務目錄包含：
- `*.md` - Markdown 輸出
- `*_content_list.json` - 結構化內容
- `*_middle.json` - 中間處理結果
- `*_model.json` - 模型輸出
- `*_layout.pdf` - 版面分析視覺化
- `*_span.pdf` - 文字區塊視覺化
- `images/` - 提取的圖片 (*.jpg)

---

## 發現的問題

### 問題 1: 圖片無法回傳給遠端 Client

**現象**:
- API 回傳的 Markdown 包含圖片路徑如 `![](images/abc123.jpg)`
- 但圖片實際儲存在伺服器的 `/tmp/mineru_tianshu_output/` 目錄
- 遠端 Client 無法存取這些圖片

**影響**:
- 回傳的 Markdown 檔案無法直接使用（圖片全部顯示不出來）
- 對於需要完整文件的使用場景，功能不完整

**API 回傳範例**:
```json
{
  "status": "completed",
  "data": {
    "content": "# Title\n\n![](images/abc123.jpg)\n\nText...",
    "has_images": true,
    "images_uploaded": false
  }
}
```

### 問題 2: MinIO 未設定

**現象**:
- 環境變數 `MINIO_*` 未設定
- `upload_images=true` 參數無法使用

**影響**:
- 無法將圖片上傳到雲端儲存
- 無法產生可存取的圖片 URL

### 問題 3: 輸出目錄在 /tmp

**現象**:
- 預設輸出目錄為 `/tmp/mineru_tianshu_output/`
- `/tmp` 在系統重啟後會被清空

**影響**:
- 結果不持久，可能意外遺失
- 需要手動設定 `--output-dir` 到持久位置

---

## 設計問題分析

### 目前架構的假設

```
目前設計假設：
1. Client 與 Server 在同一台機器（可直接存取 result_path）
2. 或者使用 MinIO 雲端儲存
3. 或者 Client 只需要文字，不需要圖片
```

### 對遠端 Client 的問題

```
遠端 Client 場景：

Client (遠端)                    Server (localhost:8000)
     │                                    │
     │  POST /tasks/submit                │
     │  ─────────────────────────────────>│
     │                                    │  處理 PDF
     │                                    │  儲存到 /tmp/...
     │  GET /tasks/{id}                   │
     │  ─────────────────────────────────>│
     │                                    │
     │  Response:                         │
     │  { "content": "![](images/x.jpg)" }│
     │  <─────────────────────────────────│
     │                                    │
     │  ❌ 無法存取 /tmp 的圖片！          │
```

---

## 建議解決方案

### 方案 A: 新增 ZIP 打包下載 API

```
GET /api/v1/tasks/{task_id}/download
→ 回傳 ZIP 檔案（包含 Markdown + images/）
```

**優點**:
- 無需額外設定
- 下載即可使用

**缺點**:
- 傳輸體積較大
- 不需要圖片時也要下載

### 方案 B: 設定 MinIO

```bash
export MINIO_ENDPOINT="minio.company.com"
export MINIO_ACCESS_KEY="xxx"
export MINIO_SECRET_KEY="xxx"
export MINIO_BUCKET="documents"
```

**優點**:
- 圖片可按需下載
- 支援 CDN 快取
- URL 可分享

**缺點**:
- 需要額外部署 MinIO
- 設定較複雜

### 方案 C: 兩者都支援（建議）

```
GET /api/v1/tasks/{task_id}
    → 回傳 Markdown 文字 + 圖片 metadata（現有）

GET /api/v1/tasks/{task_id}?upload_images=true
    → 上傳到 MinIO，回傳帶 URL 的 Markdown（現有）

GET /api/v1/tasks/{task_id}/download   ← 新增
    → 回傳 ZIP 打包檔（給不想用 MinIO 的人）
```

---

## 其他觀察

### client_example.py 的問題

`client_example.py:118` 的寫法有誤導：

```python
# 目前寫法（顯示伺服器路徑，對遠端 Client 沒用）
logger.info(f"   Output: {status.get('result_path')}")

# 建議改成
if status.get('data'):
    content = status['data']['content']
    logger.info(f"   Content length: {len(content)} chars")
```

### API 回傳的 result_path 欄位

- `result_path` 是伺服器內部路徑
- 對遠端 Client 沒有實際用途
- 建議僅用於除錯，不應作為主要功能

---

## 測試結論

1. **核心功能正常**: PDF 解析、Markdown 生成、API 查詢都正常運作
2. **圖片回傳有缺陷**: 遠端 Client 無法取得圖片，需要改進
3. **MinIO 是可選功能**: 但目前是取得圖片的唯一方式
4. **建議新增 ZIP 下載**: 讓基本功能不依賴 MinIO

---

## 已解決的問題

### 問題 4: Ctrl+C 無法完整關閉所有服務（已修復）

**現象**:
- 按 Ctrl+C 只會關閉 FastAPI 伺服器
- LitServe Worker 的子進程會變成孤兒進程繼續運行
- 需要手動 `kill` 才能完全停止

**原因**:
- `subprocess.Popen` 啟動的子進程會產生孫進程（如 GPU Workers）
- `proc.terminate()` 只會終止直接子進程，不會終止孫進程

**解決方案**:
修改 `start_all.py`，使用進程組管理：

```python
# 1. 啟動時創建獨立進程組
subprocess.Popen(..., start_new_session=True)

# 2. 終止時殺死整個進程組
os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
```

**驗證結果**: 2025-12-29 測試通過，Ctrl+C 可完整關閉所有服務

### 問題 5: client_example.py 功能不完整（已修復）

**現象**:
- 完成任務後只顯示伺服器路徑，不儲存結果到本地
- 檔案列表寫死在程式碼中，無法自動掃描目錄

**解決方案**:
1. 新增 `save_result()` 方法，完成後自動存檔到本地
2. `example_batch_tasks()` 改為自動掃描指定目錄
3. 支援命令列參數指定輸入/輸出目錄
4. 自動排除 Windows Zone.Identifier 檔案

**使用方式**:
```bash
# 預設處理 ./pdfs 目錄
python client_example.py

# 指定目錄
python client_example.py batch -i ./my_docs -o ./results
```

**驗證結果**: 2025-12-29 測試通過

### 問題 6: client_example.py batch/single 命令不下載圖片（已修復）

**現象**:
- 執行 `python client_example.py batch` 只會儲存 Markdown 檔案
- 圖片沒有被下載，導致 Markdown 中的圖片引用無法顯示

**原因**:
- `example_batch_tasks()` 和 `example_single_task()` 使用 `save_result()` 方法
- `save_result()` 只從 API 回應中取得 Markdown 文字內容
- 沒有呼叫 ZIP 下載 API 來取得圖片

**解決方案**:
修改 `client_example.py`，將 `save_result()` 改為 `download_result()`：

```python
# 修改前 (example_single_task)
client.save_result(final_status, output_dir='./output', filename=filename)

# 修改後
await client.download_result(session, task_id, output_dir='./output')

# 修改前 (example_batch_tasks)
client.save_result(status, output_dir=output_dir, filename=filename)

# 修改後
await client.download_result(session, task_id, output_dir=output_dir)
```

**修改後的行為**:

| 命令 | 修改前 | 修改後 |
|------|--------|--------|
| `batch` | 只有 .md | .md + images/ |
| `single` | 只有 .md | .md + images/ |
| `download` | .md + images/ | .md + images/ |

**備註**: `save_result()` 方法保留，供日後只需要 Markdown 文字的場景使用

**驗證結果**: 2025-12-30 修改完成

---

## 後續行動

- [x] 考慮是否新增 ZIP 打包下載 API（已實作 `GET /api/v1/tasks/{task_id}/download`）
- [ ] 評估 MinIO 部署的可行性
- [ ] 修改輸出目錄到持久位置
- [x] 修復 Ctrl+C 無法完整關閉服務的問題
- [x] 更新 client_example.py 完整功能（自動掃描目錄、存檔結果）
- [x] 修復 client_example.py batch/single 不下載圖片的問題
