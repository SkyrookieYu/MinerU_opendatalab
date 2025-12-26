# MinerU 自訂功能變更紀錄

## 版本資訊
- 基於分支: `mineru_2_6_7_custom`
- 變更日期: 2025-12-22
- 基於 MinerU 版本: 2.6.7

---

## 功能一：Markdown 轉純文字工具

### 功能說明
由於 MinerU 輸出的 Markdown 包含圖片連結、數學公式、HTML 表格等格式，提供一個後處理工具將 Markdown 轉換為純文字格式。

### 新增檔案

#### `demo/md_to_plaintext.py`

```python
"""
Markdown to Plain Text Converter for MinerU output.
Removes all Markdown formatting and returns pure text content.
"""
import re
import os
from pathlib import Path


def md_to_plaintext(md_content: str, keep_formulas: bool = False) -> str:
    """
    Convert MinerU Markdown output to plain text.

    Args:
        md_content: Markdown content string
        keep_formulas: If True, keep LaTeX formulas as-is; if False, remove them

    Returns:
        Plain text string
    """
    text = md_content

    # 1. Remove HTML tables
    text = re.sub(r'<table>.*?</table>', '', text, flags=re.DOTALL)

    # 2. Remove images: ![alt](path) or ![](path)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # 2.1 Remove copyright notice for restricted images
    text = re.sub(r'\[此內容因版權原因無法顯示\]', '', text)

    # 3. Handle formulas
    if not keep_formulas:
        # Remove block formulas: $$...$$
        text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
        # Remove inline formulas: $...$
        text = re.sub(r'\$[^$\n]+?\$', '', text)

    # 4. Remove heading markers: # ## ### etc.
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # 5. Remove bold/italic: **text**, __text__, *text*, _text_
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # 6. Remove inline code: `code`
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 7. Remove code blocks: ```...```
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

    # 8. Remove links but keep text: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 9. Remove horizontal rules: ---, ***, ___
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 10. Remove blockquotes: >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # 11. Remove list markers: - , * , 1. , 2. etc.
    text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # 12. Clean up extra blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 13. Remove trailing whitespace on each line
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # 14. Strip leading/trailing whitespace
    text = text.strip()

    return text


def convert_file(input_path: str, output_path: str = None, keep_formulas: bool = False) -> str:
    """
    Convert a Markdown file to plain text.
    """
    input_path = Path(input_path)

    if output_path is None:
        output_path = input_path.with_suffix('.txt')
    else:
        output_path = Path(output_path)

    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    plain_text = md_to_plaintext(md_content, keep_formulas=keep_formulas)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(plain_text)

    return str(output_path)


def batch_convert(input_dir: str, output_dir: str = None, keep_formulas: bool = False) -> list:
    """
    Batch convert all .md files in a directory to plain text.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_files = []
    for md_file in input_dir.rglob('*.md'):
        rel_path = md_file.relative_to(input_dir)
        output_path = output_dir / rel_path.with_suffix('.txt')
        output_path.parent.mkdir(parents=True, exist_ok=True)

        convert_file(str(md_file), str(output_path), keep_formulas=keep_formulas)
        output_files.append(str(output_path))
        print(f"Converted: {md_file} -> {output_path}")

    return output_files


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Convert MinerU Markdown to plain text')
    parser.add_argument('input', help='Input .md file or directory')
    parser.add_argument('-o', '--output', help='Output .txt file or directory')
    parser.add_argument('--keep-formulas', action='store_true', help='Keep LaTeX formulas')

    args = parser.parse_args()

    input_path = Path(args.input)

    if input_path.is_file():
        output_path = convert_file(args.input, args.output, args.keep_formulas)
        print(f"Output: {output_path}")
    elif input_path.is_dir():
        output_files = batch_convert(args.input, args.output, args.keep_formulas)
        print(f"Converted {len(output_files)} files")
    else:
        print(f"Error: {args.input} does not exist")
```

### 使用方式

```bash
# 單檔轉換
python md_to_plaintext.py output/demo1/auto/demo1.md

# 指定輸出路徑
python md_to_plaintext.py input.md -o output.txt

# 批次轉換目錄
python md_to_plaintext.py output/ -o plaintext_output/

# 保留數學公式
python md_to_plaintext.py demo1.md --keep-formulas
```

```python
# 在程式碼中使用
from md_to_plaintext import md_to_plaintext, convert_file

plain_text = md_to_plaintext(markdown_string)
convert_file('demo1.md', 'demo1.txt')
```

---

## 功能二：版權限制功能 (disable_image_extract)

### 功能說明
針對有版權限制的 PDF 文件，提供選項禁止提取圖片到 images 目錄，並在 Markdown 和 JSON 輸出中顯示版權提示文字。

### 修改的檔案清單

| 檔案路徑 | 修改類型 | 說明 |
|----------|----------|------|
| `mineru/utils/cut_image.py` | 修改 | 新增版權限制標記常量和參數 |
| `mineru/backend/pipeline/model_json_to_middle_json.py` | 修改 | 傳遞 disable_image_extract 參數 |
| `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py` | 修改 | 處理版權限制，顯示提示文字 |
| `mineru/backend/vlm/vlm_middle_json_mkcontent.py` | 修改 | 處理版權限制，顯示提示文字 |
| `demo/demo.py` | 修改 | 新增 disable_image_extract 參數 |

