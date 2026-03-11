#!/usr/bin/env python3
"""
增强的 PDF 解析脚本 - 支持完整内容提取
"""
import sys
import json
from pathlib import Path

try:
    from PyPDF2 import PdfReader
    
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "docs/examples/TheLastLeaf.pdf"
    
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    
    reader = PdfReader(pdf_path)
    
    # 提取每页完整文本
    pages_content = []
    full_text = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text.strip():
            pages_content.append({
                "page_number": i + 1,
                "text": text.strip(),
                "char_count": len(text.strip())
            })
            full_text.append(text.strip())
    
    result = {
        "success": True,
        "file": pdf_path,
        "summary": {
            "total_pages": len(reader.pages),
            "pages_with_text": len(pages_content),
            "total_characters": sum(p["char_count"] for p in pages_content),
            "metadata": {
                "title": reader.metadata.title if reader.metadata and reader.metadata.title else "未指定",
                "author": reader.metadata.author if reader.metadata and reader.metadata.author else "未指定",
                "subject": reader.metadata.subject if reader.metadata and reader.metadata.subject else None,
            }
        },
        "pages": pages_content,
        "full_text": "\n\n".join(full_text)
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "PyPDF2 未安装，请运行: pip install PyPDF2"
    }, ensure_ascii=False, indent=2))
except FileNotFoundError as e:
    print(json.dumps({
        "success": False,
        "error": str(e)
    }, ensure_ascii=False, indent=2))
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"解析失败: {str(e)}"
    }, ensure_ascii=False, indent=2))
