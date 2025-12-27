#!/usr/bin/env python3
"""
MinerU PDF 解析 API 簡易客戶端

這是一個簡單的範例程式，展示如何使用 MinerU API 將 PDF 轉換為純文字。

使用方式:
    python simple_client.py                          # 測試 pdfs/ 目錄下所有 PDF
    python simple_client.py --pdf document.pdf       # 測試單一 PDF
    python simple_client.py --url http://IP:8000     # 指定 API 伺服器

需求:
    pip install requests
"""

import json
import os
import time
from pathlib import Path

import requests

# =============================================================================
# 設定區域 - 請根據需要修改
# =============================================================================

API_URL = "http://35.194.197.46:8000"  # API 伺服器位址
POLL_INTERVAL = 10  # 輪詢間隔（秒）
OUTPUT_DIR = "output_results"  # 結果輸出目錄


# =============================================================================
# 主要函數
# =============================================================================

def parse_pdf(pdf_path: str, api_url: str = API_URL) -> dict:
    """
    解析單一 PDF 檔案

    Args:
        pdf_path: PDF 檔案路徑
        api_url: API 伺服器位址

    Returns:
        解析結果，格式為:
        {
            "task_id": "xxx",
            "status": "completed",
            "result": [
                {"pageNo": 1, "words": "第一頁內容..."},
                {"pageNo": 2, "words": "第二頁內容..."},
                ...
            ]
        }
    """
    pdf_path = Path(pdf_path)
    print(f"\n{'='*60}")
    print(f"處理檔案: {pdf_path.name}")
    print(f"{'='*60}")

    # Step 1: 提交 PDF
    print("1. 上傳 PDF...")
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{api_url}/api/v1/parse",
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=60
        )

    if resp.status_code != 201:
        print(f"   錯誤: 上傳失敗 (HTTP {resp.status_code})")
        print(f"   {resp.text}")
        return None

    task_id = resp.json()["task_id"]
    print(f"   Task ID: {task_id}")

    # Step 2: 輪詢結果
    print("2. 等待處理完成...")
    start_time = time.time()

    while True:
        resp = requests.get(f"{api_url}/api/v1/result/{task_id}", timeout=30)
        data = resp.json()
        status = data["status"]
        elapsed = time.time() - start_time

        if status == "completed":
            print(f"   完成! (耗時 {elapsed:.1f} 秒)")
            return data

        elif status == "failed":
            print(f"   失敗: {data.get('error', '未知錯誤')}")
            return None

        else:
            print(f"   處理中... ({elapsed:.0f} 秒)")
            time.sleep(POLL_INTERVAL)


def save_result(result: dict, pdf_name: str, output_dir: str = OUTPUT_DIR):
    """儲存結果到 JSON 檔案"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 儲存完整 JSON
    json_file = output_path / f"{Path(pdf_name).stem}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"3. 結果已儲存: {json_file}")

    # 儲存純文字
    txt_file = output_path / f"{Path(pdf_name).stem}.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for page in result.get("result", []):
            f.write(f"=== 第 {page['pageNo']} 頁 ===\n")
            f.write(page["words"])
            f.write("\n\n")
    print(f"   純文字版本: {txt_file}")


def show_preview(result: dict, max_chars: int = 200):
    """顯示結果預覽"""
    pages = result.get("result", [])
    print(f"\n4. 預覽 (共 {len(pages)} 頁):")
    for page in pages[:3]:
        preview = page["words"][:max_chars]
        if len(page["words"]) > max_chars:
            preview += "..."
        print(f"   [第 {page['pageNo']} 頁] {preview}")
    if len(pages) > 3:
        print(f"   ... 還有 {len(pages) - 3} 頁")


# =============================================================================
# 主程式
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MinerU PDF 解析 API 簡易客戶端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
    python simple_client.py                          # 測試 pdfs/ 目錄
    python simple_client.py --pdf document.pdf       # 測試單一檔案
    python simple_client.py --url http://IP:8000     # 指定伺服器
        """
    )
    parser.add_argument("--url", default=API_URL, help=f"API 伺服器位址 (預設: {API_URL})")
    parser.add_argument("--pdf", type=Path, help="單一 PDF 檔案路徑")
    parser.add_argument("--pdf-dir", type=Path, help="PDF 目錄路徑")
    parser.add_argument("--output", default=OUTPUT_DIR, help=f"輸出目錄 (預設: {OUTPUT_DIR})")
    args = parser.parse_args()

    # 收集 PDF 檔案
    pdf_files = []
    if args.pdf:
        if not args.pdf.exists():
            print(f"錯誤: 找不到檔案 {args.pdf}")
            return
        pdf_files.append(args.pdf)
    else:
        pdf_dir = args.pdf_dir or (Path(__file__).parent / "pdfs")
        if not pdf_dir.exists():
            print(f"錯誤: 找不到目錄 {pdf_dir}")
            return
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"錯誤: {pdf_dir} 中沒有 PDF 檔案")
            return

    # 顯示資訊
    print("=" * 60)
    print("MinerU PDF 解析 API 簡易客戶端")
    print("=" * 60)
    print(f"API 伺服器: {args.url}")
    print(f"輸出目錄:   {args.output}")
    print(f"PDF 檔案:   {len(pdf_files)} 個")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")

    # 檢查伺服器連線
    print("\n檢查伺服器連線...")
    try:
        resp = requests.get(f"{args.url}/api/v1/health", timeout=5)
        if resp.status_code == 200:
            print(f"  伺服器狀態: OK")
        else:
            print(f"  伺服器回應異常: HTTP {resp.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print(f"  錯誤: 無法連線到 {args.url}")
        print(f"  請確認伺服器已啟動")
        return

    # 處理每個 PDF
    results = []
    for pdf_path in pdf_files:
        result = parse_pdf(pdf_path, args.url)
        if result:
            save_result(result, pdf_path.name, args.output)
            show_preview(result)
            results.append((pdf_path.name, len(result.get("result", []))))

    # 總結
    print("\n" + "=" * 60)
    print("處理完成!")
    print("=" * 60)
    print(f"成功: {len(results)}/{len(pdf_files)} 個檔案")
    for name, pages in results:
        print(f"  - {name}: {pages} 頁")
    print(f"\n結果已儲存到: {args.output}/")


if __name__ == "__main__":
    main()