---

### 修改詳情

#### 1. `mineru/utils/cut_image.py`

**新增內容：**

```python
# 版權限制標記常量 (新增)
COPYRIGHT_RESTRICTED_MARKER = "__COPYRIGHT_RESTRICTED__"


def cut_image_and_table(span, page_pil_img, page_img_md5, page_id, image_writer, scale=2, disable_image_extract=False):  # 新增參數

    def return_path(path_type):
        return f"{path_type}/{page_img_md5}"

    span_type = span["type"]

    # === 新增：版權限制模式處理 ===
    if disable_image_extract:
        # 版權限制模式：不提取圖片，設定特殊標記
        span["image_path"] = COPYRIGHT_RESTRICTED_MARKER
    # === 新增結束 ===
    elif not check_img_bbox(span["bbox"]) or not image_writer:
        span["image_path"] = ""
    else:
        span["image_path"] = cut_image(
            span["bbox"], page_id, page_pil_img, return_path=return_path(span_type), image_writer=image_writer, scale=scale
        )

    return span
```

**變更說明：**
- 新增 `COPYRIGHT_RESTRICTED_MARKER` 常量
- `cut_image_and_table` 函數新增 `disable_image_extract` 參數
- 當 `disable_image_extract=True` 時，設定 `image_path` 為特殊標記而非實際提取圖片

---

#### 2. `mineru/backend/pipeline/model_json_to_middle_json.py`

**修改函數簽名：**

```python
# 原始
def page_model_info_to_page_info(page_model_info, image_dict, page, image_writer, page_index, ocr_enable=False, formula_enabled=True):

# 修改後
def page_model_info_to_page_info(page_model_info, image_dict, page, image_writer, page_index, ocr_enable=False, formula_enabled=True, disable_image_extract=False):
```

```python
# 原始
def result_to_middle_json(model_list, images_list, pdf_doc, image_writer, lang=None, ocr_enable=False, formula_enabled=True):

# 修改後
def result_to_middle_json(model_list, images_list, pdf_doc, image_writer, lang=None, ocr_enable=False, formula_enabled=True, disable_image_extract=False):
```

**修改 cut_image_and_table 調用：**

```python
# 原始
span = cut_image_and_table(
    span, page_pil_img, page_img_md5, page_index, image_writer, scale=scale
)

# 修改後
span = cut_image_and_table(
    span, page_pil_img, page_img_md5, page_index, image_writer, scale=scale, disable_image_extract=disable_image_extract
)
```

**修改 page_model_info_to_page_info 調用：**

```python
# 原始
page_info = page_model_info_to_page_info(
    page_model_info, image_dict, page, image_writer, page_index, ocr_enable=ocr_enable, formula_enabled=formula_enabled
)

# 修改後
page_info = page_model_info_to_page_info(
    page_model_info, image_dict, page, image_writer, page_index, ocr_enable=ocr_enable, formula_enabled=formula_enabled, disable_image_extract=disable_image_extract
)
```

---

#### 3. `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py`

**新增 import 和常量：**

```python
# 新增
from mineru.utils.cut_image import COPYRIGHT_RESTRICTED_MARKER

# 版權限制提示文字
COPYRIGHT_NOTICE = "此內容因版權原因無法顯示"
```

**修改 `make_blocks_to_markdown` 函數 - INTERLINE_EQUATION 處理：**

```python
# 原始
else:
    para_text += f"![]({img_buket_path}/{para_block['lines'][0]['spans'][0]['image_path']})"

# 修改後
else:
    img_path = para_block['lines'][0]['spans'][0].get('image_path', '')
    if img_path == COPYRIGHT_RESTRICTED_MARKER:
        para_text += f"[{COPYRIGHT_NOTICE}]"
    elif img_path:
        para_text += f"![]({img_buket_path}/{img_path})"
```

**修改 `make_blocks_to_markdown` 函數 - IMAGE 處理 (兩處)：**

```python
# 原始
if span.get('image_path', ''):
    para_text += f"![]({img_buket_path}/{span['image_path']})"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_text += f"[{COPYRIGHT_NOTICE}]"
elif img_path:
    para_text += f"![]({img_buket_path}/{img_path})"
```

**修改 `make_blocks_to_markdown` 函數 - TABLE 處理：**

```python
# 原始
if span.get('html', ''):
    para_text += f"\n{span['html']}\n"
elif span.get('image_path', ''):
    para_text += f"![]({img_buket_path}/{span['image_path']})"

# 修改後
if span.get('html', ''):
    para_text += f"\n{span['html']}\n"
else:
    img_path = span.get('image_path', '')
    if img_path == COPYRIGHT_RESTRICTED_MARKER:
        para_text += f"[{COPYRIGHT_NOTICE}]"
    elif img_path:
        para_text += f"![]({img_buket_path}/{img_path})"
```

**修改 `make_blocks_to_content_list` 函數 - INTERLINE_EQUATION：**

```python
# 原始
para_content = {
    'type': ContentType.EQUATION,
    'img_path': f"{img_buket_path}/{para_block['lines'][0]['spans'][0].get('image_path', '')}",
}

# 修改後
img_path = para_block['lines'][0]['spans'][0].get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_content = {
        'type': ContentType.EQUATION,
        'img_path': '',
        'copyright_restricted': True,
        'copyright_notice': COPYRIGHT_NOTICE,
    }
else:
    para_content = {
        'type': ContentType.EQUATION,
        'img_path': f"{img_buket_path}/{img_path}" if img_path else '',
    }
```

