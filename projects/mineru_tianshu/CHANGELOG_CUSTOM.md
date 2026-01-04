# MinerU Tianshu 自訂功能變更紀錄

## 版本資訊
- 基於分支: `mineru_2_7_0_custom`
- 移植日期: 2026-01-04
- 基於 MinerU 版本: 2.7.0
- 原始分支: `mineru_2_6_7_custom`
- Conda 環境: `tianshu_2_7_0`

---

## 移植說明

本分支將 `mineru_2_6_7_custom` 分支的天樞專案移植到 MinerU 2.7.0 版本。主要變更：

1. **預設 Backend 變更**: `pipeline` → `hybrid-auto-engine`
2. **Conda 環境更新**: `mineru_tianshu` → `tianshu_2_7_0`
3. **新增 ZIP 下載功能**: 遠端 Client 可下載完整結果（Markdown + 圖片）
4. **改進進程管理**: 使用進程組確保 Ctrl+C 能正確終止所有子進程

---

## 功能總覽

| 功能 | 說明 |
|------|------|
| ZIP 下載端點 | `/api/v1/tasks/{task_id}/download` |
| 客戶端下載方法 | `download_result()`, `save_result()` |
| argparse CLI | `batch`, `download`, `monitor` 命令 |
| 進程組管理 | `start_new_session=True` + `os.killpg()` |
| hybrid 後端 | 預設使用 `hybrid-auto-engine` |

---

## 功能一：ZIP 下載端點

### 功能說明

遠端 Client 可透過 API 下載任務結果的 ZIP 檔案，包含 Markdown 和 images 目錄。

### API 端點

```
GET /api/v1/tasks/{task_id}/download
```

### 回應

- **200**: 返回 ZIP 檔案（`application/zip`）
- **400**: 任務未完成
- **404**: 任務不存在
- **410**: 結果已過期清理

### ZIP 內容結構

```
{filename}_result.zip
├── {filename}.md      # Markdown 檔案
└── images/            # 圖片目錄（如有）
    ├── image1.png
    └── image2.jpg
```

### 修改的檔案

#### `api_server.py`

```python
from fastapi.responses import StreamingResponse
import zipfile
import io

@app.get("/api/v1/tasks/{task_id}/download")
async def download_task_result(task_id: str):
    """
    下載任務結果 ZIP 檔案
    """
    task = db.get_task(task_id)

    # 檢查任務狀態...

    # 建立 ZIP 檔案（在記憶體中）
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 加入 Markdown 檔案
        zip_file.write(md_file, md_file.name)

        # 加入圖片目錄
        if image_dir.exists():
            for img_file in image_dir.iterdir():
                zip_file.write(img_file, f"images/{img_file.name}")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )
```

---

## 功能二：客戶端下載方法

### 功能說明

`TianshuClient` 類別新增兩個方法：
- `download_result()`: 從伺服器下載 ZIP 並解壓縮
- `save_result()`: 將 API 回傳的內容儲存到本地

### 新增方法

#### `download_result()`

```python
async def download_result(
    self,
    session: aiohttp.ClientSession,
    task_id: str,
    output_dir: str = './output',
    extract: bool = True
) -> Optional[str]:
    """
    下載任務結果 ZIP 檔案

    Args:
        session: aiohttp session
        task_id: 任務 ID
        output_dir: 輸出目錄
        extract: 是否解壓縮 ZIP（預設 True）

    Returns:
        下載的檔案路徑（ZIP 或解壓縮目錄），失敗時返回 None
    """
```

#### `save_result()`

```python
def save_result(
    self,
    status: Dict,
    output_dir: str = './output',
    filename: Optional[str] = None
) -> Optional[str]:
    """
    將完成的任務結果儲存到本地檔案

    Args:
        status: 任務狀態字典
        output_dir: 輸出目錄
        filename: 輸出檔名（不含副檔名）

    Returns:
        儲存的檔案路徑，失敗時返回 None
    """
```

### 使用方式

```python
client = TianshuClient()

async with aiohttp.ClientSession() as session:
    # 提交任務
    result = await client.submit_task(session, 'document.pdf')
    task_id = result['task_id']

    # 等待完成
    status = await client.wait_for_task(session, task_id)

    # 下載 ZIP（包含 Markdown + 圖片）
    await client.download_result(session, task_id, output_dir='./output')
```

---

## 功能三：argparse CLI 介面

### 功能說明

`client_example.py` 使用 `argparse` 提供更完整的命令列介面。

### 支援的命令

| 命令 | 說明 |
|------|------|
| `batch` | 批次處理目錄下所有檔案（預設） |
| `single` | 處理單一檔案 |
| `priority` | 優先級佇列示範 |
| `monitor` | 監控佇列狀態 |
| `download` | 下載特定任務結果 |

### 使用方式

```bash
# 批次處理 pdfs 目錄（預設）
python client_example.py

# 指定輸入和輸出目錄
python client_example.py batch --input-dir ./my_docs --output-dir ./results

# 下載特定任務的結果（包含 Markdown + 圖片）
python client_example.py download <task_id>

# 下載但不解壓縮（保留 ZIP 檔案）
python client_example.py download <task_id> --no-extract

# 監控佇列狀態
python client_example.py monitor

# 查看幫助
python client_example.py --help
```

