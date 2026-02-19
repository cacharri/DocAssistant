CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  doc_type TEXT NOT NULL,          -- md, txt, pdf
  sha256 TEXT NOT NULL,
  bytes BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source, sha256)
);

CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  page INT NULL,                   -- for pdf
  char_start INT NOT NULL,
  char_end INT NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
