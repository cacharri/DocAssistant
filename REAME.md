# DocAssistant (RAG-lite, production-minded)

DocAssistant es un asistente de consulta sobre documentos (PDFs) que devuelve **fragmentos relevantes con citas verificables** (`source` + `page` + `chunk_id` + `score`).
Está diseñado como base “production-grade” para evolucionar a un RAG completo (añadiendo un LLM más adelante), manteniendo:

- **Trazabilidad** (citas)
- **“No sé”** cuando no hay evidencia
- **Observabilidad** (`x-request-id`, timings en `debug`)
- Arquitectura reproducible con Docker

---

## Why this matters (AI Engineer / MLOps)

En producción, el reto no es “que el modelo hable bonito”, sino:

- **Reducir alucinaciones**: responder solo con evidencia.
- **Trazabilidad**: poder auditar de dónde sale cada afirmación (citas).
- **Evaluabilidad**: medir calidad del retrieval (endpoint `/search`).
- **Operación**: reproducibilidad, tests, logs, latencia, coste.

DocAssistant está estructurado para:

- medir retrieval de forma aislada (`/search`)
- añadir generación con LLM después (RAG “completo”)
- introducir guardrails y evaluación en CI

---

## Qué problema resuelve

Cuando estudias o trabajas con varios PDFs (ML/AI Systems/MLOps), buscar información manualmente es lento.
DocAssistant permite hacer preguntas y obtener:

- extractos relevantes
- citas para verificar
- scores y debug para inspección

---

## Arquitectura

### Servicios (Docker Compose)

- **api**: FastAPI + Uvicorn
- **postgres**: almacena documentos y chunks
- **redis**: reservado para caching/cola (listo para crecer)

### Pipeline

1. **Ingesta**: PDF → texto → chunks → Postgres
2. **Indexado**: chunks → embeddings → FAISS index (`data/index/`)
3. **Consulta**:
   - embed query → FAISS top candidates
   - fetch chunks (Postgres)
   - dedupe por (`source`, `page`)
   - cap a `MAX_CITATIONS`
   - respuesta con citas

---

## Endpoints

### `GET /health`

Healthcheck del servicio.

### `POST /search`

Retrieval “puro” (para evaluación/UI).

**Request**

```json
{ "query": "Explain gradient descent and learning rate." }
```

**Response**

- `hits`: lista de fragmentos (`text`, `source`, `page`, `chunk_id`, `score`)
- `debug`: timings y parámetros si `DEBUG_RAG=true`

### `POST /ask`

Respuesta humana basada en retrieval (sin LLM aún; devuelve extractos + citas).

**Request**

```json
{ "question": "Explain gradient descent and learning rate." }
```

---

## Requisitos

- Docker + Docker Compose

---

## Quickstart

### 1) Configura variables de entorno

Crea `.env` (ejemplo):

```bash
APP_NAME=docassistant
LOG_LEVEL=INFO

# Retrieval
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
INDEX_DIR=data/index
MIN_SCORE=0.30
SEARCH_CANDIDATES_K=15
MAX_CITATIONS=5
DEBUG_RAG=true

# Postgres (si tu app las lee desde env)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=docassistant
POSTGRES_USER=docassistant
POSTGRES_PASSWORD=docassistant
```

> Nota: adapta los nombres exactos si tu `Settings` usa otros alias.

### 2) Levanta servicios

```bash
docker compose up -d --build
docker compose ps
curl -i http://localhost:8000/health
```

---

## Ingesta e indexado

### 1) Añade PDFs

Coloca PDFs en el directorio que uses para ingesta (por ejemplo `data/pdfs/` o el que tengas configurado).

### 2) Ejecuta ingesta (dentro del contenedor)

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
ls -la data/index
```

---

## Probar el sistema

### `/search`

```bash
curl -i --max-time 60 -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain gradient descent and learning rate."}'
```

### `/ask`

```bash
curl -i --max-time 60 -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Explain gradient descent and learning rate."}'
```

---

## Tests

Ejecutar tests dentro del contenedor:

```bash
docker compose run --rm api pytest -q
```

---

## Observabilidad / Debug

- Cada respuesta incluye `x-request-id`
- Si `DEBUG_RAG=true`, la API devuelve:
  - parámetros de retrieval
  - `faiss_ids` y `scores`
  - `returned_chunks`
  - timings por fase (`search_total`, `db_fetch`, `total`)

---

## Rendimiento (referencia)

En un entorno típico:

- `docassistant-api` ~300–500MB RAM (modelo embeddings + índice)
- latencia ~20–50ms por query (dependiendo de warmup)

Puedes monitorizar con:

```bash
docker stats --no-stream
```
