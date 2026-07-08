# Personal Knowledge Hub

[English](README.md) | [简体中文](README.zh-CN.md)

> Local-first personal AI memory and knowledge context layer.

Personal Knowledge Hub is a local-first AI memory layer and knowledge context workspace for people who use AI tools heavily. It is not just another note-taking app. It helps you turn personal background, project materials, historical decisions, webpages and documents into searchable, inspectable and AI-ready context that can be injected into Web AI conversations.

## Why

General-purpose AI is powerful, but it usually does not know your personal background, project history, decisions, constraints or long-term preferences. As a result, you often have to repeatedly explain the same context before the answer becomes useful.

Personal Knowledge Hub is built for this workflow:

```text
Collect scattered personal knowledge locally, parse it, split it into chunks, retrieve it with keyword/vector/graph signals, and generate explainable context for AI conversations.
```

## Screenshots

### Dashboard

![Dashboard](docs/assets/dashboard.png)

### Knowledge Library

![Knowledge Library](docs/assets/knowledge-library.png)

### Context Debug Console

![Context Debug Console](docs/assets/context-console.png)

### Knowledge Graph

![Knowledge Graph](docs/assets/knowledge-graph.png)

## Features

- Local-first knowledge workspace powered by FastAPI, SQLite and Vue.
- Import manual notes, webpages, TXT, Markdown, PDF and Word documents.
- Parse documents locally with Python or switch to an external MinerU parser service.
- Split knowledge into chunks and inspect processing status from the queue.
- Generate AI-ready context from personal knowledge with transparent retrieval hits.
- Switch between keyword retrieval and Embedding + Chroma vector retrieval.
- Configure Chat and Embedding models separately for different OpenAI-compatible vendors.
- Visualize personal entities, decisions, projects and risks as a lightweight knowledge graph.
- Use the browser extension to save pages and inject generated context into Web AI tools.

## Product Modules

```text
Dashboard              System status, knowledge metrics and recent context activity
Knowledge Library      Manage notes, documents, webpages, tags and source metadata
Import Knowledge       Add manual notes, webpages and local files
Processing Queue       Track document parsing, chunking and future AI processing steps
Knowledge Graph        Display entities, relationships and evidence network
Context Console        Debug retrieval hits and generate final prompt context
Model Settings         Configure Chat, Embedding, MinerU and Chroma without restart
Browser Extension      Save page content and insert context into Web AI conversations
```

## Repository Structure

This repository uses a monorepo layout:

```text
personal-knowledge-hub/
├── backend/              # FastAPI + SQLite backend
├── frontend/             # Vue 3 + Vite management console
├── browser-extension/    # Chrome / Edge browser extension
├── docs/                 # Architecture, development and product docs
├── .env.example
├── .gitignore
├── README.md             # English README, default on GitHub
└── README.zh-CN.md       # Simplified Chinese README
```

## Architecture

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

## Quick Start

### 1. Start Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload
```

Health check:

```text
http://127.0.0.1:8088/api/health
```

SQLite, uploaded files and Chroma runtime data are stored under `backend/data/`, which is ignored by Git.

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5175
```

The frontend talks to:

```text
http://127.0.0.1:8088/api
```

If the backend is offline, the UI falls back to built-in mock data.

### 3. Build Browser Extension

```bash
cd browser-extension
npm install
npm run build
```

Open the Chrome / Edge extension management page, enable developer mode, then load:

```text
browser-extension/dist
```

The extension connects to the local service by default:

```text
http://127.0.0.1:8088
```

## Model Configuration

Open the frontend Model Settings page. Chat and Embedding models can be configured separately, so you can use different vendors together.

Chat model:

```text
Chat Base URL
Chat API Key
Chat Model
Chat Timeout
```

Embedding model:

```text
Embedding Base URL
Embedding API Key
Embedding Model
Embedding Timeout
```

For example, you can use DeepSeek or Qwen-compatible APIs for Chat, and OpenAI or a local compatible service for Embedding.

## Retrieval Modes

Personal Knowledge Hub supports two context retrieval paths:

- Keyword retrieval: default mode, no model credential required.
- Embedding + Chroma vector retrieval: embeds chunks through an OpenAI-compatible Embedding API and stores vectors in Chroma.

Chroma supports two connection modes from Model Settings:

- Local persistent mode: uses `backend/data/chroma` or a custom local path.
- HTTP service mode: connects to a standalone Chroma server with host, port, SSL and optional API key.

After switching to vector retrieval, click `Rebuild Vector Index` to write existing chunks into Chroma. Newly imported or edited knowledge will update the vector index automatically.

## Document Parsing

The parser mode can be changed from the Model Settings page and takes effect without restarting the backend.

- Local Python parser: PDF via `pypdf`, Word via `python-docx`.
- MinerU service parser: external HTTP parser service.

MinerU request contract:

```text
POST {MinerU Parser URL}
Content-Type: multipart/form-data
Authorization: Bearer <MinerU API Key, optional>
files: uploaded file
model: mineru-vl
only_md: true
```

`MinerU Parser URL` can be a full private endpoint such as `/openapi/v1/ocr/mineru-parser`. The response can be a Markdown text stream, or JSON containing one of these fields: `text`, `content`, `markdown`, `md`, or `data`.

## API Overview

```text
GET    /api/health
GET    /api/dashboard
GET    /api/knowledge-items
POST   /api/knowledge-items
PATCH  /api/knowledge-items/{item_id}
DELETE /api/knowledge-items/{item_id}
POST   /api/import/manual
POST   /api/import/webpage
POST   /api/import/file
GET    /api/jobs
GET    /api/graph
POST   /api/context/generate
GET    /api/model-config
POST   /api/model-config
POST   /api/model-config/test-chat
POST   /api/model-config/test-embedding
POST   /api/vector/rebuild
```

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Product PRD](docs/PRD.md)
- [Security](docs/SECURITY.md)

## Roadmap

Planned next steps:

- Real processing worker for summary, tags, entity extraction and relation extraction.
- Better hybrid retrieval with keyword + vector + graph signals.
- Knowledge graph editing, relation evidence and confirmation workflow.
- Prompt templates and context compression.
- Local LLM support.
- Optional multi-device sync.

More public roadmap details will be added as the project becomes stable.

## Open Source Notes

Please do not commit:

- `.env`, API keys or model credentials
- SQLite runtime data under `backend/data/`
- uploaded personal files
- Chroma runtime data
- `node_modules/`
- frontend or extension build outputs under `dist/`
- real personal documents or private knowledge base data

## License

MIT
