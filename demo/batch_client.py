#!/usr/bin/env python3
"""
MinerU PDF 解析 API 批次客戶端

支援同時處理多個 PDF 檔案，提升處理效率。
參考 mineru_tianshu 專案的 asyncio + aiohttp 設計模式。

使用方式:
    python batch_client.py                              # 測試 pdfs/ 目錄下所有 PDF
    python batch_client.py --pdf doc1.pdf doc2.pdf      # 測試指定的多個 PDF
    python batch_client.py --max-concurrent 5           # 最多同時處理 5 個
    python batch_client.py --url http://IP:8000         # 指定 API 伺服器
    python batch_client.py --stats                      # 只顯示隊列統計
    python batch_client.py --priority 10                # 設定任務優先級

需求:
    pip install aiohttp
"""

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import aiohttp
except ImportError:
    print("錯誤: 需要安裝 aiohttp")
    print("請執行: pip install aiohttp")
    exit(1)


# =============================================================================
# 設定區域
# =============================================================================

API_URL = "http://127.0.0.1:8000"  # API 伺服器位址
POLL_INTERVAL = 5  # 輪詢間隔（秒）
MAX_CONCURRENT = 3  # 最大同時處理數
OUTPUT_DIR = "output_results"  # 結果輸出目錄
TIMEOUT = 1800  # 單個任務超時時間（秒）= 30 分鐘


# =============================================================================
# 異步客戶端類別
# =============================================================================