**修改 `make_blocks_to_content_list` 函數 - IMAGE：**

```python
# 原始
if span.get('image_path', ''):
    para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_content['img_path'] = ''
    para_content['copyright_restricted'] = True
    para_content['copyright_notice'] = COPYRIGHT_NOTICE
elif img_path:
    para_content['img_path'] = f"{img_buket_path}/{img_path}"
```

**修改 `make_blocks_to_content_list` 函數 - TABLE：**

```python
# 原始
if span.get('image_path', ''):
    para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_content['img_path'] = ''
    para_content['copyright_restricted'] = True
    para_content['copyright_notice'] = COPYRIGHT_NOTICE
elif img_path:
    para_content['img_path'] = f"{img_buket_path}/{img_path}"
```

---

#### 4. `mineru/backend/vlm/vlm_middle_json_mkcontent.py`

**新增 import 和常量：**

```python
# 新增
from mineru.utils.cut_image import COPYRIGHT_RESTRICTED_MARKER

# 版權限制提示文字
COPYRIGHT_NOTICE = "此內容因版權原因無法顯示"
```

**修改 `merge_para_with_text` 函數 - INTERLINE_EQUATION：**

```python
# 原始
else:
    if span.get('image_path', ''):
        content = f"![]({img_buket_path}/{span['image_path']})"

# 修改後
else:
    img_path = span.get('image_path', '')
    if img_path == COPYRIGHT_RESTRICTED_MARKER:
        content = f"[{COPYRIGHT_NOTICE}]"
    elif img_path:
        content = f"![]({img_buket_path}/{img_path})"
```

**修改 `mk_blocks_to_markdown` 函數 - IMAGE 處理 (兩處)：**

```python
# 原始
if span.get('image_path', ''):
    para_text += f"![]({img_buket_path}/{span['image_path']})"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_text += f"[{COPYRIGHT_NOTICE}]"
elif img_path:
    para_text += f"![]({img_buket_path}/{img_path})"
```

**修改 `mk_blocks_to_markdown` 函數 - TABLE 處理：**

```python
# 原始
if table_enable:
    if span.get('html', ''):
        para_text += f"\n{span['html']}\n"
    elif span.get('image_path', ''):
        para_text += f"![]({img_buket_path}/{span['image_path']})"
else:
    if span.get('image_path', ''):
        para_text += f"![]({img_buket_path}/{span['image_path']})"

# 修改後
if table_enable:
    if span.get('html', ''):
        para_text += f"\n{span['html']}\n"
    else:
        img_path = span.get('image_path', '')
        if img_path == COPYRIGHT_RESTRICTED_MARKER:
            para_text += f"[{COPYRIGHT_NOTICE}]"
        elif img_path:
            para_text += f"![]({img_buket_path}/{img_path})"
else:
    img_path = span.get('image_path', '')
    if img_path == COPYRIGHT_RESTRICTED_MARKER:
        para_text += f"[{COPYRIGHT_NOTICE}]"
    elif img_path:
        para_text += f"![]({img_buket_path}/{img_path})"
```

**修改 `make_blocks_to_content_list` 函數 - IMAGE：**

```python
# 原始
if span.get('image_path', ''):
    para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_content['img_path'] = ''
    para_content['copyright_restricted'] = True
    para_content['copyright_notice'] = COPYRIGHT_NOTICE
elif img_path:
    para_content['img_path'] = f"{img_buket_path}/{img_path}"
```

**修改 `make_blocks_to_content_list` 函數 - TABLE：**

```python
# 原始
if span.get('image_path', ''):
    para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"

# 修改後
img_path = span.get('image_path', '')
if img_path == COPYRIGHT_RESTRICTED_MARKER:
    para_content['img_path'] = ''
    para_content['copyright_restricted'] = True
    para_content['copyright_notice'] = COPYRIGHT_NOTICE
elif img_path:
    para_content['img_path'] = f"{img_buket_path}/{img_path}"
```

---

#### 5. `demo/demo.py`

**修改 `do_parse` 函數簽名：**

```python
# 原始
def do_parse(
    ...
    end_page_id=None,
):

# 修改後
def do_parse(
    ...
    end_page_id=None,
    disable_image_extract=False,  # 新增：Disable image extraction due to copyright restrictions
):
```

**修改 `pipeline_result_to_middle_json` 調用：**

```python
# 原始
middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, formula_enable)

# 修改後
middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, formula_enable, disable_image_extract)
```

**修改 `parse_doc` 函數簽名：**

```python
# 原始
def parse_doc(
    ...
    end_page_id=None
):

# 修改後
def parse_doc(
    ...
    end_page_id=None,
    disable_image_extract=False,
):
```

**修改 `parse_doc` 函數文檔：**

```python
# 新增參數說明
"""
    ...
    disable_image_extract: Disable image extraction due to copyright restrictions. When True, images will not be
        extracted to the images directory, and a copyright notice will be displayed in markdown and JSON output.
"""
```

**修改 `do_parse` 調用：**

