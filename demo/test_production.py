"""Production test: client_json format closest to original output
Settings: output_format="client_json", disable_image_extract=False
Tests all 4 PDF files
"""
import os
import json
from pathlib import Path

__dir__ = os.path.dirname(os.path.abspath(__file__))
pdf_files_dir = os.path.join(__dir__, "pdfs")
output_dir = os.path.join(__dir__, "output_production")

# All 4 test PDFs
test_pdfs = [
    os.path.join(pdf_files_dir, "demo1.pdf"),
    os.path.join(pdf_files_dir, "demo2.pdf"),
    os.path.join(pdf_files_dir, "demo3.pdf"),
    os.path.join(pdf_files_dir, "small_ocr.pdf"),
]

from demo import parse_doc

print("=" * 70)
print("Production Test: client_json format (closest to original output)")
print("Settings: output_format='client_json', disable_image_extract=False")
print("Test files: demo1.pdf, demo2.pdf, demo3.pdf, small_ocr.pdf")
print("=" * 70)

parse_doc(
    [Path(p) for p in test_pdfs],
    output_dir,
    backend="pipeline",
    disable_image_extract=False,  # Don't restrict image extraction (original behavior)
    output_format="client_json",  # Client-requested JSON format
)

print("\n" + "=" * 70)
print("Test Results:")
print("=" * 70)

# Check and display outputs
for pdf_name in ["demo1", "demo2", "demo3", "small_ocr"]:
    json_path = os.path.join(output_dir, pdf_name, "auto", f"{pdf_name}.json")
    images_dir = os.path.join(output_dir, pdf_name, "auto", "images")

    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Statistics
        total_pages = len(data)
        total_chars = sum(len(p["words"]) for p in data)

        # Check images directory
        img_count = 0
        if os.path.exists(images_dir):
            img_count = len([f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])

        print(f"\nOK {pdf_name}.pdf:")
        print(f"   JSON file: {os.path.getsize(json_path):,} bytes")
        print(f"   Total pages: {total_pages}")
        print(f"   Total characters: {total_chars:,}")
        print(f"   Extracted images: {img_count}")

        # Show per-page summary
        print(f"   Per-page character count:")
        for page in data:
            preview = page["words"][:50].replace('\n', ' ')
            print(f"     Page {page['pageNo']}: {len(page['words']):,} chars - \"{preview}...\"")
    else:
        print(f"\nFAIL {pdf_name}.pdf: Output file not found")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)
