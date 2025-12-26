"""
Test script for MinerU Async PDF Parsing API

Usage:
    1. Start the API server first:
       uvicorn api:app --host 0.0.0.0 --port 8000

    2. Run this test:
       python test_api.py
       python test_api.py --pdf path/to/your.pdf
       python test_api.py --url http://localhost:8000
"""

import argparse
import sys
import time
from pathlib import Path

import requests


def test_health(base_url: str) -> bool:
    """Test health endpoint"""
    print("\n[1] Testing health endpoint...")
    try:
        resp = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if resp.status_code == 200:
            print(f"    Status: OK")
            print(f"    Response: {resp.json()}")
            return True
        else:
            print(f"    Status: FAILED (HTTP {resp.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"    ERROR: Cannot connect to {base_url}")
        print(f"    Please start the API server first:")
        print(f"      uvicorn api:app --host 0.0.0.0 --port 8000")
        return False


def test_parse_pdf(base_url: str, pdf_path: Path, poll_interval: int = 3, output_dir: Path = None) -> bool:
    """Test PDF parsing workflow"""
    print(f"\n[2] Testing PDF parsing: {pdf_path.name}")

    # Step 1: Submit PDF
    print("    Submitting PDF...")
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        resp = requests.post(f"{base_url}/api/v1/parse", files=files, timeout=30)

    if resp.status_code != 201:
        print(f"    ERROR: Failed to submit PDF (HTTP {resp.status_code})")
        print(f"    Response: {resp.text}")
        return False

    data = resp.json()
    task_id = data["task_id"]
    print(f"    Task ID: {task_id}")
    print(f"    Status: {data['status']}")

    # Step 2: Poll for result
    print("\n[3] Polling for result...")
    max_attempts = 60  # Max 3 minutes (60 * 3 seconds)
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        resp = requests.get(f"{base_url}/api/v1/result/{task_id}", timeout=10)
        data = resp.json()
        status = data["status"]

        if status == "completed":
            print(f"    Status: COMPLETED")
            result = data["result"]
            print(f"    Pages: {len(result)}")
            print("\n[4] Result preview:")
            for page in result[:3]:  # Show first 3 pages
                words_preview = page["words"][:100] + "..." if len(page["words"]) > 100 else page["words"]
                print(f"    Page {page['pageNo']}: {words_preview}")
            if len(result) > 3:
                print(f"    ... and {len(result) - 3} more pages")

            # Save result to file
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"{task_id}.json"
                import json
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"\n[*] Result saved to: {output_file}")

            return True

        elif status == "failed":
            print(f"    Status: FAILED")
            print(f"    Error: {data.get('error', 'Unknown error')}")
            return False

        else:
            print(f"    Attempt {attempt}: {status}...")
            time.sleep(poll_interval)

    print(f"    ERROR: Timeout after {max_attempts * poll_interval} seconds")
    return False


def test_invalid_file(base_url: str) -> bool:
    """Test error handling for invalid file"""
    print("\n[5] Testing error handling (non-PDF file)...")

    # Create a temporary text file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"This is not a PDF")
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            resp = requests.post(f"{base_url}/api/v1/parse", files=files, timeout=10)

        if resp.status_code == 400:
            print(f"    Status: OK (correctly rejected)")
            print(f"    Response: {resp.json()}")
            return True
        else:
            print(f"    Status: Unexpected (HTTP {resp.status_code})")
            return False
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_not_found(base_url: str) -> bool:
    """Test 404 for non-existent task"""
    print("\n[6] Testing 404 for non-existent task...")

    resp = requests.get(f"{base_url}/api/v1/result/non-existent-task-id", timeout=5)

    if resp.status_code == 404:
        print(f"    Status: OK (correctly returned 404)")
        print(f"    Response: {resp.json()}")
        return True
    else:
        print(f"    Status: Unexpected (HTTP {resp.status_code})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test MinerU Async PDF Parsing API")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--pdf", type=Path, help="Path to single PDF file to test (if not specified, tests all PDFs in pdfs/)")
    parser.add_argument("--pdf-dir", type=Path, help="Directory containing PDF files to test")
    parser.add_argument("--output-dir", type=Path, default=Path("output_api_test"), help="Directory to save result JSON")
    parser.add_argument("--poll-interval", type=int, default=3, help="Polling interval in seconds")
    args = parser.parse_args()

    # Collect PDF files to test
    pdf_files = []
    if args.pdf:
        # Single PDF specified
        if not args.pdf.exists():
            print(f"ERROR: PDF file not found: {args.pdf}")
            sys.exit(1)
        pdf_files.append(args.pdf)
    else:
        # Use pdf-dir or default pdfs/ directory
        pdf_dir = args.pdf_dir or (Path(__file__).parent / "pdfs")
        if not pdf_dir.exists():
            print(f"ERROR: PDF directory not found: {pdf_dir}")
            sys.exit(1)
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"ERROR: No PDF files found in {pdf_dir}")
            sys.exit(1)

    print("=" * 60)
    print("MinerU Async PDF Parsing API Test")
    print("=" * 60)
    print(f"API URL: {args.url}")
    print(f"PDF files to test: {len(pdf_files)}")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")

    results = []

    # Test 1: Health check
    results.append(("Health Check", test_health(args.url)))
    if not results[-1][1]:
        print("\n" + "=" * 60)
        print("ABORTED: API server not running")
        sys.exit(1)

    # Test 2: PDF parsing for all files
    for pdf_file in pdf_files:
        test_name = f"PDF: {pdf_file.name}"
        result = test_parse_pdf(args.url, pdf_file, args.poll_interval, args.output_dir)
        results.append((test_name, result))

    # Test 3: Invalid file
    results.append(("Invalid File Handling", test_invalid_file(args.url)))

    # Test 4: 404
    results.append(("404 Handling", test_not_found(args.url)))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} passed")
    print(f"\nResults saved to: {args.output_dir}/")

    if passed == len(results):
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
