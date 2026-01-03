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

    Args:
        input_path: Path to the input .md file
        output_path: Path for output .txt file (optional, auto-generated if not provided)
        keep_formulas: If True, keep LaTeX formulas

    Returns:
        Path to the output file
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

    Args:
        input_dir: Input directory containing .md files
        output_dir: Output directory for .txt files (optional, same as input if not provided)
        keep_formulas: If True, keep LaTeX formulas

    Returns:
        List of output file paths
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_files = []
    for md_file in input_dir.rglob('*.md'):
        # Preserve relative path structure
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
