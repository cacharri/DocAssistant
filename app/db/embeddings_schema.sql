CREATE TABLE IF NOT EXISTS chunk_embeddings (
  chunk_id BIGINT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  dim INT NOT NULL,
  faiss_id BIGINT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model_name);
