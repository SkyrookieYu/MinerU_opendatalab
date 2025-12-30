"""
MinerU Tianshu - Client Example
天枢客户端示例

演示如何使用 Python 客户端提交任务和查询状态
"""
import asyncio
import aiohttp
from pathlib import Path
from loguru import logger
import time
from typing import Dict, Optional


class TianshuClient:
    """天枢客户端"""
    
    def __init__(self, api_url='http://localhost:8000'):
        self.api_url = api_url
        self.base_url = f"{api_url}/api/v1"
    
    async def submit_task(
        self,
        session: aiohttp.ClientSession,
        file_path: str,
        backend: str = 'pipeline',
        lang: str = 'ch',
        method: str = 'auto',
        formula_enable: bool = True,
        table_enable: bool = True,
        priority: int = 0
    ) -> Dict:
        """
        提交任务
        
        Args:
            session: aiohttp session
            file_path: 文件路径
            backend: 处理后端
            lang: 语言
            method: 解析方法
            formula_enable: 是否启用公式识别
            table_enable: 是否启用表格识别
            priority: 优先级
            
        Returns:
            响应字典，包含 task_id
        """
        with open(file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=Path(file_path).name)
            data.add_field('backend', backend)
            data.add_field('lang', lang)
            data.add_field('method', method)
            data.add_field('formula_enable', str(formula_enable).lower())
            data.add_field('table_enable', str(table_enable).lower())
            data.add_field('priority', str(priority))
            
            async with session.post(f'{self.base_url}/tasks/submit', data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"✅ Submitted: {file_path} -> Task ID: {result['task_id']}")
                    return result
                else:
                    error = await resp.text()
                    logger.error(f"❌ Failed to submit {file_path}: {error}")
                    return {'success': False, 'error': error}
    
    async def get_task_status(self, session: aiohttp.ClientSession, task_id: str) -> Dict:
        """
        查询任务状态
        
        Args:
            session: aiohttp session
            task_id: 任务ID
            
        Returns:
            任务状态字典
        """
        async with session.get(f'{self.base_url}/tasks/{task_id}') as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {'success': False, 'error': 'Task not found'}
    
    async def wait_for_task(
        self,
        session: aiohttp.ClientSession,
        task_id: str,
        timeout: int = 600,
        poll_interval: int = 2
    ) -> Dict:
        """
        等待任务完成
        
        Args:
            session: aiohttp session
            task_id: 任务ID
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            最终任务状态
        """
        start_time = time.time()
        
        while True:
            status = await self.get_task_status(session, task_id)
            
            if not status.get('success'):
                logger.error(f"❌ Failed to get status for task {task_id}")
                return status
            
            task_status = status.get('status')
            
            if task_status == 'completed':
                logger.info(f"✅ Task {task_id} completed!")
                # 顯示內容長度而非伺服器路徑（對遠端 Client 更有意義）
                data = status.get('data', {})
                if data.get('content'):
                    logger.info(f"   Content: {len(data['content']):,} chars")
                return status
            
            elif task_status == 'failed':
                logger.error(f"❌ Task {task_id} failed!")
                logger.error(f"   Error: {status.get('error_message')}")
                return status
            
            elif task_status == 'cancelled':
                logger.warning(f"⚠️  Task {task_id} was cancelled")
                return status
            
            # 检查超时
            if time.time() - start_time > timeout:
                logger.error(f"⏱️  Task {task_id} timeout after {timeout}s")
                return {'success': False, 'error': 'timeout'}
            
            # 等待后继续轮询
            await asyncio.sleep(poll_interval)
    
    async def get_queue_stats(self, session: aiohttp.ClientSession) -> Dict:
        """获取队列统计"""
        async with session.get(f'{self.base_url}/queue/stats') as resp:
            return await resp.json()
    
    async def cancel_task(self, session: aiohttp.ClientSession, task_id: str) -> Dict:
        """取消任务"""
        async with session.delete(f'{self.base_url}/tasks/{task_id}') as resp:
            return await resp.json()

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
        import zipfile
        import io

        url = f'{self.base_url}/tasks/{task_id}/download'

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    # 從 header 取得檔名
                    content_disposition = resp.headers.get('Content-Disposition', '')
                    if 'filename=' in content_disposition:
                        zip_filename = content_disposition.split('filename=')[1].strip('"')
                    else:
                        zip_filename = f'{task_id}_result.zip'

                    # 建立輸出目錄
                    output_path = Path(output_dir)
                    output_path.mkdir(parents=True, exist_ok=True)

                    # 讀取 ZIP 內容
                    zip_content = await resp.read()

                    if extract:
                        # 解壓縮到輸出目錄
                        extract_dir = output_path / zip_filename.replace('_result.zip', '')
                        extract_dir.mkdir(parents=True, exist_ok=True)

                        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                            zf.extractall(extract_dir)

                        # 計算解壓縮的檔案數量
                        files = list(extract_dir.rglob('*'))
                        file_count = len([f for f in files if f.is_file()])

                        logger.info(f"📦 Downloaded & extracted: {extract_dir} ({file_count} files)")
                        return str(extract_dir)
                    else:
                        # 直接儲存 ZIP 檔案
                        zip_path = output_path / zip_filename
                        zip_path.write_bytes(zip_content)

                        logger.info(f"📦 Downloaded: {zip_path} ({len(zip_content):,} bytes)")
                        return str(zip_path)

                elif resp.status == 400:
                    error = await resp.json()
                    logger.warning(f"⚠️  Cannot download: {error.get('detail')}")
                    return None
                elif resp.status == 404:
                    logger.error(f"❌ Task not found: {task_id}")
                    return None
                elif resp.status == 410:
                    error = await resp.json()
                    logger.warning(f"⚠️  Result expired: {error.get('detail')}")
                    return None
                else:
                    error = await resp.text()
                    logger.error(f"❌ Download failed ({resp.status}): {error}")
                    return None

        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return None

    def save_result(
        self,
        status: Dict,
        output_dir: str = './output',
        filename: Optional[str] = None
    ) -> Optional[str]:
        """
        將完成的任務結果儲存到本地檔案

        Args:
            status: 任務狀態字典（從 wait_for_task 或 get_task_status 取得）
            output_dir: 輸出目錄
            filename: 輸出檔名（不含副檔名），預設使用 task_id

        Returns:
            儲存的檔案路徑，失敗時返回 None
        """
        if status.get('status') != 'completed':
            logger.warning(f"Task not completed, status: {status.get('status')}")
            return None

        data = status.get('data', {})
        content = data.get('content')

        if not content:
            logger.warning("No content in task result")
            return None

        # 建立輸出目錄
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 決定檔名
        if not filename:
            filename = status.get('task_id', 'output')

        # 儲存 Markdown 檔案
        md_file = output_path / f"{filename}.md"
        md_file.write_text(content, encoding='utf-8')

        logger.info(f"💾 Saved: {md_file} ({len(content):,} chars)")

        return str(md_file)