### 批次處理自動掃描

```python
# 支援的檔案格式
supported_extensions = {
    '.epub', '.pdf', '.docx', '.doc',
    '.pptx', '.ppt', '.xlsx', '.xls',
    '.html', '.htm', '.png', '.jpg', '.jpeg'
}

# 自動遍歷目錄下所有支援的檔案
files = [
    str(f) for f in input_path.iterdir()
    if f.is_file() and f.suffix.lower() in supported_extensions
]
```

---

## 功能四：進程組管理

### 功能說明

使用 `start_new_session=True` 創建獨立進程組，確保 Ctrl+C 時能正確終止所有子進程（包括 LitServe 的孫進程）。

### 問題背景

原本的實作只用 `proc.terminate()`，但 LitServe Worker 會產生額外的子進程（如 CUDA 進程），這些孫進程不會被 `terminate()` 終止，導致：
- GPU 記憶體未釋放
- 端口被佔用
- 需要手動 `kill` 進程

### 解決方案

#### `start_all.py`

```python
# 啟動時創建新進程組
api_proc = subprocess.Popen(
    [sys.executable, 'api_server.py'],
    cwd=Path(__file__).parent,
    env=env,
    start_new_session=True  # 創建新進程組
)

worker_proc = subprocess.Popen(
    worker_cmd,
    cwd=Path(__file__).parent,
    start_new_session=True  # 創建新進程組
)

scheduler_proc = subprocess.Popen(
    scheduler_cmd,
    cwd=Path(__file__).parent,
    start_new_session=True  # 創建新進程組
)
```

```python
def stop_services(self, signum=None, frame=None):
    """停止所有服务（包括子進程的所有孫進程）"""

    # 終止整個進程組
    for name, proc in self.processes:
        if proc.poll() is None:
            try:
                # 發送 SIGTERM 到整個進程組
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()

    # 強制殺死未響應的進程
    for name, proc in self.processes:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
```

---

## 功能五：hybrid-auto-engine 後端

### 功能說明

MinerU 2.7.0 預設使用 `hybrid-auto-engine` 後端，結合 pipeline 和 VLM 的優點。

### 變更

#### `api_server.py`

```python
# 舊版（2.6.7）
backend: str = Form('pipeline', description="处理后端: pipeline/vlm-transformers/vlm-vllm-engine")

# 新版（2.7.0）
backend: str = Form('hybrid-auto-engine', description="处理后端: hybrid-auto-engine/pipeline/vlm-transformers")
```

#### `client_example.py`

```python
# 舊版（2.6.7）
backend: str = 'pipeline',

# 新版（2.7.0）
backend: str = 'hybrid-auto-engine',
```

### 輸出路徑說明

不同 backend 輸出到不同子目錄：

| Backend | 輸出目錄 |
|---------|----------|
| `pipeline` | `{output_dir}/{filename}/auto/` |
| `hybrid-auto-engine` | `{output_dir}/{filename}/hybrid_auto/` |
| `vlm-*` | `{output_dir}/{filename}/vlm/` |

**注意**: Tianshu 的 API 使用 `rglob('*.md')` 搜尋，不受輸出路徑影響。

---

## 檔案變更總覽

### 新增檔案

```
projects/mineru_tianshu/
├── CLAUDE.md              # 專案文件（英文）
├── CLAUDE_zh.md           # 專案文件（中文）
└── CHANGELOG_CUSTOM.md    # 本變更紀錄
```

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `api_server.py` | 新增 ZIP 下載端點、更新預設 backend |
| `client_example.py` | 新增下載方法、argparse CLI、更新預設 backend |
| `start_all.py` | 新增進程組管理 |

---

## 安裝與設定

### 環境需求

```bash
# 使用專用 conda 環境
conda activate tianshu_2_7_0

# 安裝 MinerU（從專案根目錄）
cd /home/cobra/projects/MinerU_opendatalab
pip install -e ".[all]"

# 安裝 tianshu 依賴
cd projects/mineru_tianshu
pip install -r requirements.txt
```

### 快速開始

```bash
# 啟動所有服務
python start_all.py

# 另一個終端執行客戶端
python client_example.py batch
```

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 2.7.0-custom | 2026-01-04 | 移植到 MinerU 2.7.0，新增 ZIP 下載、進程管理 |
| 2.6.7-custom | 2025-12-30 | 原始天樞專案實作 |

---

## 聯絡資訊

如有問題，請參考：
- 專案 CLAUDE.md: `/home/cobra/projects/MinerU_opendatalab/CLAUDE.md`
- Tianshu CLAUDE.md: `/home/cobra/projects/MinerU_opendatalab/projects/mineru_tianshu/CLAUDE.md`
- Demo CHANGELOG: `/home/cobra/projects/MinerU_opendatalab/demo/CHANGELOG_CUSTOM.md`