```python
# 原始
do_parse(
    ...
    end_page_id=end_page_id
)

# 修改後
do_parse(
    ...
    end_page_id=end_page_id,
    disable_image_extract=disable_image_extract,
)
```

---

### 使用方式

```python
from demo import parse_doc

# 啟用版權限制模式
parse_doc(
    doc_path_list,
    output_dir,
    backend="pipeline",
    disable_image_extract=True  # 新參數
)
```

### 輸出效果

#### Markdown 輸出
原本圖片位置：
```markdown
![](images/xxxx.jpg)
Fig. 1. Description...
```

啟用版權限制後：
```markdown
[此內容因版權原因無法顯示]
Fig. 1. Description...
```

#### JSON 輸出
```json
{
    "type": "image",
    "img_path": "",
    "copyright_restricted": true,
    "copyright_notice": "此內容因版權原因無法顯示",
    "image_caption": ["Fig. 1. Description..."]
}
```

#### images 目錄
啟用版權限制後，images 目錄將為空（不提取任何圖片）。

---

## 測試檔案

### `demo/test_copyright.py`
用於測試版權限制功能的測試腳本。

### 測試輸出目錄
- `demo/output_copyright_test/` - 版權限制功能測試輸出

---

## 注意事項

1. 修改 MinerU 核心程式碼後，需要重新安裝套件才能生效：
   ```bash
   cd /home/cobra/projects/MinerU_opendatalab
   pip install -e .
   ```

2. 版權限制功能目前僅支援 `pipeline` 後端。VLM 後端的圖片處理邏輯不同，尚未完整整合。

3. 版權限制會影響所有類型的圖片內容，包括：
   - 一般圖片 (image)
   - 表格圖片 (table)
   - 公式圖片 (equation/interline_equation)

---

## 功能三：統一輸出介面整合

### 功能說明
將「純文字輸出」和「版權限制」功能整合到 `parse_doc` 函數中，透過 `output_format` 參數統一控制輸出格式。

### 修改的檔案

#### `demo/demo.py`

**新增 import：**

```python
# 導入純文字轉換工具
from md_to_plaintext import md_to_plaintext
```

**修改 `do_parse` 函數簽名 - 新增參數：**

```python
def do_parse(
    ...
    disable_image_extract=False,  # Disable image extraction due to copyright restrictions
    output_format="markdown",  # Output format: "markdown" or "plaintext"  # 新增
):
```

**修改 `_process_output` 函數簽名 - 新增參數：**

```python
def _process_output(
    ...
    is_pipeline=True,
    output_format="markdown"  # 新增
):
```

**修改 `_process_output` 函數 - 處理輸出格式：**

```python
# 原始
if f_dump_md:
    make_func = pipeline_union_make if is_pipeline else vlm_union_make
    md_content_str = make_func(pdf_info, f_make_md_mode, image_dir)
    md_writer.write_string(
        f"{pdf_file_name}.md",
        md_content_str,
    )

# 修改後
if f_dump_md:
    make_func = pipeline_union_make if is_pipeline else vlm_union_make
    md_content_str = make_func(pdf_info, f_make_md_mode, image_dir)

    # 根據 output_format 決定輸出格式
    if output_format == "plaintext":
        # 轉換為純文字並輸出 .txt 檔案
        plaintext_content = md_to_plaintext(md_content_str)
        md_writer.write_string(
            f"{pdf_file_name}.txt",
            plaintext_content,
        )
    else:
        # 預設輸出 Markdown
        md_writer.write_string(
            f"{pdf_file_name}.md",
            md_content_str,
        )
```

**修改 `parse_doc` 函數簽名 - 新增參數：**

```python
def parse_doc(
    ...
    disable_image_extract=False,
    output_format="markdown",  # 新增
):
```

**修改 `parse_doc` 函數文檔 - 新增參數說明：**

```python
"""
    ...
    output_format: Output format for the parsed content. Options:
        "markdown": Output as Markdown file (.md) - default
        "plaintext": Output as plain text file (.txt) with all Markdown formatting removed
"""
```

**修改 `do_parse` 調用 - 傳遞新參數：**

```python
do_parse(
    ...
    disable_image_extract=disable_image_extract,
    output_format=output_format,  # 新增
)
```

---

### 使用方式

```python
from demo import parse_doc

# 情境 A: 標準 Markdown 輸出 (預設)
parse_doc(doc_path_list, output_dir)

# 情境 B: 純文字輸出
parse_doc(doc_path_list, output_dir, output_format="plaintext")

# 情境 C: 版權限制 + Markdown 輸出
parse_doc(doc_path_list, output_dir, disable_image_extract=True)

# 情境 D: 版權限制 + 純文字輸出 (完整整合)
parse_doc(
    doc_path_list,
    output_dir,
    disable_image_extract=True,
    output_format="plaintext"
)
```

### 輸出效果對照

| 設定 | 圖片提取 | 輸出檔案 | 圖片位置顯示 |
|------|----------|----------|--------------|
| 預設 | ✅ 提取 | `.md` | `![](images/xxx.jpg)` |
| `output_format="plaintext"` | ✅ 提取 | `.txt` | (完全移除) |
| `output_format="client_json"` | ✅ 提取 | `.json` | (完全移除) |
| `disable_image_extract=True` | ❌ 不提取 | `.md` | `[此內容因版權原因無法顯示]` |
| 兩者結合 (plaintext) | ❌ 不提取 | `.txt` | (完全移除) |
| 兩者結合 (client_json) | ❌ 不提取 | `.json` | (完全移除) |