async def example_single_task():
    """示例1：提交单个任务并等待完成"""
    logger.info("=" * 60)
    logger.info("示例1：提交单个任务")
    logger.info("=" * 60)

    client = TianshuClient()
    file_path = './pdfs/w101-126.pdf'

    async with aiohttp.ClientSession() as session:
        # 提交任务
        result = await client.submit_task(
            session,
            file_path=file_path,
            backend='pipeline',
            lang='ch',
            formula_enable=True,
            table_enable=True
        )

        if result.get('success'):
            task_id = result['task_id']

            # 等待完成
            logger.info(f"⏳ Waiting for task {task_id} to complete...")
            final_status = await client.wait_for_task(session, task_id)

            # 下載結果到本地（包含 Markdown + 圖片）
            if final_status.get('status') == 'completed':
                await client.download_result(session, task_id, output_dir='./output')

            return final_status


async def example_batch_tasks(input_dir: str = './pdfs', output_dir: str = './output'):
    """示例2：批量提交目錄下所有檔案並等待完成"""
    logger.info("=" * 60)
    logger.info("示例2：批量提交多个任务")
    logger.info("=" * 60)

    client = TianshuClient()

    # 支援的檔案格式
    supported_extensions = {'.epub', '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.html', '.htm', '.png', '.jpg', '.jpeg'}

    # 遍歷目錄下所有支援的檔案
    input_path = Path(input_dir)
    if not input_path.exists():
        logger.error(f"❌ Input directory not found: {input_dir}")
        return []

    files = [
        str(f) for f in input_path.iterdir()
        if f.is_file()
        and f.suffix.lower() in supported_extensions
        and 'Zone.Identifier' not in f.name  # 排除 Windows Zone.Identifier 檔案
    ]

    if not files:
        logger.warning(f"⚠️  No supported files found in {input_dir}")
        return []

    logger.info(f"📂 Found {len(files)} files in {input_dir}")

    async with aiohttp.ClientSession() as session:
        # 并发提交所有任务
        logger.info(f"📤 Submitting {len(files)} tasks...")
        submit_tasks = [
            client.submit_task(session, file)
            for file in files
        ]
        results = await asyncio.gather(*submit_tasks)

        # 提取成功提交的任務資訊（task_id 與原始檔案路徑）
        submitted = [
            (r['task_id'], files[i])
            for i, r in enumerate(results)
            if r.get('success')
        ]
        task_ids = [t[0] for t in submitted]
        logger.info(f"✅ Submitted {len(task_ids)} tasks successfully")

        # 并发等待所有任务完成
        logger.info(f"⏳ Waiting for all tasks to complete...")
        wait_tasks = [
            client.wait_for_task(session, task_id)
            for task_id in task_ids
        ]
        final_results = await asyncio.gather(*wait_tasks)

        # 下載完成的結果到本地（包含 Markdown + 圖片）
        logger.info("")
        logger.info("📦 Downloading results...")
        for i, status in enumerate(final_results):
            if status.get('status') == 'completed':
                task_id = submitted[i][0]
                await client.download_result(session, task_id, output_dir=output_dir)

        # 统计结果
        completed = sum(1 for r in final_results if r.get('status') == 'completed')
        failed = sum(1 for r in final_results if r.get('status') == 'failed')

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"📊 Results: {completed} completed, {failed} failed")
        logger.info("=" * 60)

        return final_results


