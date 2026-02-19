import hashlib
from pathlib import Path
from typing import Optional
from app.ingest.extract import extract_text_from_md_or_txt, extract_text_from_pdf
from app.ingest.chunking import chunk_text
from app.db.repo import upsert_document, insert_chunk

SUPPORTED = {".md", ".txt", ".pdf"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def detect_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".md":
        return "md"
    if ext == ".txt":
        return "txt"
    if ext == ".pdf":
        return "pdf"
    return "unknown"

def ingest_dir(docs_dir: Path) -> int:
    total_chunks = 0
    for path in docs_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED:
            continue

        doc_type = detect_type(path)
        digest = sha256_file(path)
        size = path.stat().st_size
        source = str(path.relative_to(docs_dir))

        doc_id = upsert_document(source, doc_type, digest, size)

        if doc_type in ("md", "txt"):
            pages = extract_text_from_md_or_txt(path)
        else:
            pages = extract_text_from_pdf(path)

        chunk_index = 0
        for page_num, text in pages:
            for ch in chunk_text(page_num, text):
                insert_chunk(
                    document_id=doc_id,
                    chunk_index=chunk_index,
                    page=ch["page"],
                    char_start=ch["char_start"],
                    char_end=ch["char_end"],
                    text=ch["text"],
                )
                total_chunks += 1
                chunk_index += 1

    return total_chunks

if __name__ == "__main__":
    docs = Path("data/docs")
    if not docs.exists():
        raise SystemExit("Missing data/docs. Create it and add .md/.txt/.pdf files.")
    n = ingest_dir(docs)
    print(f"Ingested chunks: {n}")