**注意**: 純文字輸出 (`plaintext` 或 `client_json`) 會完全移除所有圖片相關內容，包括：
- 圖片連結 `![](images/xxx.jpg)`
- 版權提示 `[此內容因版權原因無法顯示]`

這確保純文字輸出只包含實際的文字內容，適合後續 RAG 處理。

### 測試檔案

#### `demo/test_production.py`
產品線測試腳本，使用最接近原始輸出的設定測試所有 4 個 PDF 檔案。

### 測試輸出目錄
- `demo/output_production/` - 產品線測試輸出（包含 demo1, demo2, demo3, small_ocr）

---

## 功能四：客戶端 JSON 輸出格式 (client_json)

### 功能說明
根據客戶端需求，提供分頁的純文字 JSON 輸出格式，每頁包含 `pageNo`（從 1 開始）和 `words`（該頁純文字內容）。

### 輸出格式

```json
[
  {"pageNo": 1, "words": "第一頁的純文字內容..."},
  {"pageNo": 2, "words": "第二頁的純文字內容..."},
  ...
]
```

### 修改的檔案

#### `demo/demo.py`

**新增 `make_client_json` 函數：**

```python
def make_client_json(pdf_info, make_func, f_make_md_mode, image_dir):
    """
    Generate client-requested JSON format with page-by-page plain text.

    Output format:
    [
        {"pageNo": 1, "words": "text content of page 1"},
        {"pageNo": 2, "words": "text content of page 2"},
        ...
    ]

    Args:
        pdf_info: List of page info dictionaries
        make_func: Function to generate markdown (pipeline_union_make or vlm_union_make)
        f_make_md_mode: Make mode for markdown generation
        image_dir: Image directory path

    Returns:
        List of dictionaries with pageNo and words
    """
    result = []

    for page_idx, page_info in enumerate(pdf_info):
        # Create a single-page list to use existing make function
        single_page_info = [page_info]

        # Generate markdown for this page
        page_md_content = make_func(single_page_info, f_make_md_mode, image_dir)

        # Handle both string and list returns
        if isinstance(page_md_content, list):
            page_md_str = '\n'.join(page_md_content)
        else:
            page_md_str = str(page_md_content)

        # Convert markdown to plain text
        page_plaintext = md_to_plaintext(page_md_str)

        # Add to result (pageNo starts from 1)
        result.append({
            "pageNo": page_idx + 1,
            "words": page_plaintext
        })

    return result
```

**修改 `_process_output` 函數 - 新增 client_json 處理：**

```python
if f_dump_md:
    make_func = pipeline_union_make if is_pipeline else vlm_union_make

    # 根據 output_format 決定輸出格式
    if output_format == "client_json":
        # 客戶端要求的 JSON 格式：[{pageNo: 1, words: "xxx"}, ...]
        client_json_data = make_client_json(pdf_info, make_func, f_make_md_mode, image_dir)
        md_writer.write_string(
            f"{pdf_file_name}.json",
            json.dumps(client_json_data, ensure_ascii=False, indent=2),
        )
    elif output_format == "plaintext":
        # 轉換為純文字並輸出 .txt 檔案
        md_content_str = make_func(pdf_info, f_make_md_mode, image_dir)
        plaintext_content = md_to_plaintext(md_content_str)
        md_writer.write_string(
            f"{pdf_file_name}.txt",
            plaintext_content,
        )
    else:
        # 預設輸出 Markdown
        md_content_str = make_func(pdf_info, f_make_md_mode, image_dir)
        md_writer.write_string(
            f"{pdf_file_name}.md",
            md_content_str,
        )
```

**修改 `parse_doc` 函數文檔：**

```python
"""
    output_format: Output format for the parsed content. Options:
        "markdown": Output as Markdown file (.md) - default
        "plaintext": Output as plain text file (.txt) with all Markdown formatting removed
        "client_json": Output as JSON file with page-by-page plain text: [{pageNo: 1, words: "..."}, ...]
"""
```

### 使用方式

```python
from demo import parse_doc

# 客戶端 JSON 格式輸出
parse_doc(
    doc_path_list,
    output_dir,
    backend="pipeline",
    output_format="client_json"
)

# 結合版權限制功能
parse_doc(
    doc_path_list,
    output_dir,
    backend="pipeline",
    disable_image_extract=True,
    output_format="client_json"
)
```

### 輸出範例

處理 `small_ocr.pdf` (8 頁) 的輸出：

```json
[
  {
    "pageNo": 1,
    "words": "史的事情。(3)为有用物的量找到社会尺度，也是这样。商品的这些尺度之所以不同，部分是由于被计量的物的性质不同，部分是由于约定俗成。\n\n物的有用性使物成为使用价值..."
  },
  {
    "pageNo": 2,
    "words": "某种特殊的商品，例如一夸特小麦，按各种极不相同的比例同别的商品交换..."
  },
  ...
]
```

---

## 檔案變更總覽

