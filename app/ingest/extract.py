from pathlib import Path
from typing import List, Tuple, Optional
from pypdf import PdfReader

def extract_text_from_md_or_txt(path: Path) -> List[Tuple[Optional[int], str]]:
    # returns list of (page, text). For md/txt page=None
    return [(None, path.read_text(encoding="utf-8", errors="ignore"))]

def extract_text_from_pdf(path: Path) -> List[Tuple[Optional[int], str]]:
    reader = PdfReader(str(path))
    out: List[Tuple[Optional[int], str]] = []
    for i, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        out.append((i + 1, txt))
    return out