async def example_priority_tasks():
    """示例3：使用优先级队列"""
    logger.info("=" * 60)
    logger.info("示例3：优先级队列")
    logger.info("=" * 60)
    
    client = TianshuClient()
    
    async with aiohttp.ClientSession() as session:
        # 提交低优先级任务
        low_priority = await client.submit_task(
            session,
            file_path='../../demo/pdfs/demo1.pdf',
            priority=0
        )
        logger.info(f"📝 Low priority task: {low_priority['task_id']}")
        
        # 提交高优先级任务
        high_priority = await client.submit_task(
            session,
            file_path='../../demo/pdfs/demo2.pdf',
            priority=10
        )
        logger.info(f"🔥 High priority task: {high_priority['task_id']}")
        
        # 高优先级任务会先被处理
        logger.info("⏳ 高优先级任务将优先处理...")


async def example_queue_monitoring():
    """示例4：监控队列状态"""
    logger.info("=" * 60)
    logger.info("示例4：监控队列状态")
    logger.info("=" * 60)

    client = TianshuClient()

    async with aiohttp.ClientSession() as session:
        # 获取队列统计
        stats = await client.get_queue_stats(session)

        logger.info("📊 Queue Statistics:")
        logger.info(f"   Total: {stats.get('total', 0)}")
        for status, count in stats.get('stats', {}).items():
            logger.info(f"   {status:12s}: {count}")


async def example_download_task(task_id: str, output_dir: str = './output', extract: bool = True):
    """示例5：下載任務結果 ZIP（包含 Markdown + 圖片）"""
    logger.info("=" * 60)
    logger.info("示例5：下載任務結果")
    logger.info("=" * 60)

    client = TianshuClient()

    async with aiohttp.ClientSession() as session:
        # 先檢查任務狀態
        status = await client.get_task_status(session, task_id)

        if not status.get('success'):
            logger.error(f"❌ Task not found: {task_id}")
            return None

        task_status = status.get('status')
        logger.info(f"📋 Task {task_id}")
        logger.info(f"   File: {status.get('file_name')}")
        logger.info(f"   Status: {task_status}")

        if task_status != 'completed':
            logger.warning(f"⚠️  Task is not completed yet (status: {task_status})")
            return None

        # 下載 ZIP
        result_path = await client.download_result(
            session,
            task_id,
            output_dir=output_dir,
            extract=extract
        )

        if result_path:
            logger.info(f"✅ Result saved to: {result_path}")

        return result_path


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='MinerU Tianshu 客戶端範例',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 批次處理 pdfs 目錄下所有檔案
  python client_example.py batch

  # 指定輸入和輸出目錄
  python client_example.py batch --input-dir ./my_docs --output-dir ./results

  # 下載特定任務的結果（包含 Markdown + 圖片）
  python client_example.py download <task_id>

  # 下載但不解壓縮（保留 ZIP 檔案）
  python client_example.py download <task_id> --no-extract

  # 監控佇列狀態
  python client_example.py monitor
        """
    )

    parser.add_argument('command', nargs='?', default='batch',
                        choices=['batch', 'single', 'priority', 'monitor', 'download'],
                        help='要執行的範例 (預設: batch)')
    parser.add_argument('task_id', nargs='?', default=None,
                        help='任務 ID（download 命令使用）')
    parser.add_argument('--input-dir', '-i', type=str, default='./pdfs',
                        help='輸入目錄 (預設: ./pdfs)')
    parser.add_argument('--output-dir', '-o', type=str, default='./output',
                        help='輸出目錄 (預設: ./output)')
    parser.add_argument('--no-extract', action='store_true',
                        help='下載時不解壓縮 ZIP（預設會解壓縮）')

    args = parser.parse_args()

    try:
        if args.command == 'single':
            await example_single_task()

        elif args.command == 'batch':
            await example_batch_tasks(
                input_dir=args.input_dir,
                output_dir=args.output_dir
            )

        elif args.command == 'priority':
            await example_priority_tasks()

        elif args.command == 'monitor':
            await example_queue_monitoring()

        elif args.command == 'download':
            if not args.task_id:
                logger.error("❌ 請提供 task_id，例如: python client_example.py download <task_id>")
                return
            await example_download_task(
                task_id=args.task_id,
                output_dir=args.output_dir,
                extract=not args.no_extract
            )

    except Exception as e:
        logger.error(f"Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    """
    使用方法:

    # 批次處理 pdfs 目錄（預設）
    python client_example.py

    # 指定輸入和輸出目錄
    python client_example.py batch -i ./my_docs -o ./results

    # 下載特定任務的結果（包含 Markdown + 圖片）
    python client_example.py download <task_id>

    # 下載但不解壓縮（保留 ZIP 檔案）
    python client_example.py download <task_id> --no-extract

    # 監控佇列狀態
    python client_example.py monitor

    # 查看幫助
    python client_example.py --help
    """
    asyncio.run(main())