```
MinerU_opendatalab/
├── demo/
│   ├── md_to_plaintext.py          [新增] Markdown 轉純文字工具
│   ├── demo.py                     [修改] 新增 disable_image_extract, output_format, make_client_json
│   ├── CHANGELOG_CUSTOM.md         [新增] 本變更紀錄文件
│   ├── test_production.py          [新增] 產品線測試腳本
│   └── output_production/          [新增] 產品線測試輸出 (demo1, demo2, demo3, small_ocr)
│
└── mineru/
    ├── utils/
    │   └── cut_image.py            [修改] 新增版權限制標記和參數
    │
    └── backend/
        ├── pipeline/
        │   ├── model_json_to_middle_json.py      [修改] 傳遞 disable_image_extract 參數
        │   └── pipeline_middle_json_mkcontent.py [修改] 處理版權提示
        │
        └── vlm/
            └── vlm_middle_json_mkcontent.py      [修改] 處理版權提示
```

---

## 功能總結

| 功能 | 參數 | 說明 |
|------|------|------|
| 純文字輸出 | `output_format="plaintext"` | 輸出 .txt 檔案，移除所有 Markdown 格式及圖片相關內容 |
| 版權限制 | `disable_image_extract=True` | 不提取圖片，顯示版權提示 |
| 客戶端 JSON | `output_format="client_json"` | 輸出 .json 檔案，分頁純文字 `{pageNo, words}` |

### 完整使用範例

```python
from demo import parse_doc
from pathlib import Path

# 客戶端需求：分頁純文字 JSON + 版權限制
parse_doc(
    [Path("document.pdf")],
    "output_dir",
    backend="pipeline",
    disable_image_extract=True,   # 不提取圖片
    output_format="client_json"   # 分頁 JSON 輸出
)
```

---

## 重要特性：MinerU 的語意分頁機制

### 發現背景

在測試 `client_json` 輸出時發現，某些 PDF 的最後一頁（如 demo1.pdf 第 13 頁）在輸出中顯示為空內容。經調查後確認這是 **MinerU 原始設計的行為**，而非本次修改引入的問題。

### 技術細節

MinerU 的處理流程 (`model_json_to_middle_json`) 會進行**跨頁內容合併**：

1. **model_json（原始偵測）**: 模型確實偵測到第 13 頁有 32 個文字區塊
2. **middle_json（處理後）**: 這些區塊被標記為 `lines_deleted: True`
3. **原因**: MinerU 判斷這些內容是前一頁的延續（如跨頁參考文獻），自動合併到前一頁

### 對 RAG 應用的好處

這個設計對後續 RAG (Retrieval Augmented Generation) 的 chunking 非常有利：

| 傳統按物理頁切分 | MinerU 的語意合併 |
|-----------------|------------------|
| 參考文獻被切成 Page 12 + Page 13 | 參考文獻完整保留在 Page 12 |
| 表格可能被切斷 | 跨頁表格合併處理 |
| 段落在頁面邊界中斷 | 連續段落保持完整 |

**優點：**

1. **語意完整性**: 一份參考文獻、一個表格不會被切成多個 chunk
2. **檢索精確度**: 相關內容在同一個 chunk，向量檢索更準確
3. **減少雜訊**: 避免 chunk 邊界剛好切在句子或段落中間
4. **符合閱讀邏輯**: 輸出結構更接近人類閱讀的理解單位

### 輸出解讀

使用 `output_format="client_json"` 時：

- `pageNo`: 代表**邏輯頁**而非 PDF 的物理頁碼
- 空的 `words`: 表示該物理頁的內容已被合併到前一個邏輯頁
- 這是預期行為，對 RAG 應用更有利

### 範例

```json
[
  {"pageNo": 12, "words": "Acknowledgements... References... Zhang, L., ...（包含原第13頁的參考文獻）"},
  {"pageNo": 13, "words": ""}  // 內容已合併到第12頁
]
```

### 結論

此特性是 MinerU 的核心設計，**不建議修改**。對於需要嚴格按物理頁切分的場景，請使用下方的「功能五：物理頁面模式」。

---

## 功能五：物理頁面模式 (parse_doc_by_physical_page)

### 功能說明

針對需要嚴格按 PDF 物理頁碼進行文字搜尋的場景，提供逐頁解析功能，繞過 MinerU 的語意合併機制。

### 設計原理

利用 `do_parse` 的 `start_page_id` 和 `end_page_id` 參數，每次只處理一頁，確保：
- 每個物理頁的內容獨立輸出
- 不會發生跨頁內容合併
- 頁碼與 PDF 物理頁碼嚴格對應

### 新增函數

#### `demo/demo.py` - `get_pdf_page_count`

```python
def get_pdf_page_count(pdf_path: Path) -> int:
    """
    Get the total number of pages in a PDF file.
    """
    import pypdfium2 as pdfium
    pdf_bytes = read_fn(pdf_path)
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    page_count = len(pdf_doc)
    pdf_doc.close()
    return page_count
```

#### `demo/demo.py` - `parse_doc_by_physical_page`

```python
def parse_doc_by_physical_page(
    pdf_path: Path,
    output_dir,
    lang="ch",
    backend="pipeline",
    method="auto",
    server_url=None,
    disable_image_extract=False,
):
    """
    Parse PDF page by page, bypassing MinerU's semantic merging mechanism.
    This ensures each physical page's content is strictly separated.

    Suitable for scenarios requiring page-based text search.

    Output format (JSON file):
    [
        {"pageNo": 1, "words": "text content of physical page 1"},
        {"pageNo": 2, "words": "text content of physical page 2"},
        ...
    ]
    """
```

