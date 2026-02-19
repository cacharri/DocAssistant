from typing import List, Tuple, Optional

def chunk_text(page: Optional[int], text: str, chunk_size: int = 1000, overlap: int = 150):
    # yields dicts: {page, char_start, char_end, text}
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunks = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append({
                "page": page,
                "char_start": start,
                "char_end": end,
                "text": chunk,
            })
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks
