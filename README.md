# DocAssistant (RAG-lite, sin LLM, production-minded)

DocAssistant es un servicio de consulta sobre documentos (PDFs) que devuelve **evidencia verificable** (fragmentos + citas) para una pregunta.

- ✅ **Sin LLM** (por ahora): el sistema **no “inventa”**; solo devuelve fragmentos relevantes y/o una respuesta basada en esos fragmentos.
- ✅ **Citas auditables**: `source` + `page` + `chunk_id` + `score`.
- ✅ **Abstención (“no sé”)** cuando no hay evidencia suficiente (`abstained=true`).
- ✅ **Evaluación reproducible** del retrieval (gold/no-evidence) para detectar regresiones.
- ✅ **Dockerizado** con Postgres y Redis.

---

## Why this matters (AI Engineer / Applied ML)

En sistemas reales, lo importante no es “hablar bonito”, sino:

- **Reducir alucinaciones**: responder **solo** cuando hay evidencia.
- **Trazabilidad**: poder auditar de dónde sale cada afirmación.
- **Evaluabilidad**: medir calidad del retrieval (Recall/MRR) y no-evidence (abstención).
- **Operación**: reproducibilidad (Docker), tests, latencia, logs, request IDs.

DocAssistant separa claramente:

- **Retrieval** (búsqueda + citas) → medible y testeable.
- **Answering** (actualmente extractivo/stub) → puede mejorarse sin tocar el retrieval.

---

## Qué problema resuelve

Cuando trabajas/estudias con varios PDFs, buscar manualmente es lento.
DocAssistant te permite preguntar y obtener:

- fragmentos relevantes
- citas verificables
- scores y debug (opcional) para inspección

---

## Arquitectura

### Servicios (Docker Compose)

- **api**: FastAPI + Uvicorn
- **postgres**: almacén de documentos/chunks/embeddings
- **redis**: reservado para cache/cola (listo para crecer)

### Pipeline

1. **Ingesta**: PDF → texto → chunks → Postgres
2. **Indexado**: chunks → embeddings → FAISS index (`data/index/`)
3. **Consulta**:
   - embed query → FAISS top candidates
   - fetch chunks (Postgres)
   - asigna `_score` por `faiss_id`
   - filter por umbral (row)
   - dedupe por (`source`, `page`)
   - cap a `MAX_CITATIONS`
   - respuesta con citas / abstención

---

## Endpoints

### `GET /health`

Healthcheck del servicio.

**Response**

```json
{ "status": "ok" }
```

---

### `POST /search`

Retrieval “puro” (inspección / evaluación / UI).

**Request**

```json
{ "query": "Explain gradient descent and learning rate." }
```

**Response (shape)**

- `hits`: lista de fragmentos con `text`, `source`, `page`, `chunk_id`, `score`
- `request_id`: id de request
- `latency_ms`
- `debug` (si `DEBUG_RAG=1`)

---

### `POST /ask`

Respuesta basada en evidencia (sin LLM): devuelve un texto con fragmentos relevantes y citas.

**Request**

```json
{ "question": "What is gradient descent?" }
```

**Response (shape)**

- `answer`: texto basado en evidencia
- `citations`: lista de citas `{source,page,chunk_id,score}`
- `abstained`: `true` si no hay evidencia suficiente
- `request_id`
- `latency_ms`
- `cost_usd`: 0.0 (sin LLM)
- `debug` (si `DEBUG_RAG=1`)

---

## Requisitos

- Docker + Docker Compose

---

## Quickstart

### 1) Configura variables de entorno

Crea `.env` (ejemplo funcional):

```bash
APP_NAME=DocAssistant
APP_ENV=local
LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://docassistant:docassistant@postgres:5432/docassistant
REDIS_URL=redis://redis:6379/0

# Retrieval
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
INDEX_DIR=data/index
SEARCH_CANDIDATES_K=15
MAX_CITATIONS=5

# Thresholds (calibrables)
MIN_TOP_SCORE=0.30
MIN_ROW_SCORE=0.30
MIN_SCORE_GAP=0.02
MIN_TOP_SCORE_MARGIN=0.05

# Debug
DEBUG_RAG=0
```

> Nota: `DEBUG_RAG=1` hará que `/ask` y `/search` devuelvan un bloque `debug` con detalles del retrieval.

---

### 2) Levanta servicios

```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health
```

---

## Ingesta e indexado

### 1) Añade PDFs

Coloca tus PDFs en el directorio que usa tu ingesta (según tu implementación actual en `app/ingest/ingest.py`).

> Si todavía no has parametrizado el directorio, mantén una carpeta fija (por ejemplo `data/pdfs/`) y úsala de forma consistente.

### 2) Ejecuta ingesta

```bash
docker compose run --rm api python -m app.ingest.ingest
```

Verifica conteos (opcional):

```bash
docker exec -it docassistant-postgres psql -U docassistant -d docassistant -c "SELECT count(*) FROM documents;"
docker exec -it docassistant-postgres psql -U docassistant -d docassistant -c "SELECT count(*) FROM chunks;"
```

### 3) Construye índice FAISS

```bash
docker compose run --rm api python -m app.retrieval.build_index
ls -lah data/index
```

---

## Probar el sistema

### `/search`

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain gradient descent and learning rate."}'
```

### `/ask`

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is gradient descent?"}'
```

---

## Evaluación del retrieval

El retrieval se evalúa sin depender de un LLM.

### Gold eval (Recall/MRR)

```bash
docker compose run --rm api python -m app.eval.retrieval_eval \
  --data data/eval/retrieval_gold.jsonl \
  --out data/eval/report_gold.json \
  --k 5
```

### No-evidence eval (abstención)

```bash
docker compose run --rm api python -m app.eval.retrieval_eval \
  --data data/eval/retrieval_no_evidence.jsonl \
  --out data/eval/report_no_evidence.json \
  --k 5
```

---

## Tests

```bash
docker compose run --rm api pytest -q
```

---

## Atajos con Makefile (opcional)

Si usas el `Makefile`, tienes targets de conveniencia (misma lógica que los comandos anteriores):

```bash
make up       # docker compose up -d --build
make ingest   # ingesta PDFs
make index    # build FAISS
make eval     # eval retrieval
make test     # pytest
make logs     # tail logs
make psql     # shell psql
```

> El Makefile no es obligatorio: puedes ejecutar los `docker compose ...` directamente.

---

## Observabilidad / Debug

- Cada request tiene un `request_id` (middleware) y se propaga en logs.
- Si `DEBUG_RAG=1`, las respuestas incluyen `debug` con:
  - parámetros de retrieval
  - `faiss_ids` y `scores`
  - `returned_chunks`
  - timings (`search_total`, `db_fetch`, `total`)

---

## Rendimiento (referencia)

En un entorno típico (CPU):

- RAM: ~300–700MB (modelo de embeddings + índice, depende del tamaño del corpus)
- Latencia: ~15–50ms por query tras warmup (depende de máquina e índice)

Puedes monitorizar con:

```bash
docker stats --no-stream
```