### 使用方式

```python
from demo import parse_doc_by_physical_page
from pathlib import Path

# 單一 PDF 逐頁解析
result = parse_doc_by_physical_page(
    pdf_path=Path("document.pdf"),
    output_dir="output_dir",
    backend="pipeline",
    disable_image_extract=True,  # 可選：啟用版權限制
)

# 結果會輸出到: output_dir/document_physical_pages.json
```

### 輸出格式

輸出檔案：`{pdf_name}_physical_pages.json`

```json
[
  {"pageNo": 1, "words": "第一頁的純文字內容..."},
  {"pageNo": 2, "words": "第二頁的純文字內容..."},
  {"pageNo": 3, "words": "第三頁的純文字內容..."}
]
```

### 與 client_json 的差異

| 特性 | `output_format="client_json"` | `parse_doc_by_physical_page` |
|------|-------------------------------|------------------------------|
| 頁碼對應 | 邏輯頁（可能有空頁） | 物理頁（嚴格對應） |
| 跨頁合併 | 會發生 | 不會發生 |
| 適用場景 | RAG chunking | 頁面文字搜尋 |
| 效能 | 較快（批次處理） | 較慢（逐頁處理） |
| 輸出檔名 | `{name}.json` | `{name}_physical_pages.json` |

### 注意事項

1. **效能考量**：逐頁處理會比批次處理慢，但對於 pipeline 後端影響可接受（模型為 singleton）
2. **跨頁內容**：跨頁表格、段落會被切斷，這是此模式的預期行為
3. **單一檔案**：此函數設計為處理單一 PDF 檔案

---

## 功能六：異步 PDF 解析 API (FastAPI)

### 功能說明

提供 RESTful API 介面，採用異步任務模式處理 PDF 解析請求。客戶端先提交 PDF 取得 `task_id`，後續使用 `task_id` 輪詢查詢解析結果。適合需要 HTTP API 整合的應用場景。

### 設計架構

```
┌──────────┐          ┌─────────────────┐          ┌──────────────────┐
│  Client  │          │   FastAPI Server │          │ Background Worker│
└────┬─────┘          └────────┬────────┘          └────────┬─────────┘
     │                         │                            │
     │  POST /api/v1/parse     │                            │
     │    (上傳 PDF)           │                            │
     ├────────────────────────>│                            │
     │                         │  生成 task_id              │
     │                         │  存入任務隊列              │
     │                         ├───────────────────────────>│
     │  返回 task_id           │                            │
     │<────────────────────────┤                            │
     │                         │                            │  開始處理 PDF
     │                         │                            │  (parse_doc_by_physical_page)
     │  GET /result/{task_id}  │                            │
     ├────────────────────────>│                            │
     │  返回 processing        │                            │
     │<────────────────────────┤                            │
     │                         │                            │  處理完成
     │  GET /result/{task_id}  │                            │
     ├────────────────────────>│                            │
     │  返回 completed + 結果  │                            │
     │<────────────────────────┤── 自動刪除臨時檔案         │
```

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `demo/api.py` | FastAPI 應用程式主體 |
| `demo/test_api.py` | API 測試腳本 |

---

### API 端點

#### 1. 提交 PDF 解析任務

```
POST /api/v1/parse
Content-Type: multipart/form-data

Request:
  - file: PDF 檔案 (required)

Response: 201 Created
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

#### 2. 查詢任務結果

```
GET /api/v1/result/{task_id}

Response (等待中): 202 Accepted
{
  "task_id": "550e8400-...",
  "status": "pending"
}

Response (處理中): 202 Accepted
{
  "task_id": "550e8400-...",
  "status": "processing"
}

Response (完成): 200 OK
{
  "task_id": "550e8400-...",
  "status": "completed",
  "result": [
    {"pageNo": 1, "words": "第一頁內容..."},
    {"pageNo": 2, "words": "第二頁內容..."}
  ]
}
# 注意：返回後自動刪除任務資料和臨時檔案

Response (失敗): 200 OK
{
  "task_id": "550e8400-...",
  "status": "failed",
  "error": "錯誤訊息"
}

Response (不存在): 404 Not Found
{
  "detail": "Task not found"
}
```

#### 3. 健康檢查

```
GET /api/v1/health

Response: 200 OK
{
  "status": "healthy",
  "pending_tasks": 0,
  "processing_tasks": 1
}
```

#### 4. Swagger UI 文檔

FastAPI 內建 OpenAPI 文檔：

| 界面 | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

### 任務狀態流程

```
         提交任務              開始處理              處理完成
┌─────────┐      ┌────────────┐      ┌────────────┐
│ pending │ ───> │ processing │ ───> │ completed  │
└─────────┘      └────────────┘      └────────────┘
                       │
                       │ 發生錯誤
                       ▼
                 ┌──────────┐
                 │  failed  │
                 └──────────┘
```

---

### 核心實作說明

#### `demo/api.py`

```python
# 主要組件

# 1. 任務狀態管理
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 2. 任務資料結構
class TaskData:
    task_id: str
    status: TaskStatus
    pdf_path: Path
    output_dir: Path
    result: Optional[list]
    error: Optional[str]
    created_at: datetime

