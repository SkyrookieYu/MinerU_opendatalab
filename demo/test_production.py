"""產品線測試：最接近原始輸出的 client_json 格式
設定: output_format="client_json", disable_image_extract=False
測試全部 4 個 PDF 檔案
"""
import os
import json
from pathlib import Path

__dir__ = os.path.dirname(os.path.abspath(__file__))
pdf_files_dir = os.path.join(__dir__, "pdfs")
output_dir = os.path.join(__dir__, "output_production")

# 全部 4 個測試 PDF
test_pdfs = [
    os.path.join(pdf_files_dir, "demo1.pdf"),
    os.path.join(pdf_files_dir, "demo2.pdf"),
    os.path.join(pdf_files_dir, "demo3.pdf"),
    os.path.join(pdf_files_dir, "small_ocr.pdf"),
]

from demo import parse_doc

print("=" * 70)
print("產品線測試：client_json 格式 (最接近原始輸出)")
print("設定: output_format='client_json', disable_image_extract=False")
print("測試檔案: demo1.pdf, demo2.pdf, demo3.pdf, small_ocr.pdf")
print("=" * 70)

parse_doc(
    [Path(p) for p in test_pdfs],
    output_dir,
    backend="pipeline",
    disable_image_extract=False,  # 不限制圖片提取 (原始行為)
    output_format="client_json",  # 客戶端要求的 JSON 格式
)

print("\n" + "=" * 70)
print("測試結果:")
print("=" * 70)

# 檢查並顯示輸出
for pdf_name in ["demo1", "demo2", "demo3", "small_ocr"]:
    json_path = os.path.join(output_dir, pdf_name, "auto", f"{pdf_name}.json")
    images_dir = os.path.join(output_dir, pdf_name, "auto", "images")

    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 統計
        total_pages = len(data)
        total_chars = sum(len(p["words"]) for p in data)

        # 檢查圖片目錄
        img_count = 0
        if os.path.exists(images_dir):
            img_count = len([f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])

        print(f"\n✅ {pdf_name}.pdf:")
        print(f"   JSON 檔案: {os.path.getsize(json_path):,} bytes")
        print(f"   總頁數: {total_pages}")
        print(f"   總字元數: {total_chars:,}")
        print(f"   提取圖片數: {img_count}")

        # 顯示每頁摘要
        print(f"   各頁字元數:")
        for page in data:
            preview = page["words"][:50].replace('\n', ' ')
            print(f"     Page {page['pageNo']}: {len(page['words']):,} 字元 - \"{preview}...\"")
    else:
        print(f"\n❌ {pdf_name}.pdf: 輸出檔案不存在")

print("\n" + "=" * 70)
print("測試完成！")
print("=" * 70)