class BatchClient:
    """批次處理客戶端"""

    def __init__(
        self,
        api_url: str = API_URL,
        poll_interval: float = POLL_INTERVAL,
        timeout: int = TIMEOUT,
    ):
        self.api_url = api_url.rstrip('/')
        self.poll_interval = poll_interval
        self.timeout = timeout

    async def check_health(self, session: aiohttp.ClientSession) -> dict:
        """檢查伺服器健康狀態"""
        try:
            async with session.get(
                f"{self.api_url}/api/v1/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def get_queue_stats(self, session: aiohttp.ClientSession) -> dict:
        """取得隊列統計資訊"""
        try:
            async with session.get(
                f"{self.api_url}/api/v1/queue/stats",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def submit_task(
        self,
        session: aiohttp.ClientSession,
        pdf_path: Path,
        priority: int = 0,
    ) -> dict:
        """
        提交單一 PDF 任務（不等待完成）

        Returns:
            {'success': True, 'task_id': 'xxx', 'pdf_name': 'xxx.pdf'}
            或
            {'success': False, 'error': '錯誤訊息', 'pdf_name': 'xxx.pdf'}
        """
        pdf_name = pdf_path.name
        try:
            with open(pdf_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field(
                    'file',
                    f,
                    filename=pdf_name,
                    content_type='application/pdf'
                )
                data.add_field('priority', str(priority))

                async with session.post(
                    f"{self.api_url}/api/v1/parse",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 201:
                        result = await resp.json()
                        return {
                            'success': True,
                            'task_id': result['task_id'],
                            'pdf_name': pdf_name,
                        }
                    else:
                        text = await resp.text()
                        return {
                            'success': False,
                            'error': f"HTTP {resp.status}: {text}",
                            'pdf_name': pdf_name,
                        }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'pdf_name': pdf_name,
            }

    async def wait_for_task(
        self,
        session: aiohttp.ClientSession,
        task_id: str,
        pdf_name: str,
    ) -> dict:
        """
        等待單一任務完成（輪詢）

        Returns:
            {'success': True, 'task_id': 'xxx', 'pdf_name': 'xxx.pdf', 'result': [...], 'elapsed': 123.4}
            或
            {'success': False, 'task_id': 'xxx', 'pdf_name': 'xxx.pdf', 'error': '錯誤訊息'}
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            # 檢查超時
            if elapsed > self.timeout:
                return {
                    'success': False,
                    'task_id': task_id,
                    'pdf_name': pdf_name,
                    'error': f"超時 ({self.timeout} 秒)",
                }

            try:
                async with session.get(
                    f"{self.api_url}/api/v1/result/{task_id}",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    status = data.get('status')

                    if status == 'completed':
                        return {
                            'success': True,
                            'task_id': task_id,
                            'pdf_name': pdf_name,
                            'result': data.get('result', []),
                            'elapsed': elapsed,
                        }
                    elif status == 'failed':
                        return {
                            'success': False,
                            'task_id': task_id,
                            'pdf_name': pdf_name,
                            'error': data.get('error', '處理失敗'),
                        }
                    # else: pending 或 processing，繼續等待

            except Exception as e:
                # 網路錯誤，繼續重試
                pass

            await asyncio.sleep(self.poll_interval)

    async def process_single_pdf(
        self,
        session: aiohttp.ClientSession,
        pdf_path: Path,
        priority: int = 0,
        progress_callback=None,
    ) -> dict:
        """
        處理單一 PDF：提交 + 等待完成

        這是給「滑動視窗」模式使用的包裝函數
        """
        pdf_name = pdf_path.name

        # 提交任務
        submit_result = await self.submit_task(session, pdf_path, priority=priority)
        if not submit_result['success']:
            if progress_callback:
                progress_callback(pdf_name, 'failed', submit_result.get('error'))
            return submit_result

        task_id = submit_result['task_id']
        if progress_callback:
            progress_callback(pdf_name, 'submitted', task_id)

        # 等待完成
        wait_result = await self.wait_for_task(session, task_id, pdf_name)
        if progress_callback:
            if wait_result['success']:
                progress_callback(pdf_name, 'completed', wait_result.get('elapsed'))
            else:
                progress_callback(pdf_name, 'failed', wait_result.get('error'))

        return wait_result


# =============================================================================
# 批次處理函數
# =============================================================================

async def process_batch(
    pdf_files: list[Path],
    api_url: str = API_URL,
    max_concurrent: int = MAX_CONCURRENT,
    poll_interval: float = POLL_INTERVAL,
    output_dir: str = OUTPUT_DIR,
    priority: int = 0,
) -> dict:
    """
    批次處理多個 PDF 檔案

    使用「滑動視窗」模式：
    - 最多同時處理 max_concurrent 個任務
    - 完成一個就補充一個
    - 直到所有檔案處理完成

    Args:
        pdf_files: PDF 檔案路徑列表
        api_url: API 伺服器位址
        max_concurrent: 最大同時處理數
        poll_interval: 輪詢間隔（秒）
        output_dir: 輸出目錄
        priority: 任務優先級（越高越優先處理）

    Returns:
        {
            'total': 10,
            'completed': 8,
            'failed': 2,
            'results': [...],
            'total_time': 123.4
        }
    """
    client = BatchClient(api_url=api_url, poll_interval=poll_interval)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 狀態追蹤
    pending_pdfs = list(pdf_files)  # 待處理的 PDF
    active_tasks: dict[str, asyncio.Task] = {}  # {pdf_name: task}
    results = []  # 所有結果
    start_time = time.time()

    # 進度顯示
    total_count = len(pdf_files)
    completed_count = 0
    failed_count = 0

    def print_progress(pdf_name: str, status: str, info=None):
        nonlocal completed_count, failed_count
        timestamp = datetime.now().strftime("%H:%M:%S")

        if status == 'submitted':
            active_count = len(active_tasks)
            pending_count = len(pending_pdfs)
            print(f"  [{timestamp}] Submitted: {pdf_name} (task_id: {info[:8]}...)")
            print(f"             Status: {active_count} processing, {pending_count} pending")
        elif status == 'completed':
            completed_count += 1
            print(f"  [{timestamp}] Completed: {pdf_name} ({info:.1f} sec)")
            print(f"             Progress: {completed_count + failed_count}/{total_count}")
        elif status == 'failed':
            failed_count += 1
            print(f"  [{timestamp}] Failed: {pdf_name} ({info})")

    print(f"\n{'='*60}")
    print(f"Starting batch processing ({total_count} files, max {max_concurrent} concurrent)")
    print(f"{'='*60}")

    async with aiohttp.ClientSession() as session:
        # 檢查伺服器連線
        health = await client.check_health(session)
        if not health:
            print(f"Error: Cannot connect to {api_url}")
            return {
                'total': total_count,
                'completed': 0,
                'failed': total_count,
                'results': [],
                'total_time': time.time() - start_time,
            }

        workers = health.get('workers', 'N/A')
        print(f"Server connected (Workers: {workers})\n")

        # 主迴圈：滑動視窗模式
        while pending_pdfs or active_tasks:
            # 1. 補充任務到 max_concurrent
            while pending_pdfs and len(active_tasks) < max_concurrent:
                pdf_path = pending_pdfs.pop(0)
                pdf_name = pdf_path.name

                # 建立異步任務
                task = asyncio.create_task(
                    client.process_single_pdf(session, pdf_path, priority, print_progress)
                )
                active_tasks[pdf_name] = task

            # 2. 等待任一任務完成
            if active_tasks:
                done, _ = await asyncio.wait(
                    active_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )

                # 3. 處理完成的任務
                for completed_task in done:
                    result = completed_task.result()
                    pdf_name = result['pdf_name']

                    # 從活躍任務中移除
                    if pdf_name in active_tasks:
                        del active_tasks[pdf_name]

                    # 儲存結果
                    results.append(result)
                    if result['success']:
                        save_result(result, output_path)

    # 統計
    total_time = time.time() - start_time
    completed = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])

    return {
        'total': total_count,
        'completed': completed,
        'failed': failed,
        'results': results,
        'total_time': total_time,
    }


def save_result(result: dict, output_path: Path):
    """儲存單一結果到檔案"""
    pdf_name = result['pdf_name']
    stem = Path(pdf_name).stem

    # 儲存 JSON
    json_file = output_path / f"{stem}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'task_id': result['task_id'],
            'status': 'completed',
            'result': result['result'],
        }, f, ensure_ascii=False, indent=2)


# =============================================================================
# 主程式
# =============================================================================

async def show_queue_stats(api_url: str):
    """顯示隊列統計資訊"""
    client = BatchClient(api_url=api_url)

    async with aiohttp.ClientSession() as session:
        health = await client.check_health(session)
        if not health:
            print(f"Error: Cannot connect to {api_url}")
            return

        stats = await client.get_queue_stats(session)
        if not stats:
            print("Error: Cannot get queue stats")
            return

        print("=" * 60)
        print("MinerU Batch API Queue Statistics")
        print("=" * 60)
        print(f"API Server:   {api_url}")
        print(f"Workers:      {health.get('workers', 'N/A')}")
        print()
        print("Queue Status:")
        queue_stats = stats.get('stats', {})
        print(f"  Pending:    {queue_stats.get('pending', 0)}")
        print(f"  Processing: {queue_stats.get('processing', 0)}")
        print(f"  Completed:  {queue_stats.get('completed', 0)}")
        print(f"  Failed:     {queue_stats.get('failed', 0)}")
        print(f"  Total:      {stats.get('total', 0)}")
        print()
        print(f"Timestamp: {stats.get('timestamp', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(
        description="MinerU PDF Parsing API Batch Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python batch_client.py                              # Test pdfs/ directory
    python batch_client.py --pdf doc1.pdf doc2.pdf      # Specify multiple files
    python batch_client.py --max-concurrent 5           # Max 5 concurrent
    python batch_client.py --url http://IP:8000         # Specify server
    python batch_client.py --stats                      # Show queue stats
    python batch_client.py --priority 10                # Set high priority
        """
    )
    parser.add_argument("--url", default=API_URL,
                        help=f"API server URL (default: {API_URL})")
    parser.add_argument("--pdf", type=Path, nargs='+',
                        help="Specify one or more PDF files")
    parser.add_argument("--pdf-dir", type=Path,
                        help="PDF directory path")
    parser.add_argument("--output", default=OUTPUT_DIR,
                        help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT,
                        help=f"Max concurrent tasks (default: {MAX_CONCURRENT})")
    parser.add_argument("--poll-interval", type=float, default=POLL_INTERVAL,
                        help=f"Poll interval in seconds (default: {POLL_INTERVAL})")
    parser.add_argument("--priority", type=int, default=0,
                        help="Task priority (default: 0, higher = processed first)")
    parser.add_argument("--stats", action="store_true",
                        help="Only show queue stats, don't process files")
    args = parser.parse_args()

    # 如果只顯示統計
    if args.stats:
        asyncio.run(show_queue_stats(args.url))
        return

    # 收集 PDF 檔案
    pdf_files = []
    if args.pdf:
        for pdf in args.pdf:
            if not pdf.exists():
                print(f"Error: File not found {pdf}")
                return
            pdf_files.append(pdf)
    else:
        pdf_dir = args.pdf_dir or (Path(__file__).parent / "pdfs")
        if not pdf_dir.exists():
            print(f"Error: Directory not found {pdf_dir}")
            return
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"Error: No PDF files in {pdf_dir}")
            return

    # 顯示資訊
    print("=" * 60)
    print("MinerU PDF Parsing API Batch Client")
    print("=" * 60)
    print(f"API Server:      {args.url}")
    print(f"Output Dir:      {args.output}")
    print(f"Max Concurrent:  {args.max_concurrent}")
    print(f"Poll Interval:   {args.poll_interval} sec")
    print(f"PDF Files:       {len(pdf_files)}")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")

    # 執行批次處理
    summary = asyncio.run(process_batch(
        pdf_files=pdf_files,
        api_url=args.url,
        max_concurrent=args.max_concurrent,
        poll_interval=args.poll_interval,
        output_dir=args.output,
        priority=args.priority,
    ))

    # 顯示總結
    print(f"\n{'='*60}")
    print("Processing Complete!")
    print(f"{'='*60}")
    total_time = summary.get('total_time', 0)
    print(f"Total:    {summary['total']} files")
    print(f"Success:  {summary['completed']}")
    print(f"Failed:   {summary['failed']}")
    print(f"Duration: {total_time:.1f} sec")

    if summary['completed'] > 0:
        avg_time = total_time / summary['completed']
        print(f"Average:  {avg_time:.1f} sec/file")

    # 顯示詳細結果
    print(f"\nDetailed Results:")
    for r in summary['results']:
        if r['success']:
            pages = len(r.get('result', []))
            print(f"  OK {r['pdf_name']}: {pages} pages ({r['elapsed']:.1f} sec)")
        else:
            print(f"  FAIL {r['pdf_name']}: {r.get('error', 'Unknown error')}")

    print(f"\nResults saved to: {args.output}/")


if __name__ == "__main__":
    main()