# 3. 背景任務執行器 (ThreadPoolExecutor)
executor = ThreadPoolExecutor(max_workers=2)

# 4. 任務存儲 (記憶體字典)
tasks: dict[str, TaskData] = {}
```

**設計特點：**

1. **異步處理**：使用 `ThreadPoolExecutor` 在背景執行 PDF 解析，避免阻塞 HTTP 請求
2. **物理頁面模式**：預設使用 `parse_doc_by_physical_page`，確保頁碼與 PDF 物理頁嚴格對應
3. **自動清理**：任務完成並被取回後，自動刪除臨時檔案和任務資料
4. **版權限制**：預設 `disable_image_extract=True`，不提取圖片

---

### 使用方式

#### 啟動 API 服務器

```bash
cd /home/cobra/projects/MinerU_opendatalab/demo

# 方式一：使用 uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000

# 方式二：直接執行
python api.py
```

#### 使用 curl 測試

```bash
# 1. 提交 PDF
curl -X POST "http://localhost:8000/api/v1/parse" \
  -F "file=@pdfs/demo1.pdf"
# Response: {"task_id": "xxx-xxx", "status": "pending"}

# 2. 查詢結果（輪詢直到 completed）
curl "http://localhost:8000/api/v1/result/{task_id}"
# Response: {"task_id": "...", "status": "completed", "result": [...]}
```

#### 使用測試腳本

```bash
# 測試 pdfs/ 目錄下所有 PDF
python test_api.py

# 指定單一 PDF
python test_api.py --pdf pdfs/demo1.pdf

# 指定其他 PDF 目錄
python test_api.py --pdf-dir /path/to/pdfs/

# 自訂輸出目錄
python test_api.py --output-dir my_results/

# 自訂 API URL
python test_api.py --url http://192.168.1.100:8000
```

**測試腳本功能：**
- 自動測試指定目錄下所有 PDF 檔案
- 將每個任務的結果 JSON 保存到輸出目錄
- 測試錯誤處理（非 PDF 檔案、不存在的 task_id）

---

### 輸出範例

處理 `small_ocr.pdf` (8 頁) 的 API 回應：

```json
{
  "task_id": "1e29c637-5dd5-419b-95c2-408ea561ee2b",
  "status": "completed",
  "result": [
    {
      "pageNo": 1,
      "words": "史的事情。(3)为有用物的量找到社会尺度，也是这样..."
    },
    {
      "pageNo": 2,
      "words": "内在的交换价值似乎是经院哲学家所说的形容语的矛盾..."
    },
    {
      "pageNo": 3,
      "words": "的、化学的属性等等。商品的天然属性只是就它们使商品有用..."
    }
  ]
}
```

---

### 檔案變更總覽（更新）

```
MinerU_opendatalab/
├── demo/
│   ├── api.py                     [新增] FastAPI 異步 API 應用
│   ├── test_api.py                [新增] API 測試腳本
│   ├── md_to_plaintext.py         [既有] Markdown 轉純文字工具
│   ├── demo.py                    [既有] 核心解析函數
│   ├── CHANGELOG_CUSTOM.md        [更新] 本變更紀錄文件
│   └── output_api_test/           [新增] API 測試輸出目錄
│
└── mineru/
    └── (既有修改，見功能一至五)
```

---

## 功能總結（更新）

| 功能 | 參數/函數 | 說明 |
|------|----------|------|
| 純文字輸出 | `output_format="plaintext"` | 輸出 .txt 檔案，移除所有 Markdown 格式 |
| 版權限制 | `disable_image_extract=True` | 不提取圖片，顯示版權提示 |
| 客戶端 JSON | `output_format="client_json"` | 分頁純文字（邏輯頁，有語意合併） |
| 物理頁面模式 | `parse_doc_by_physical_page()` | 分頁純文字（物理頁，無語意合併） |
| 異步 API | `api.py` | RESTful API，異步任務模式 |

### 完整使用範例

```python
from demo import parse_doc, parse_doc_by_physical_page
from pathlib import Path

# 情境 A: RAG 應用 - 使用語意合併的 client_json
parse_doc(
    [Path("document.pdf")],
    "output_dir",
    backend="pipeline",
    disable_image_extract=True,
    output_format="client_json"
)

# 情境 B: 頁面搜尋應用 - 使用物理頁面模式
parse_doc_by_physical_page(
    pdf_path=Path("document.pdf"),
    output_dir="output_dir",
    backend="pipeline",
    disable_image_extract=True,
)

# 情境 C: HTTP API 整合 - 啟動 API 服務器
# uvicorn api:app --host 0.0.0.0 --port 8000
```

### API 使用範例 (Python requests)

```python
import requests
import time

API_URL = "http://localhost:8000"

# 1. 提交 PDF
with open("document.pdf", "rb") as f:
    resp = requests.post(f"{API_URL}/api/v1/parse", files={"file": f})
task_id = resp.json()["task_id"]

# 2. 輪詢結果
while True:
    resp = requests.get(f"{API_URL}/api/v1/result/{task_id}")
    data = resp.json()
    if data["status"] == "completed":
        result = data["result"]  # [{pageNo: 1, words: "..."}, ...]
        break
    elif data["status"] == "failed":
        raise Exception(data["error"])
    time.sleep(3)
```
