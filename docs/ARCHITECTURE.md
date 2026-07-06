# Architecture

## 1. System Overview

Personal Knowledge Hub uses a local-first architecture.

```text
Browser Extension
        |
        | save page / generate context / insert context
        v
Vue Frontend  <---- REST API ---->  FastAPI Backend
                                      |
                                      | SQLite metadata and knowledge chunks
                                      v
                                  SQLite DB
                                      |
                                      | optional vector index
                                      v
                                    Chroma
                                      |
                                      | optional OpenAI-compatible APIs
                                      v
                           Chat Model / Embedding Model
```

## 2. Modules

### Backend

Path: `backend/`

Responsibilities:

- Knowledge item CRUD
- File upload and document parsing
- Chunk generation
- Processing job records
- Model configuration persistence
- Context generation
- Optional Chroma vector indexing
- Browser extension APIs

Core files:

```text
backend/app/main.py             FastAPI routes and orchestration
backend/app/database.py         SQLite schema, migrations, seed data
backend/app/document_parser.py  TXT / Markdown / PDF / Word / MinerU parsing
backend/app/vector_store.py     Embedding API and Chroma integration
```

### Frontend

Path: `frontend/`

Responsibilities:

- Dashboard
- Knowledge library
- Import knowledge
- Processing queue
- Knowledge graph
- Context debug console
- Model configuration
- System settings

### Browser Extension

Path: `browser-extension/`

Responsibilities:

- Connect to local backend
- Save current page or selected content
- Generate context from local knowledge
- Insert generated context into Web AI input boxes
- Fall back to local IndexedDB memory when backend is unavailable

## 3. Data Storage

The MVP uses SQLite for local metadata and knowledge content.

Main tables:

- `knowledge_items`
- `knowledge_chunks`
- `processing_jobs`
- `graph_nodes`
- `graph_edges`
- `model_config`

Runtime data is stored under `backend/data/` and should not be committed.

## 4. Retrieval Paths

### Keyword Retrieval

Default mode. It does not require model credentials and is suitable for the first local run.

### Vector Retrieval

Optional mode.

Flow:

```text
Knowledge content -> chunks -> Embedding API -> Chroma
Question -> Embedding API -> Chroma query -> context prompt
```

Chroma can run in local persistent mode or connect to a standalone HTTP Chroma server. Chat and Embedding settings are stored separately so different model vendors can be used together.

## 5. Document Parsing

Two parsing modes are supported:

- Local Python parser: `pypdf` and `python-docx`
- MinerU service parser: external HTTP parsing service using `files + model + only_md`, supporting Markdown text/stream responses

The parser mode and MinerU endpoint are configured from the frontend and take effect without restarting the backend.

## 6. Current Boundaries

The current project is an MVP. It intentionally avoids:

- Multi-user account system
- Cloud sync
- Payment and licensing
- Complex task queue
- Mobile app
- Enterprise permission model

These capabilities can be added after the local personal workflow is stable.
